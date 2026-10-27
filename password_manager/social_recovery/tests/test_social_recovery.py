"""Integration tests for the social_recovery app.

These tests exercise the full web-of-trust recovery flow end to end:

* Ed25519 key generation + did:key registration
* Circle creation from shares split and sealed on the owner's device
* Invitation acceptance by Ed25519-signed tokens plus a share proof
* Schnorr equality proof construction and verification at attestation time
* Quorum evaluation, stake commitment / slashing
* Completion releases only shares re-sealed to the requester
* Append-only audit log hash chain
"""
from __future__ import annotations

import base64
import hashlib
import secrets as _secrets
from datetime import timedelta

import pytest

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
)

from decentralized_identity.services.did_service import (
    multibase_encode_ed25519_pub,
)
from zk_proofs.crypto import secp256k1 as ec
from zk_proofs.crypto import schnorr

from social_recovery.models import (
    RecoveryCircle,
    RelationshipCommitment,
    SocialRecoveryAuditLog,
    SocialRecoveryRequest,
    VouchAttestation,
    Voucher,
)
from social_recovery.services import (
    accept_invitation,
    complete_request,
    create_circle,
    initiate_request,
    submit_attestation,
)
from social_recovery.services.recovery_completion_service import (
    cancel_request,
    reject_fraudulent_attestation,
)
from social_recovery.services.web_of_trust_service import evaluate_quorum
from shared.tests import sealed_share_fixtures as fx


User = get_user_model()


def _make_voucher_keypair():
    """Return ``(private_key, public_key_multibase)``."""
    private = Ed25519PrivateKey.generate()
    pub_bytes = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return private, multibase_encode_ed25519_pub(pub_bytes)


def _sign(private_key: Ed25519PrivateKey, message: bytes) -> bytes:
    return private_key.sign(message)


# share proof (base64) per voucher Ed25519 key, as the voucher's device
# would compute it after opening its sealed share
_PROOFS: dict = {}


def _sealed(vouchers):
    """Add what the owner's device sends for each voucher."""
    out = []
    for i, spec in enumerate(vouchers, start=1):
        proof, proof_hash = fx.share_proof()
        _PROOFS[spec["ed25519_public_key"]] = proof
        out.append({
            **spec,
            "hybrid_public_key": base64.b64decode(fx.hybrid_public_key()),
            "share_index": i,
            "sealed_share": base64.b64decode(fx.sealed_share()),
            "share_proof_hash": base64.b64decode(proof_hash),
        })
    return out


def _accept(voucher, private_key):
    return accept_invitation(
        invitation_token=voucher.invitation_token,
        signature=_sign(private_key, voucher.invitation_token.encode("utf-8")),
        share_proof=_PROOFS[voucher.ed25519_public_key],
    )


def _initiate(circle, **kwargs):
    return initiate_request(
        circle=circle,
        requester_public_key=base64.b64decode(fx.hybrid_public_key()),
        **kwargs,
    )


def _approval_message(request, resealed: bytes) -> bytes:
    return (
        f"pwm-social-recovery-v2|{request.request_id}|approve|{request.challenge_nonce}"
        f"|{hashlib.sha256(resealed).hexdigest()}"
    ).encode("utf-8")


def _scalar_from_bytes(blob: bytes) -> int:
    return int.from_bytes(hashlib.sha256(blob).digest(), "big") % ec.N or 1


