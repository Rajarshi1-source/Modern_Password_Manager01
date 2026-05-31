"""
Audit Group C / finding #6 (2026-05): the decoy vault must never read
real secrets from the environment.

``DecoyVaultService`` builds the fake vault an attacker sees after a
duress-code trigger. The ``API Keys`` decoy note previously fell back to
``os.getenv('STRIPE_API_KEY', ...)`` / ``STRIPE_STAGING_KEY`` — so on a
deployment that actually sets those env vars, the decoy screen designed
to deceive the attacker would instead hand them the real production
Stripe keys. The values must be hardcoded fakes.
"""

import os
from unittest import mock

from django.test import SimpleTestCase

from security.services.decoy_vault_service import DecoyVaultService


class DecoyApiKeyNoteTests(SimpleTestCase):
    def setUp(self):
        self.service = DecoyVaultService()

    def test_api_keys_note_does_not_read_env(self):
        # Even with real-looking Stripe keys in the environment, the
        # decoy note must contain only the hardcoded placeholders.
        sentinel_prod = 'REAL-PROD-KEY-SHOULD-NOT-LEAK'
        sentinel_staging = 'REAL-STAGING-KEY-SHOULD-NOT-LEAK'
        with mock.patch.dict(os.environ, {
            'STRIPE_API_KEY': sentinel_prod,
            'STRIPE_STAGING_KEY': sentinel_staging,
        }):
            note = self.service._generate_fake_note_content('API Keys')

        self.assertNotIn(sentinel_prod, note)
        self.assertNotIn(sentinel_staging, note)
        self.assertIn('STRIPE-PLACEHOLDER-PROD-1', note)
        self.assertIn('STRIPE-PLACEHOLDER-STAGING-1', note)

    def test_api_keys_note_is_constant_regardless_of_env(self):
        # The note is identical whether or not the env vars are set.
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop('STRIPE_API_KEY', None)
            os.environ.pop('STRIPE_STAGING_KEY', None)
            without_env = self.service._generate_fake_note_content('API Keys')
        with mock.patch.dict(os.environ, {
            'STRIPE_API_KEY': 'x',
            'STRIPE_STAGING_KEY': 'y',
        }):
            with_env = self.service._generate_fake_note_content('API Keys')
        self.assertEqual(without_env, with_env)
