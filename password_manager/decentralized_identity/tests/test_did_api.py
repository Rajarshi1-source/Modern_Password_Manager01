"""Integration tests for decentralized_identity HTTP API."""

from __future__ import annotations

import base64
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from decentralized_identity.models import IssuerKey, UserDID, VerifiableCredential
from decentralized_identity.services import did_service

User = get_user_model()


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64uj(obj) -> str:
    return _b64u(json.dumps(obj, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def _sign_vp(priv: Ed25519PrivateKey, did: str, nonce: str) -> str:
    header = {"alg": "EdDSA", "typ": "JWT"}
    payload = {
        "iss": did,
        "nonce": nonce,
        "vp": {"@context": ["https://www.w3.org/2018/credentials/v1"]},
    }
    signing = f"{_b64uj(header)}.{_b64uj(payload)}".encode("ascii")
    sig = priv.sign(signing)
    return signing.decode("ascii") + "." + _b64u(sig)


@pytest.mark.django_db
class TestDIDRegisterAndResolve(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="u", email="u@e.com", password="TestPassword123!"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        priv = Ed25519PrivateKey.generate()
        pub = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        self.priv = priv
        self.pub = pub
        self.mb = did_service.multibase_encode_ed25519_pub(pub)
        self.did = "did:key:" + self.mb

    def test_register_did_succeeds(self):
        resp = self.client.post(
            "/api/did/register/",
            {
                "did_string": self.did,
                "public_key_multibase": self.mb,
                "make_primary": True,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            UserDID.objects.filter(user=self.user, did_string=self.did).count(), 1
        )

    def test_register_did_rejects_mismatched_multibase(self):
        bad_mb = did_service.multibase_encode_ed25519_pub(
            Ed25519PrivateKey.generate()
            .public_key()
            .public_bytes(Encoding.Raw, PublicFormat.Raw)
        )
        resp = self.client.post(
            "/api/did/register/",
            {"did_string": self.did, "public_key_multibase": bad_mb},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_resolve_did_key_public(self):
        anon = APIClient()
        resp = anon.get(f"/api/did/resolve/{self.did}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["id"], self.did)

    def test_list_mine_empty_then_contains_registered(self):
        resp = self.client.get("/api/did/mine/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json(), [])

        self.client.post(
            "/api/did/register/",
            {"did_string": self.did, "public_key_multibase": self.mb},
            format="json",
        )
        resp = self.client.get("/api/did/mine/")
        self.assertEqual(len(resp.json()), 1)


@pytest.mark.django_db
class TestSignInAPI(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="siu", email="si@e.com", password="TestPassword123!"
        )
        self.priv = Ed25519PrivateKey.generate()
        self.pub = self.priv.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw
        )
        self.mb = did_service.multibase_encode_ed25519_pub(self.pub)
        self.did = "did:key:" + self.mb
        UserDID.objects.create(
            user=self.user, did_string=self.did, public_key_multibase=self.mb
        )

    def test_challenge_then_verify_mints_jwt(self):
        client = APIClient()
        ch_resp = client.post(
            "/api/did/auth/challenge/",
            {"did_string": self.did},
            format="json",
        )
        self.assertEqual(ch_resp.status_code, status.HTTP_200_OK)
        nonce = ch_resp.json()["nonce"]

        vp = _sign_vp(self.priv, self.did, nonce)
        verify = client.post(
            "/api/did/auth/verify/",
            {"did_string": self.did, "nonce": nonce, "vp_jwt": vp},
            format="json",
        )
        self.assertEqual(verify.status_code, status.HTTP_200_OK)
        body = verify.json()
        self.assertTrue(body["verified"])
        self.assertIn("access_token", body)
        self.assertIn("refresh_token", body)
        self.assertEqual(body["user"]["username"], self.user.username)

    def test_verify_fails_on_bad_signature(self):
        client = APIClient()
        ch_resp = client.post(
            "/api/did/auth/challenge/",
            {"did_string": self.did},
            format="json",
        )
        nonce = ch_resp.json()["nonce"]
        other = Ed25519PrivateKey.generate()
        vp = _sign_vp(other, self.did, nonce)
        verify = client.post(
            "/api/did/auth/verify/",
            {"did_string": self.did, "nonce": nonce, "vp_jwt": vp},
            format="json",
        )
        self.assertEqual(verify.status_code, status.HTTP_401_UNAUTHORIZED)


@pytest.mark.django_db
class TestWellKnownDID(TestCase):
    def test_well_known_did_json(self):
        # Ensure an issuer key exists so discovery returns a document.
        did_service.ensure_issuer_key()
        client = APIClient()
        resp = client.get("/.well-known/did.json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json() if hasattr(resp, "json") else json.loads(resp.content)
        self.assertTrue(body["id"].startswith("did:web:"))
        self.assertIn("verificationMethod", body)


@pytest.mark.django_db
class TestVCIssueApi(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin", email="a@e.com", password="x", is_staff=True
        )
        self.subject = User.objects.create_user(
            username="sub", email="sub@e.com", password="x"
        )
        priv = Ed25519PrivateKey.generate()
        pub = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        self.subject_did = did_service.create_did_key_from_public_key(pub)
        self.client = APIClient()

    def test_non_staff_cannot_issue(self):
        non_staff = APIClient()
        non_staff.force_authenticate(user=self.subject)
        resp = non_staff.post(
            "/api/did/credentials/issue/",
            {
                "subject_did": self.subject_did,
                "schema_id": "VaultAccessCredential",
                "credential_subject": {"tier": "premium"},
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_can_issue(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            "/api/did/credentials/issue/",
            {
                "subject_did": self.subject_did,
                "schema_id": "VaultAccessCredential",
                "credential_subject": {"tier": "premium"},
                "validity_days": 30,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        body = resp.json()
        self.assertIn("jwt_vc", body)
        self.assertEqual(
            VerifiableCredential.objects.filter(
                subject_did=self.subject_did
            ).count(),
            1,
        )
