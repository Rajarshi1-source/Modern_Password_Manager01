"""
End-to-end-ish tests for the multi-party ZK verification sessions (Phase 1b).

These use Django's ORM directly plus APIClient so they exercise views,
serializers, routing, and the Schnorr provider in one go. They assume the
pytest-django plugin is active (default via pytest.ini).
"""

from __future__ import annotations

import base64

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from zk_proofs.crypto import schnorr
from zk_proofs.models import (
    ZKCommitment,
    ZKSession,
    ZKSessionParticipant,
    ZKVerificationAttempt,
)
from zk_proofs.providers import get_provider


pytestmark = pytest.mark.django_db


@pytest.fixture
def user_factory(db):
    User = get_user_model()
    counter = {"i": 0}

    def make(password="testpass123!", **kwargs):
        counter["i"] += 1
        username = kwargs.pop("username", f"zk_user_{counter['i']}")
        email = kwargs.pop("email", f"{username}@example.test")
        user = User.objects.create_user(username=username, email=email, password=password, **kwargs)
        return user

    return make


@pytest.fixture
def client_factory():
    def make(user=None):
        c = APIClient()
        if user:
            c.force_authenticate(user=user)
        return c

    return make


def _derive_commit(password: str, item_id: str):
    """Reproduce the client-side Pedersen derivation used by the frontend."""
    from hashlib import sha256

    def _to_scalar(tag: bytes, *parts: bytes) -> int:
        h = sha256()
        h.update(tag)
        for p in parts:
            h.update(len(p).to_bytes(4, "big"))
            h.update(p)
        return int.from_bytes(h.digest(), "big") % __import__("zk_proofs.crypto.secp256k1", fromlist=["N"]).N

    m = _to_scalar(b"pwm-zkp-v1|m-scalar|", password.encode("utf-8"), item_id.encode("utf-8"))
    r = _to_scalar(b"pwm-zkp-v1|r-blinding|", password.encode("utf-8"), item_id.encode("utf-8"))
    return m, r


def _register_commitment(user, scope_id, password, scope_type="vault_item"):
    m, r = _derive_commit(password, scope_id)
    point = schnorr.commit(m, r)
    from zk_proofs.crypto import secp256k1 as ec
    blob = ec.encode_point(point)
    return ZKCommitment.objects.create(
        user=user,
        scope_type=scope_type,
        scope_id=scope_id,
        commitment=blob,
        scheme="commitment-schnorr-v1",
    ), m, r


class TestZKSessionCreate:
    def test_create_session_requires_owned_reference(self, user_factory, client_factory):
        owner = user_factory()
        stranger = user_factory()
        ref, _, _ = _register_commitment(owner, "item-1", "hunter2")
        c = client_factory(stranger)

        resp = c.post(
            "/api/zk/sessions/",
            {"reference_commitment_id": str(ref.id)},
            format="json",
        )
        assert resp.status_code == 404

    def test_create_and_list_session(self, user_factory, client_factory):
        owner = user_factory()
        ref, _, _ = _register_commitment(owner, "item-1", "hunter2")
        c = client_factory(owner)

        resp = c.post(
            "/api/zk/sessions/",
            {
                "reference_commitment_id": str(ref.id),
                "title": "Family streaming",
                "expires_in_hours": 24,
            },
            format="json",
        )
        assert resp.status_code == 201, resp.content
        session_id = resp.data["id"]
        assert resp.data["status"] == "open"
        assert resp.data["title"] == "Family streaming"
        assert resp.data["participants"] == []

        resp = c.get("/api/zk/sessions/")
        assert resp.status_code == 200
        assert len(resp.data) == 1
        assert resp.data[0]["id"] == session_id


