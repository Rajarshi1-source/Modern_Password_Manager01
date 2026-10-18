"""
The server-side /api/kyber KEM endpoints are retired (410): they kept users'
KEM private keys unwrapped on the server, accepted vault plaintext and even a
client's private key, and decrypted server-side, which breaks the
zero-knowledge model. (They were also unreachable: async views under DRF's
@api_view always returned 500.)
"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from auth_module.models import KyberKeyPair

RETIRED = (
    'kyber_generate_keypair', 'kyber_batch_keygen',
    'kyber_encrypt', 'kyber_decrypt', 'kyber_batch_encrypt',
)


class RetiredServerSideKemTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('kem-user', 'kem@example.com', 'Kem-User-Pass-1!')
        self.client = APIClient()

    def test_retired_endpoints_return_410_and_store_nothing(self):
        self.client.force_authenticate(self.user)
        for name in RETIRED:
            response = self.client.post(
                reverse(name),
                {'plaintext': 'vault-secret', 'private_key': 'AAAA', 'count': 1},
                format='json',
            )
            self.assertEqual(response.status_code, 410, name)
            self.assertEqual(response.json()['code'], 'server_side_kem_retired')
        self.assertFalse(KyberKeyPair.objects.exists())

    def test_retired_endpoints_still_require_authentication(self):
        for name in RETIRED:
            self.assertIn(self.client.post(reverse(name), {}, format='json').status_code, (401, 403))

    def test_status_endpoint_still_works(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(reverse('kyber_status'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['crypto_status']['algorithm'], 'ML-KEM-768')