def _build_equality_proof(voucher_public_key: str, circle_id) -> tuple[bytes, bytes, bytes, bytes]:
    """Produce ``(fresh_commitment_bytes, T, s, stored_commit_bytes)`` for a
    voucher at attestation time.

    The stored blinding factor ``r1`` is deterministically derived from the
    ``salt`` now persisted on the :class:`RelationshipCommitment` row, exactly
    how a real voucher would reconstruct it from their invitation payload.
    """
    m_bytes = f"{voucher_public_key}|{circle_id}".encode("utf-8")
    m_scalar = _scalar_from_bytes(m_bytes)

    rc = (
        RelationshipCommitment.objects.filter(
            voucher__ed25519_public_key=voucher_public_key,
            circle_id=circle_id,
        )
        .select_related("circle")
        .order_by("-commitment_id")
        .first()
    )
    assert rc is not None, "no RelationshipCommitment found for voucher/circle"
    stored_commit_bytes = bytes(rc.pedersen_commitment)
    r1 = _scalar_from_bytes(bytes(rc.salt)) or 1

    salt2 = _secrets.token_bytes(32)
    r2 = _scalar_from_bytes(salt2) or 1
    fresh_point = schnorr.commit(m_scalar, r2)
    fresh_bytes = ec.encode_point(fresh_point)

    stored_point = schnorr.commit(m_scalar, r1)
    T, s = schnorr.prove_equality(fresh_point, stored_point, r2, r1)
    return fresh_bytes, T, s, stored_commit_bytes


