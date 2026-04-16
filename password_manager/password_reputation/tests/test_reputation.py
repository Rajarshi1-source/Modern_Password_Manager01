"""
Tests for the password_reputation app (Phase 2a).

Covers:
  * submit_proof acceptance + score/token minting
  * binding_hash enforcement
  * entropy floor / ceiling clamping
  * rate-limit per-window capping
  * idempotent re-submission per (user, scope_id)
  * slash event path
  * NullAnchor batch flushing via _maybe_flush_batch + explicit flush
  * Merkle root reproducibility
"""

from __future__ import annotations

import base64
import hashlib

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from password_reputation import services
from password_reputation.merkle import hash_leaf, merkle_root
from password_reputation.models import (
    AnchorBatch,
    ReputationAccount,
    ReputationEvent,
    ReputationProof,
)
from password_reputation.providers.commitment_claim import (
    MAX_ENTROPY_BITS,
    MIN_ENTROPY_BITS,
    TOKENS_PER_BIT,
    compute_binding_hash,
)
from zk_proofs.crypto import schnorr, secp256k1 as ec


pytestmark = pytest.mark.django_db


@pytest.fixture
def user_factory(db):
    User = get_user_model()
    counter = {"i": 0}

    def make(**kwargs):
        counter["i"] += 1
        username = kwargs.pop("username", f"rep_user_{counter['i']}")
        email = kwargs.pop("email", f"{username}@example.test")
        return User.objects.create_user(
            username=username, email=email, password="Testpass123!", **kwargs,
        )

    return make


@pytest.fixture
def client_factory():
    def make(user=None):
        c = APIClient()
        if user:
            c.force_authenticate(user=user)
        return c

    return make


def _valid_commitment(seed: bytes = b"rep-test-commitment") -> bytes:
    """Produce a well-formed 33-byte compressed secp256k1 point."""
    m = int.from_bytes(hashlib.sha256(b"m|" + seed).digest(), "big") % ec.N
    r = int.from_bytes(hashlib.sha256(b"r|" + seed).digest(), "big") % ec.N
    point = schnorr.commit(m, r)
    return ec.encode_point(point)


# ----------------------------------------------------------------------------
# Direct-service tests (avoid HTTP stack)
# ----------------------------------------------------------------------------

def test_submit_proof_happy_path(user_factory):
    user = user_factory()
    commitment = _valid_commitment(seed=b"happy")
    bits = 80
    binding = compute_binding_hash(commitment, bits, user.id)

    result = services.submit_proof(
        user=user,
        scope_id="vault-item-1",
        commitment=commitment,
        claimed_entropy_bits=bits,
        binding_hash=binding,
    )

    assert result.accepted is True, result.error
    assert result.proof.status == ReputationProof.STATUS_ACCEPTED
    assert result.proof.score_delta == bits
    assert result.proof.tokens_delta == bits * TOKENS_PER_BIT
    assert result.event is not None
    assert result.event.event_type == ReputationEvent.EVENT_PROOF_ACCEPTED
    assert result.account.score == bits
    assert result.account.tokens == bits * TOKENS_PER_BIT
    assert result.account.proofs_accepted == 1


def test_submit_proof_binding_hash_mismatch_rejects(user_factory):
    user = user_factory()
    commitment = _valid_commitment(seed=b"mismatch")
    bits = 80
    bad_binding = b"\x00" * 32

    result = services.submit_proof(
        user=user,
        scope_id="vault-item-2",
        commitment=commitment,
        claimed_entropy_bits=bits,
        binding_hash=bad_binding,
    )

    assert result.accepted is False
    assert "Binding hash mismatch" in (result.error or "")
    assert result.proof.status == ReputationProof.STATUS_REJECTED
    assert result.account.proofs_rejected == 1
    assert result.account.score == 0
    assert ReputationEvent.objects.filter(
        user=user, event_type=ReputationEvent.EVENT_PROOF_REJECTED,
    ).exists()


def test_submit_proof_entropy_floor_enforced(user_factory):
    user = user_factory()
    bits = MIN_ENTROPY_BITS - 1
    commitment = _valid_commitment(seed=b"floor")
    binding = compute_binding_hash(commitment, bits, user.id)

    result = services.submit_proof(
        user=user,
        scope_id="vault-item-3",
        commitment=commitment,
        claimed_entropy_bits=bits,
        binding_hash=binding,
    )

    assert result.accepted is False
    assert "below minimum" in (result.error or "")
    assert result.account.score == 0


