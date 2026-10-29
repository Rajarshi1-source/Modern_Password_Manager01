"""Social recovery API with shares split and sealed on the owner's device.

``POST /circles/`` used to take ``master_secret_hex`` in clear and split it on
the server, and ``/complete/`` returned ``secret_hex``. The server now gets
sealed shares and a seed check only (shared/sealed_shares.py).
"""
from __future__ import annotations

import base64

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from decentralized_identity.services.did_service import multibase_encode_ed25519_pub
from shared.tests import sealed_share_fixtures as fx
from social_recovery.models import RecoveryCircle, Voucher

User = get_user_model()


def _ed25519():
    key = Ed25519PrivateKey.generate()
    pub = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return key, multibase_encode_ed25519_pub(pub)


class ClientSealedCircleApiTests(TestCase):
    def setUp(self):
        cache.clear()
        # force_authenticate below: the account needs no usable password
        self.owner = User.objects.create_user(username="owner", email="owner@example.com")
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.keys = [_ed25519() for _ in range(3)]
        self.proofs = []
        self.vouchers = []
        for i, (_, pub) in enumerate(self.keys, start=1):
            proof, proof_hash = fx.share_proof()
            self.proofs.append(proof)
            self.vouchers.append({
                "email": f"v{i}@example.com", "ed25519_public_key": pub,
                "hybrid_public_key": fx.hybrid_public_key(), "share_index": i,
                "sealed_share": fx.sealed_share(), "share_proof_hash": proof_hash,
            })

    def _create(self, **extra):
        body = {"threshold": 2, "secret_check": fx.seed_check(), "vouchers": self.vouchers}
        body.update(extra)
        return self.client.post("/api/social-recovery/circles/", body, format="json")

    def test_a_secret_in_clear_is_refused(self):
        r = self._create(master_secret_hex="ab" * 32)
        self.assertEqual(r.status_code, 400, r.content)
        self.assertFalse(RecoveryCircle.objects.exists())

    def test_vouchers_without_sealed_shares_are_refused(self):
        original = dict(self.vouchers[0])
        for field, bad in (("hybrid_public_key", fx.b64(b"\x01" * 32)),
                           ("sealed_share", fx.b64(b"\x01" * 64)),
                           ("share_proof_hash", "")):
            self.vouchers[0] = {**original, field: bad}
            r = self._create()
            self.assertEqual(r.status_code, 400, (field, r.content))
        self.assertFalse(RecoveryCircle.objects.exists())

    def test_one_guardian_key_for_two_vouchers_is_refused(self):
        # Its holder could open both shares and meet a threshold of two alone.
        self.vouchers[1] = {**self.vouchers[1],
                            "hybrid_public_key": self.vouchers[0]["hybrid_public_key"]}
        r = self._create()
        self.assertEqual(r.status_code, 400, r.content)
        self.assertFalse(RecoveryCircle.objects.exists())

    def test_the_sealed_shares_are_stored_as_sent(self):
        r = self._create()
        self.assertEqual(r.status_code, 201, r.content)
        for spec in self.vouchers:
            v = Voucher.objects.get(share_index=spec["share_index"])
            self.assertEqual(bytes(v.encrypted_shard_data), base64.b64decode(spec["sealed_share"]))
            self.assertEqual(bytes(v.hybrid_public_key), base64.b64decode(spec["hybrid_public_key"]))

    def test_a_voucher_fetches_its_sealed_share_and_accepts_with_the_proof(self):
        self.assertEqual(self._create().status_code, 201)
        anon = APIClient()
        voucher = Voucher.objects.get(share_index=1)
        url = f"/api/social-recovery/vouchers/{voucher.invitation_token}/accept/"
        r = anon.get(url)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["sealed_share"], self.vouchers[0]["sealed_share"])
        signature = base64.b64encode(
            self.keys[0][0].sign(voucher.invitation_token.encode())).decode()
        r = anon.post(url, {"signature_b64": signature}, format="json")
        self.assertEqual(r.status_code, 400, r.content)
        r = anon.post(url, {"signature_b64": signature, "share_proof": self.proofs[1]}, format="json")
        self.assertEqual(r.status_code, 400, r.content)
        r = anon.post(url, {"signature_b64": signature, "share_proof": self.proofs[0]}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["status"], "accepted")

    def test_a_recovery_request_needs_the_requesters_key(self):
        self.assertEqual(self._create().status_code, 201)
        circle = RecoveryCircle.objects.get()
        circle.status = "active"
        circle.save()
        anon = APIClient()
        r = anon.post("/api/social-recovery/requests/", {"circle_id": str(circle.circle_id)},
                      format="json")
        self.assertEqual(r.status_code, 400, r.content)
        key = fx.hybrid_public_key()
        r = anon.post("/api/social-recovery/requests/", {
            "circle_id": str(circle.circle_id), "requester_public_key": key}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        # Guardians read the key from the request to re-seal their shares.
        r = anon.get(f"/api/social-recovery/requests/{r.json()['request_id']}/")
        self.assertEqual(r.json()["requester_public_key"], key)