@pytest.mark.django_db
class SocialRecoveryFullFlowTests(TestCase):
    """End-to-end test of a successful recovery."""

    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com",
            password="owner-pass-1234",
        )
        self.voucher_users = [
            User.objects.create_user(
                email=f"v{i}@example.com", password="pass-word-1234"
            )
            for i in range(3)
        ]
        self.voucher_keypairs = [_make_voucher_keypair() for _ in range(3)]

    def _build_circle(self, threshold: int = 2):
        vouchers = []
        for i, (private, pub_mb) in enumerate(self.voucher_keypairs):
            vouchers.append(
                {
                    "user": self.voucher_users[i],
                    "ed25519_public_key": pub_mb,
                    "display_name": f"Voucher {i}",
                    "vouch_weight": 2,
                    "stake_amount": 5,
                }
            )
        circle = create_circle(
            user=self.owner,
            secret_check=base64.b64decode(fx.seed_check()),
            threshold=threshold,
            vouchers=_sealed(vouchers),
            min_total_stake=0,
        )
        return None, circle

    def test_schnorr_equality_proof_verifies(self):
        # Both commitments commit to the same scalar but with different
        # blinding factors -> verify_equality must accept.
        m = 123456789
        r1 = 424242
        r2 = 111333
        c1 = schnorr.commit(m, r1)
        c2 = schnorr.commit(m, r2)
        T, s = schnorr.prove_equality(c1, c2, r1, r2)
        assert schnorr.verify_equality(
            ec.encode_point(c1), ec.encode_point(c2), T, s
        )

    def test_schnorr_equality_proof_rejects_tampered(self):
        m = 999
        c1 = schnorr.commit(m, 5)
        c2 = schnorr.commit(m + 1, 7)  # different message -> must fail
        T, s = schnorr.prove_equality(c1, c2, 5, 7)
        assert not schnorr.verify_equality(
            ec.encode_point(c1), ec.encode_point(c2), T, s
        )

    def test_create_circle_stores_the_sealed_shares_as_sent(self):
        _, circle = self._build_circle()
        assert circle.status == "draft"
        assert circle.total_vouchers == 3
        assert circle.vouchers.count() == 3
        assert RelationshipCommitment.objects.filter(circle=circle).count() == 3
        # Each voucher must receive a distinct share index.
        indices = sorted(circle.vouchers.values_list("share_index", flat=True))
        assert indices == [1, 2, 3]
        # No server-side commitment to the seed: the server never had it.
        assert bytes(circle.secret_commitment) == b""
        assert len(bytes(circle.secret_check)) == 32
        for v in circle.vouchers.all():
            assert v.encryption_metadata["algorithm"].startswith("X25519MLKEM768")

    def test_invitation_acceptance_activates_circle(self):
        _, circle = self._build_circle()
        for (private, _pub), voucher in zip(
            self.voucher_keypairs, circle.vouchers.order_by("share_index")
        ):
            accepted = _accept(voucher, private)
            assert accepted.status == "accepted"
        circle.refresh_from_db()
        assert circle.status == "active"

    def test_invitation_acceptance_rejects_bad_signature(self):
        _, circle = self._build_circle()
        voucher = circle.vouchers.first()
        # Signed the wrong message — must reject.
        (private, _pub) = self.voucher_keypairs[0]
        bad_signature = _sign(private, b"not-the-token")
        with pytest.raises(ValueError):
            accept_invitation(
                invitation_token=voucher.invitation_token,
                signature=bad_signature,
                share_proof=_PROOFS[voucher.ed25519_public_key],
            )

    def test_invitation_acceptance_requires_the_share_proof(self):
        _, circle = self._build_circle()
        voucher = circle.vouchers.order_by("share_index").first()
        private, _pub = self.voucher_keypairs[0]
        signature = _sign(private, voucher.invitation_token.encode("utf-8"))
        for proof in ("", fx.share_proof()[0], _PROOFS[self.voucher_keypairs[1][1]]):
            with pytest.raises(ValueError):
                accept_invitation(
                    invitation_token=voucher.invitation_token,
                    signature=signature,
                    share_proof=proof,
                )
        voucher.refresh_from_db()
        assert voucher.status == "pending"

    def test_attestation_rejects_without_zk_proof_on_approve(self):
        _, circle = self._build_circle()
        # accept all invites
        for (private, _pub), voucher in zip(
            self.voucher_keypairs, circle.vouchers.order_by("share_index")
        ):
            _accept(voucher, private)
        circle.refresh_from_db()
        request = _initiate(circle, initiator_email="x@example.com")
        voucher = circle.vouchers.order_by("share_index").first()
        private, _pub = self.voucher_keypairs[0]
        resealed = base64.b64decode(fx.sealed_share())
        with pytest.raises(ValueError):
            submit_attestation(
                request=request,
                voucher=voucher,
                decision="approve",
                signature=_sign(private, _approval_message(request, resealed)),
                resealed_share=resealed,
            )

    def test_approval_requires_a_resealed_share_its_signature_covers(self):
        _, circle = self._build_circle()
        for (private, _pub), voucher in zip(
            self.voucher_keypairs, circle.vouchers.order_by("share_index")
        ):
            _accept(voucher, private)
        circle.refresh_from_db()
        request = _initiate(circle)
        voucher = circle.vouchers.order_by("share_index").first()
        private, _pub = self.voucher_keypairs[0]
        fresh, T, s, _ = _build_equality_proof(voucher.ed25519_public_key, voucher.circle_id)
        resealed = base64.b64decode(fx.sealed_share())
        proof = dict(fresh_commitment=fresh, proof_T=T, proof_s=s)
        # No re-sealed share: refused.
        with pytest.raises(ValueError):
            submit_attestation(request=request, voucher=voucher, decision="approve",
                               signature=_sign(private, _approval_message(request, b"")),
                               **proof)
        # A share swapped after signing: refused.
        with pytest.raises(ValueError):
            submit_attestation(request=request, voucher=voucher, decision="approve",
                               signature=_sign(private, _approval_message(request, resealed)),
                               resealed_share=base64.b64decode(fx.sealed_share()), **proof)
        att = submit_attestation(request=request, voucher=voucher, decision="approve",
                                 signature=_sign(private, _approval_message(request, resealed)),
                                 resealed_share=resealed, **proof)
        assert bytes(att.resealed_share) == resealed