def test_submit_proof_entropy_clamped_to_ceiling(user_factory):
    user = user_factory()
    bits = MAX_ENTROPY_BITS + 50
    commitment = _valid_commitment(seed=b"ceiling")
    binding = compute_binding_hash(commitment, bits, user.id)

    result = services.submit_proof(
        user=user,
        scope_id="vault-item-4",
        commitment=commitment,
        claimed_entropy_bits=bits,
        binding_hash=binding,
    )

    assert result.accepted is True
    assert result.proof.score_delta <= MAX_ENTROPY_BITS
    assert result.account.score <= MAX_ENTROPY_BITS


def test_submit_proof_invalid_commitment_bytes(user_factory):
    user = user_factory()
    bad_commitment = b"\xFF" * 33  # decodable length, invalid point
    bits = 80
    binding = compute_binding_hash(bad_commitment, bits, user.id)

    result = services.submit_proof(
        user=user,
        scope_id="vault-item-5",
        commitment=bad_commitment,
        claimed_entropy_bits=bits,
        binding_hash=binding,
    )

    assert result.accepted is False
    assert "not a valid point" in (result.error or "")


def test_submit_proof_idempotent_per_scope(user_factory):
    user = user_factory()
    commitment = _valid_commitment(seed=b"idempotent-1")
    bits = 60
    binding = compute_binding_hash(commitment, bits, user.id)

    r1 = services.submit_proof(
        user=user,
        scope_id="scope-A",
        commitment=commitment,
        claimed_entropy_bits=bits,
        binding_hash=binding,
    )
    assert r1.accepted

    # Same scope, stronger claim → replaces the prior ReputationProof row.
    commitment2 = _valid_commitment(seed=b"idempotent-2")
    bits2 = 100
    binding2 = compute_binding_hash(commitment2, bits2, user.id)
    r2 = services.submit_proof(
        user=user,
        scope_id="scope-A",
        commitment=commitment2,
        claimed_entropy_bits=bits2,
        binding_hash=binding2,
    )
    assert r2.accepted
    assert ReputationProof.objects.filter(user=user, scope_id="scope-A").count() == 1


def test_submit_proof_rate_limit_clamps_score(user_factory, settings):
    # Force a tiny cap so the first submission saturates the window.
    settings.PASSWORD_REPUTATION = {
        "ANCHOR_ADAPTER": "null",
        "MAX_SCORE_PER_WINDOW": 80,
        "ANCHOR_BATCH_SIZE": 999,
    }
    user = user_factory()
    bits = 80
    c1 = _valid_commitment(seed=b"rl-1")
    services.submit_proof(
        user=user,
        scope_id="scope-R1",
        commitment=c1,
        claimed_entropy_bits=bits,
        binding_hash=compute_binding_hash(c1, bits, user.id),
    )
    c2 = _valid_commitment(seed=b"rl-2")
    r2 = services.submit_proof(
        user=user,
        scope_id="scope-R2",
        commitment=c2,
        claimed_entropy_bits=bits,
        binding_hash=compute_binding_hash(c2, bits, user.id),
    )
    # Second proof accepted but clamped to 0 extra score (cap already hit).
    assert r2.accepted is True
    assert r2.event is not None
    assert r2.event.score_delta == 0


def test_slash_applies_penalty(user_factory):
    user = user_factory()
    commitment = _valid_commitment(seed=b"slash")
    bits = 90
    services.submit_proof(
        user=user,
        scope_id="scope-slash",
        commitment=commitment,
        claimed_entropy_bits=bits,
        binding_hash=compute_binding_hash(commitment, bits, user.id),
    )
    event = services.slash(user=user, score_penalty=40, reason="integration-test-breach")
    assert event.score_delta == -40
    account = services.account_for(user)
    assert account.score == bits - 40
    assert account.last_breach_at is not None


# ----------------------------------------------------------------------------
# Merkle batch flushing via NullAnchor
# ----------------------------------------------------------------------------

