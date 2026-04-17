"""Unit tests for DID, VC issuance, and sign-in primitives.

Covers the flows that must hold for the decentralized identity surface to
be secure:

* Round-trip ``did:key`` creation + public-key recovery.
* Multibase decoding rejects non-Ed25519 identifiers.
* Issuer key creation is idempotent.
* A freshly issued VC JWT verifies with the issuer's public key and fails
  after revocation.
* The sign-in challenge flow consumes a nonce exactly once.
"""

from __future__ import annotations

import base64
import json
from datetime import timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)
from django.contrib.auth import get_user_model
from django.utils import timezone as djtz

from decentralized_identity.models import (
    IssuerKey,
    SignInChallenge,
    UserDID,
    VerifiableCredential,
)
from decentralized_identity.services import (
    did_service,
    issue_credential,
    resolve_did,
    register_user_did,
    verify_sign_in_presentation,
)
from decentralized_identity.services.sign_in_service import create_challenge
from decentralized_identity.services.vc_verifier_service import (
    verify_presentation,
    verify_vc_jwt,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# did:key primitives
# ---------------------------------------------------------------------------


class TestDidKeyPrimitives:
    def test_round_trip_did_key(self):
        priv = Ed25519PrivateKey.generate()
        pub_bytes = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        did = did_service.create_did_key_from_public_key(pub_bytes)
        assert did.startswith("did:key:z")
        recovered = did_service.public_key_from_did_key(did)
        assert recovered == pub_bytes

    def test_multibase_rejects_non_z_prefix(self):
        with pytest.raises(ValueError):
            did_service.multibase_decode("base32encoded")

    def test_did_document_for_did_key_includes_verification_method(self):
        priv = Ed25519PrivateKey.generate()
        pub = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        did = did_service.create_did_key_from_public_key(pub)
        doc = did_service.did_document_for_did_key(did)
        assert doc["id"] == did
        assert len(doc["verificationMethod"]) == 1
        vm = doc["verificationMethod"][0]
        assert vm["type"] == "Ed25519VerificationKey2020"
        assert vm["controller"] == did


# ---------------------------------------------------------------------------
# Issuer key + did:web
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestIssuerKey:
    def test_ensure_issuer_key_is_idempotent(self):
        k1 = did_service.ensure_issuer_key()
        k2 = did_service.ensure_issuer_key()
        assert k1.pk == k2.pk
        assert IssuerKey.objects.filter(is_active=True).count() == 1

    def test_did_web_document_references_kid(self):
        key = did_service.ensure_issuer_key()
        doc = did_service.did_document_for_did_web(key)
        kid = doc["verificationMethod"][0]["id"]
        assert key.kid in kid
        assert doc["verificationMethod"][0]["publicKeyMultibase"] == (
            key.public_key_multibase
        )


# ---------------------------------------------------------------------------
# UserDID registration
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRegisterUserDID:
    def test_register_did_validates_multibase_matches(self):
        user = User.objects.create_user(
            username="diduser", email="d@example.com", password="x"
        )
        priv = Ed25519PrivateKey.generate()
        pub = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        mb = did_service.multibase_encode_ed25519_pub(pub)
        did = "did:key:" + mb

        obj = register_user_did(user, did, mb, make_primary=True)
        assert obj.user == user
        assert obj.did_string == did
        assert obj.is_primary is True

    def test_register_did_rejects_mismatched_multibase(self):
        user = User.objects.create_user(
            username="du2", email="d2@example.com", password="x"
        )
        priv = Ed25519PrivateKey.generate()
        pub = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        other = Ed25519PrivateKey.generate()
        other_pub = other.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        mb_wrong = did_service.multibase_encode_ed25519_pub(other_pub)
        did_good = did_service.create_did_key_from_public_key(pub)
        with pytest.raises(ValueError):
            register_user_did(user, did_good, mb_wrong)


# ---------------------------------------------------------------------------
# VC issuance + verification
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestVCIssueVerifyFlow:
    def test_issue_jwt_vc_signs_with_issuer_key_and_verifies(self):
        did_service.ensure_issuer_key()
        priv = Ed25519PrivateKey.generate()
        pub = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        subject_did = did_service.create_did_key_from_public_key(pub)

        vc = issue_credential(
            subject_did=subject_did,
            schema_id="VaultAccessCredential",
            credential_subject={"tier": "premium"},
            validity_days=30,
        )
        assert vc.status == "active"
        assert vc.jwt_vc.count(".") == 2  # compact JWS

        ok, payload, errors = verify_vc_jwt(vc.jwt_vc)
        assert ok, errors
        assert payload["sub"] == subject_did

    def test_verify_vc_jwt_fails_after_revocation(self):
        did_service.ensure_issuer_key()
        priv = Ed25519PrivateKey.generate()
        pub = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        subject_did = did_service.create_did_key_from_public_key(pub)
        vc = issue_credential(
            subject_did=subject_did,
            schema_id="VaultAccessCredential",
            credential_subject={"tier": "premium"},
            validity_days=30,
        )
        vc.status = "revoked"
        vc.save(update_fields=["status"])
        ok, _payload, errors = verify_vc_jwt(vc.jwt_vc)
        assert ok is False
        assert any("revoked" in e for e in errors)

    def test_verify_vc_jwt_rejects_tampered_signature(self):
        did_service.ensure_issuer_key()
        priv = Ed25519PrivateKey.generate()
        pub = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        subject = did_service.create_did_key_from_public_key(pub)
        vc = issue_credential(
            subject_did=subject,
            schema_id="VaultAccessCredential",
            credential_subject={"tier": "premium"},
        )
        head, body, sig = vc.jwt_vc.split(".")
        # Flip a signature byte
        sig_bytes = bytearray(
            base64.urlsafe_b64decode(sig + "=" * ((4 - len(sig) % 4) % 4))
        )
        sig_bytes[0] ^= 0xFF
        tampered = (
            head
            + "."
            + body
            + "."
            + base64.urlsafe_b64encode(bytes(sig_bytes)).decode("ascii").rstrip("=")
        )
        ok, _payload, errors = verify_vc_jwt(tampered)
        assert ok is False
        assert any("signature" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# Presentation + sign-in
# ---------------------------------------------------------------------------


def _sign_vp(priv: Ed25519PrivateKey, holder_did: str, nonce: str, audience=None):
    """Build a minimal holder-signed VP JWT (no nested VCs)."""
    import json as _json

    def b64u(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")

    def b64uj(obj) -> str:
        return b64u(_json.dumps(obj, separators=(",", ":"), sort_keys=True).encode("utf-8"))

    header = {"alg": "EdDSA", "typ": "JWT"}
    payload = {
        "iss": holder_did,
        "nonce": nonce,
        "vp": {"@context": ["https://www.w3.org/2018/credentials/v1"]},
    }
    if audience is not None:
        payload["aud"] = audience
    signing_input = f"{b64uj(header)}.{b64uj(payload)}".encode("ascii")
    sig = priv.sign(signing_input)
    return signing_input.decode("ascii") + "." + b64u(sig)


@pytest.mark.django_db
class TestSignInFlow:
    def test_challenge_then_verify_ok(self):
        user = User.objects.create_user(
            username="signer", email="s@example.com", password="x"
        )
        priv = Ed25519PrivateKey.generate()
        pub = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        did = did_service.create_did_key_from_public_key(pub)
        mb = did_service.multibase_encode_ed25519_pub(pub)
        register_user_did(user, did, mb)

        challenge = create_challenge(did)
        vp_jwt = _sign_vp(priv, did, challenge.nonce)

        ok, signed_in_user, errors = verify_sign_in_presentation(
            did_string=did, vp_jwt=vp_jwt, expected_nonce=challenge.nonce
        )
        assert ok is True, errors
        assert signed_in_user.pk == user.pk

    def test_replay_is_rejected(self):
        user = User.objects.create_user(
            username="replayer", email="r@example.com", password="x"
        )
        priv = Ed25519PrivateKey.generate()
        pub = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        did = did_service.create_did_key_from_public_key(pub)
        mb = did_service.multibase_encode_ed25519_pub(pub)
        register_user_did(user, did, mb)

        challenge = create_challenge(did)
        vp_jwt = _sign_vp(priv, did, challenge.nonce)

        ok1, _, _ = verify_sign_in_presentation(
            did_string=did, vp_jwt=vp_jwt, expected_nonce=challenge.nonce
        )
        ok2, _, errors = verify_sign_in_presentation(
            did_string=did, vp_jwt=vp_jwt, expected_nonce=challenge.nonce
        )
        assert ok1 is True
        assert ok2 is False
        assert any("consumed" in e.lower() or "expired" in e.lower() for e in errors)

    def test_mismatched_holder_rejected(self):
        user = User.objects.create_user(
            username="mismatch", email="m@example.com", password="x"
        )
        priv = Ed25519PrivateKey.generate()
        other = Ed25519PrivateKey.generate()
        pub = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        did = did_service.create_did_key_from_public_key(pub)
        mb = did_service.multibase_encode_ed25519_pub(pub)
        register_user_did(user, did, mb)

        challenge = create_challenge(did)
        # Sign the VP with the WRONG key.
        vp_jwt = _sign_vp(other, did, challenge.nonce)
        ok, _, errors = verify_sign_in_presentation(
            did_string=did, vp_jwt=vp_jwt, expected_nonce=challenge.nonce
        )
        assert ok is False
        assert any("signature" in e.lower() for e in errors)