@pytest.mark.django_db
class QuorumAndStakeTests(TestCase):
    """Focused tests of quorum evaluation and stake commitment."""

    def setUp(self):
        self.owner = User.objects.create_user(
            email="qowner@example.com", password="x-pass-1234"
        )
        self.voucher_users = [
            User.objects.create_user(email=f"qv{i}@example.com", password="x-pass-1234")
            for i in range(3)
        ]
        self.voucher_keypairs = [_make_voucher_keypair() for _ in range(3)]

        vouchers = [
            {
                "user": self.voucher_users[i],
                "ed25519_public_key": self.voucher_keypairs[i][1],
                "vouch_weight": 1,
                "stake_amount": 10,
            }
            for i in range(3)
        ]
        self.circle = create_circle(
            user=self.owner,
            secret_check=base64.b64decode(fx.seed_check()),
            threshold=2,
            vouchers=_sealed(vouchers),
            min_total_stake=15,
        )
        for (private, _), voucher in zip(
            self.voucher_keypairs, self.circle.vouchers.order_by("share_index")
        ):
            _accept(voucher, private)
        self.circle.refresh_from_db()

    def _submit_approval(self, request, voucher, private_key, stake=8, resealed=None):
        resealed = resealed or base64.b64decode(fx.sealed_share())
        signed_message = _approval_message(request, resealed)
        fresh_bytes, T, s, _stored = _build_equality_proof(
            voucher.ed25519_public_key, voucher.circle_id
        )

        return submit_attestation(
            request=request,
            voucher=voucher,
            decision="approve",
            signature=_sign(private_key, signed_message),
            fresh_commitment=fresh_bytes,
            proof_T=T,
            proof_s=s,
            resealed_share=resealed,
            stake_amount=stake,
        )

    def test_quorum_satisfied_once_threshold_reached(self):
        request = _initiate(self.circle)
        vouchers = list(self.circle.vouchers.order_by("share_index"))
        self._submit_approval(request, vouchers[0], self.voucher_keypairs[0][0])
        request.refresh_from_db()
        assert request.status == "pending"  # threshold not met yet
        self._submit_approval(request, vouchers[1], self.voucher_keypairs[1][0])
        request.refresh_from_db()
        q = evaluate_quorum(request)
        assert q.approve_count >= 2
        assert q.satisfies_count
        assert request.status in ("approved", "pending")  # updated within call
        assert evaluate_quorum(request).quorum_met

    def test_stake_slash_on_cancel(self):
        request = _initiate(self.circle)
        vouchers = list(self.circle.vouchers.order_by("share_index"))
        self._submit_approval(request, vouchers[0], self.voucher_keypairs[0][0], stake=10)
        self._submit_approval(request, vouchers[1], self.voucher_keypairs[1][0], stake=10)
        request.refresh_from_db()
        cancel_request(request=request, slash_denies=True)
        request.refresh_from_db()
        assert request.status == "cancelled"

    def test_completion_keeps_approver_stakes_committed(self):
        from password_reputation.models import ReputationEvent
        request = _initiate(self.circle)
        vouchers = list(self.circle.vouchers.order_by("share_index"))
        for v, (private, _) in list(zip(vouchers, self.voucher_keypairs))[:2]:
            self._submit_approval(request, v, private, stake=8)
        request.refresh_from_db()
        complete_request(request=request)
        # The server cannot verify the re-sealed shares, so completing
        # releases nothing; a fraudulent approval can still be slashed.
        notes = ReputationEvent.objects.filter(note__contains=str(request.request_id)).values_list("note", flat=True)
        self.assertFalse([n for n in notes if "|release|" in n])
        self.assertEqual(len([n for n in notes if "|commit|" in n]), 2)

    def test_complete_request_returns_only_the_resealed_shares(self):
        request = _initiate(self.circle)
        vouchers = list(self.circle.vouchers.order_by("share_index"))
        with pytest.raises(ValueError):
            complete_request(request=request)  # not approved yet
        resealed = [base64.b64decode(fx.sealed_share()) for _ in range(2)]
        for v, (private, _), r in zip(vouchers, self.voucher_keypairs, resealed):
            self._submit_approval(request, v, private, resealed=r)
        request.refresh_from_db()
        assert request.status == "approved"

        result = complete_request(request=request)
        assert result["threshold"] == 2
        assert base64.b64decode(result["secret_check"]) == bytes(self.circle.secret_check)
        assert [base64.b64decode(x["sealed_share"]) for x in result["sealed_shares"]] == resealed
        assert [x["share_index"] for x in result["sealed_shares"]] == [1, 2]
        # The server holds no share or secret to return.
        assert "secret_hex" not in result
        request.refresh_from_db()
        assert request.status == "completed"
        # Completing again returns the same shares.
        assert complete_request(request=request)["sealed_shares"] == result["sealed_shares"]