def test_flush_pending_batch_with_null_anchor(user_factory, settings):
    settings.PASSWORD_REPUTATION = {
        "ANCHOR_ADAPTER": "null",
        "ANCHOR_BATCH_SIZE": 2,
        "MAX_SCORE_PER_WINDOW": 10_000,
    }
    user = user_factory()
    for idx in range(3):
        commitment = _valid_commitment(seed=f"flush-{idx}".encode())
        bits = 70
        services.submit_proof(
            user=user,
            scope_id=f"scope-flush-{idx}",
            commitment=commitment,
            claimed_entropy_bits=bits,
            binding_hash=compute_binding_hash(commitment, bits, user.id),
        )

    # Force a final flush to pick up any remaining events.
    batch = services.flush_pending_batch()
    assert AnchorBatch.objects.count() >= 1
    last = AnchorBatch.objects.order_by("-created_at").first()
    assert last.adapter == "null"
    assert last.status == AnchorBatch.STATUS_SKIPPED
    assert last.merkle_root.startswith("0x") and len(last.merkle_root) == 66
    # Events in the batch are now anchor_status=skipped.
    skipped_events = ReputationEvent.objects.filter(
        anchor_status=ReputationEvent.ANCHOR_STATUS_SKIPPED,
    )
    assert skipped_events.count() >= 1


def test_merkle_root_reproducible():
    leaves = [
        hash_leaf(bytes.fromhex("aa" * 32)),
        hash_leaf(bytes.fromhex("bb" * 32)),
        hash_leaf(bytes.fromhex("cc" * 32)),
    ]
    root1 = merkle_root(leaves)
    root2 = merkle_root(list(leaves))
    assert root1 == root2
    assert len(root1) == 32


# ----------------------------------------------------------------------------
# HTTP layer smoke tests
# ----------------------------------------------------------------------------

def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def test_http_submit_and_me(user_factory, client_factory):
    user = user_factory()
    client = client_factory(user)
    commitment = _valid_commitment(seed=b"http-happy")
    bits = 90
    binding = compute_binding_hash(commitment, bits, user.id)
    payload = {
        "scope_id": "http-scope-1",
        "commitment": _b64(commitment),
        "claimed_entropy_bits": bits,
        "binding_hash": _b64(binding),
    }
    resp = client.post("/api/reputation/submit-proof/", payload, format="json")
    assert resp.status_code == 200, resp.content
    assert resp.data["accepted"] is True
    assert resp.data["account"]["score"] == bits

    me = client.get("/api/reputation/me/")
    assert me.status_code == 200
    assert me.data["score"] == bits
    assert me.data["tokens"] == bits * TOKENS_PER_BIT

    events = client.get("/api/reputation/events/")
    assert events.status_code == 200
    assert len(events.data) >= 1


def test_http_submit_rejects_bad_binding(user_factory, client_factory):
    user = user_factory()
    client = client_factory(user)
    commitment = _valid_commitment(seed=b"http-bad")
    payload = {
        "scope_id": "http-scope-bad",
        "commitment": _b64(commitment),
        "claimed_entropy_bits": 80,
        "binding_hash": _b64(b"\x00" * 32),
    }
    resp = client.post("/api/reputation/submit-proof/", payload, format="json")
    assert resp.status_code in (200, 202)
    assert resp.data["accepted"] is False


def test_http_config_exposes_adapter_and_schemes(user_factory, client_factory):
    user = user_factory()
    client = client_factory(user)
    resp = client.get("/api/reputation/config/")
    assert resp.status_code == 200
    assert "commitment-claim-v1" in resp.data["schemes"]
    assert resp.data["adapter"] in ("null", "arbitrum")


def test_http_leaderboard_returns_ranked_users(user_factory, client_factory):
    u1 = user_factory()
    u2 = user_factory()
    for u, bits in [(u1, 100), (u2, 60)]:
        commitment = _valid_commitment(seed=f"lb-{u.id}".encode())
        services.submit_proof(
            user=u,
            scope_id=f"lb-scope-{u.id}",
            commitment=commitment,
            claimed_entropy_bits=bits,
            binding_hash=compute_binding_hash(commitment, bits, u.id),
        )
    client = client_factory(u1)
    resp = client.get("/api/reputation/leaderboard/")
    assert resp.status_code == 200
    ranks = [(row["rank"], row["user_id"], row["score"]) for row in resp.data]
    assert ranks[0][2] >= ranks[-1][2]  # descending by score