class TestZKSessionInviteFlow:
    def test_full_verified_flow(self, user_factory, client_factory):
        password = "shared-password-42"
        owner = user_factory()
        alice = user_factory()

        # Owner's reference commitment.
        ref, m_ref, r_ref = _register_commitment(owner, "ref-item", password)
        # Alice's own commitment (her scope_id differs — same password).
        alice_commit, m_alice, r_alice = _register_commitment(alice, "alice-item", password)

        owner_client = client_factory(owner)
        # Create session
        resp = owner_client.post(
            "/api/zk/sessions/",
            {"reference_commitment_id": str(ref.id), "title": "Test"},
            format="json",
        )
        assert resp.status_code == 201
        session_id = resp.data["id"]

        # Invite a participant slot
        resp = owner_client.post(
            f"/api/zk/sessions/{session_id}/invite/",
            {"invited_email": "alice@example.test", "invited_label": "Alice"},
            format="json",
        )
        assert resp.status_code == 201, resp.content
        token = resp.data["invite_token"]
        assert resp.data["status"] == "pending"

        # Alice resolves the invite — should become "joined" and return ref bytes
        alice_client = client_factory(alice)
        resp = alice_client.get(f"/api/zk/sessions/join/{token}/")
        assert resp.status_code == 200
        assert resp.data["reference_commitment_id"] == str(ref.id)
        assert resp.data["reference_scope_id"] == "ref-item"
        assert base64.b64decode(resp.data["reference_commitment_b64"]) == bytes(ref.commitment)

        # Alice builds a Schnorr equality proof using both her blinding and the
        # reference blinding (both re-derivable from the shared password).
        ref_point = schnorr.commit(m_ref, r_ref)
        alice_point = schnorr.commit(m_alice, r_alice)
        T, s = schnorr.prove_equality(ref_point, alice_point, r_ref, r_alice)

        resp = alice_client.post(
            "/api/zk/sessions/submit-proof/",
            {
                "invite_token": token,
                "participant_commitment_id": str(alice_commit.id),
                "proof_T": base64.b64encode(T).decode(),
                "proof_s": base64.b64encode(s).decode(),
            },
            format="json",
        )
        assert resp.status_code == 200, resp.content
        assert resp.data["verified"] is True

        # Owner view reflects the verification.
        resp = owner_client.get(f"/api/zk/sessions/{session_id}/")
        assert resp.status_code == 200
        assert resp.data["verified_count"] == 1
        p = resp.data["participants"][0]
        assert p["status"] == "verified"

    def test_wrong_password_rejected(self, user_factory, client_factory):
        owner = user_factory()
        bob = user_factory()

        ref, m_ref, r_ref = _register_commitment(owner, "ref-item", "correct-password")
        bob_commit, m_bob, r_bob = _register_commitment(bob, "bob-item", "different-password")

        owner_client = client_factory(owner)
        resp = owner_client.post(
            "/api/zk/sessions/",
            {"reference_commitment_id": str(ref.id)},
            format="json",
        )
        session_id = resp.data["id"]
        resp = owner_client.post(
            f"/api/zk/sessions/{session_id}/invite/",
            {"invited_label": "Bob"},
            format="json",
        )
        token = resp.data["invite_token"]

        # Bob assembles a proof using his *own* blinding pair, which will not
        # verify against the reference because his password-derived m differs.
        ref_point = schnorr.commit(m_ref, r_ref)
        bob_point = schnorr.commit(m_bob, r_bob)
        T, s = schnorr.prove_equality(ref_point, bob_point, r_ref, r_bob)

        bob_client = client_factory(bob)
        resp = bob_client.post(
            "/api/zk/sessions/submit-proof/",
            {
                "invite_token": token,
                "participant_commitment_id": str(bob_commit.id),
                "proof_T": base64.b64encode(T).decode(),
                "proof_s": base64.b64encode(s).decode(),
            },
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["verified"] is False

        participant = ZKSessionParticipant.objects.get(invite_token=token)
        assert participant.status == "failed"

    def test_participant_commitment_must_be_owned(self, user_factory, client_factory):
        password = "shared"
        owner = user_factory()
        alice = user_factory()
        bob = user_factory()

        ref, m_ref, r_ref = _register_commitment(owner, "ref-item", password)
        alice_commit, m_alice, r_alice = _register_commitment(alice, "alice-item", password)

        owner_client = client_factory(owner)
        resp = owner_client.post(
            "/api/zk/sessions/",
            {"reference_commitment_id": str(ref.id)},
            format="json",
        )
        session_id = resp.data["id"]
        resp = owner_client.post(
            f"/api/zk/sessions/{session_id}/invite/",
            {"invited_label": "Alice"},
            format="json",
        )
        token = resp.data["invite_token"]

        # Bob tries to submit Alice's commitment — must be rejected.
        ref_point = schnorr.commit(m_ref, r_ref)
        alice_point = schnorr.commit(m_alice, r_alice)
        T, s = schnorr.prove_equality(ref_point, alice_point, r_ref, r_alice)

        bob_client = client_factory(bob)
        resp = bob_client.post(
            "/api/zk/sessions/submit-proof/",
            {
                "invite_token": token,
                "participant_commitment_id": str(alice_commit.id),
                "proof_T": base64.b64encode(T).decode(),
                "proof_s": base64.b64encode(s).decode(),
            },
            format="json",
        )
        # After Bob binds to the invite, Alice's commitment lookup fails (404)
        # because she doesn't own it from request.user's perspective.
        assert resp.status_code == 404

    def test_revoke_blocks_submission(self, user_factory, client_factory):
        password = "abc"
        owner = user_factory()
        alice = user_factory()

        ref, m_ref, r_ref = _register_commitment(owner, "ref-item", password)
        alice_commit, m_alice, r_alice = _register_commitment(alice, "alice-item", password)

        owner_client = client_factory(owner)
        session = owner_client.post(
            "/api/zk/sessions/",
            {"reference_commitment_id": str(ref.id)},
            format="json",
        ).data
        part = owner_client.post(
            f"/api/zk/sessions/{session['id']}/invite/",
            {"invited_label": "Alice"},
            format="json",
        ).data
        owner_client.post(
            f"/api/zk/sessions/{session['id']}/participants/{part['id']}/revoke/",
            format="json",
        )

        alice_client = client_factory(alice)
        resp = alice_client.get(f"/api/zk/sessions/join/{part['invite_token']}/")
        assert resp.status_code == 410

    def test_closing_session_blocks_joins(self, user_factory, client_factory):
        owner = user_factory()
        alice = user_factory()
        ref, _, _ = _register_commitment(owner, "ref-item", "p")
        owner_client = client_factory(owner)
        session = owner_client.post(
            "/api/zk/sessions/",
            {"reference_commitment_id": str(ref.id)},
            format="json",
        ).data
        part = owner_client.post(
            f"/api/zk/sessions/{session['id']}/invite/",
            {"invited_label": "Alice"},
            format="json",
        ).data
        owner_client.delete(f"/api/zk/sessions/{session['id']}/")

        alice_client = client_factory(alice)
        resp = alice_client.get(f"/api/zk/sessions/join/{part['invite_token']}/")
        assert resp.status_code == 410

    def test_expired_session_is_closed_lazily(self, user_factory, client_factory):
        owner = user_factory()
        alice = user_factory()
        ref, _, _ = _register_commitment(owner, "ref-item", "p")
        session = ZKSession.objects.create(
            owner=owner,
            reference_commitment=ref,
            title="Expired",
            expires_at=timezone.now() - timezone.timedelta(hours=1),
        )
        part = ZKSessionParticipant.objects.create(session=session)

        alice_client = client_factory(alice)
        resp = alice_client.get(f"/api/zk/sessions/join/{part.invite_token}/")
        assert resp.status_code == 410
        session.refresh_from_db()
        assert session.status == "expired"


class TestMyInvites:
    def test_list_my_invites(self, user_factory, client_factory):
        owner = user_factory()
        alice = user_factory()
        ref, _, _ = _register_commitment(owner, "ref-item", "p")
        owner_client = client_factory(owner)
        session = owner_client.post(
            "/api/zk/sessions/",
            {"reference_commitment_id": str(ref.id)},
            format="json",
        ).data
        part = owner_client.post(
            f"/api/zk/sessions/{session['id']}/invite/",
            {"invited_label": "Alice"},
            format="json",
        ).data

        alice_client = client_factory(alice)
        # Before resolve, no bound invites yet.
        resp = alice_client.get("/api/zk/sessions/my-invites/")
        assert resp.status_code == 200
        assert resp.data == []

        alice_client.get(f"/api/zk/sessions/join/{part['invite_token']}/")
        resp = alice_client.get("/api/zk/sessions/my-invites/")
        assert resp.status_code == 200
        assert len(resp.data) == 1
        assert resp.data[0]["session_id"] == session["id"]