@pytest.mark.django_db
class AuditLogHashChainTests(TestCase):
    def test_audit_chain_is_hash_linked(self):
        owner = User.objects.create_user(
            email="audit@example.com", password="x-pass-1234"
        )
        vouchers = [
            User.objects.create_user(email=f"a{i}@example.com", password="x-pass-1234")
            for i in range(3)
        ]
        kp = [_make_voucher_keypair() for _ in range(3)]
        circle = create_circle(
            user=owner,
            secret_check=base64.b64decode(fx.seed_check()),
            threshold=2,
            vouchers=_sealed([
                {
                    "user": vouchers[i],
                    "ed25519_public_key": kp[i][1],
                    "vouch_weight": 1,
                    "stake_amount": 0,
                }
                for i in range(3)
            ]),
        )
        # Accept one voucher so we append another audit entry.
        v = circle.vouchers.order_by("share_index").first()
        _accept(v, kp[0][0])
        entries = list(
            SocialRecoveryAuditLog.objects.all().order_by("created_at")
        )
        assert len(entries) >= 2
        # Every row after the first must reference the previous entry's hash.
        for prev, current in zip(entries, entries[1:]):
            assert bytes(current.prev_hash) == bytes(prev.entry_hash)
        # Forgery must be detectable: compute expected hash and ensure it
        # matches the persisted one.
        for prev_hash, entry in zip(
            [b""] + [bytes(e.entry_hash) for e in entries[:-1]], entries
        ):
            expected = SocialRecoveryAuditLog.compute_entry_hash(
                prev_hash=prev_hash,
                user_id=entry.user_id,
                circle_id=entry.circle.circle_id if entry.circle_id else None,
                event_type=entry.event_type,
                event_data=entry.event_data or {},
                created_at_iso=entry.created_at.isoformat(),
            )
            assert bytes(entry.entry_hash) == expected


@pytest.mark.django_db
class StakeSlashTests(TestCase):
    def test_reject_fraudulent_attestation_records_slash_event(self):
        owner = User.objects.create_user(
            email="frauds@example.com", password="x-pass-1234"
        )
        voucher_user = User.objects.create_user(
            email="fraudv@example.com", password="x-pass-1234"
        )
        kp = _make_voucher_keypair()
        circle = create_circle(
            user=owner,
            secret_check=base64.b64decode(fx.seed_check()),
            threshold=2,
            vouchers=_sealed([
                {
                    "user": voucher_user,
                    "ed25519_public_key": kp[1],
                    "vouch_weight": 1,
                    "stake_amount": 5,
                },
                {
                    "user": None,
                    "did_string": "did:key:zFakeMallory",
                    "ed25519_public_key": _make_voucher_keypair()[1],
                    "vouch_weight": 1,
                    "stake_amount": 5,
                },
            ]),
        )
        voucher = circle.vouchers.get(user=voucher_user)
        # Skip full flow; fabricate a request + attestation.
        request = SocialRecoveryRequest.objects.create(
            circle=circle,
            required_approvals=2,
            challenge_nonce="abc",
            expires_at=timezone.now() + timedelta(days=1),
        )
        VouchAttestation.objects.create(
            request=request,
            voucher=voucher,
            ed25519_signature=b"x",
            signed_message=b"y",
            decision="approve",
            stake_committed=5,
        )
        from password_reputation.models import ReputationAccount

        ReputationAccount.objects.get_or_create(user=voucher_user, defaults={"score": 10})
        reject_fraudulent_attestation(
            voucher=voucher, request=request, reason="unit-test"
        )
        assert SocialRecoveryAuditLog.objects.filter(event_type="stake_slashed").exists()
