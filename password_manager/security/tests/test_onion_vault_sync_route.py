"""
Contract tests for onion-routed vault sync.

The backend side of this feature was already complete and correct -- what was
missing was a client that used it. These tests exist to make sure the wiring
the new frontend `onionSyncService` depends on cannot silently rot: a rename of
the `vault-sync` URL name, or a tidy-up that drops `vault_sync` from the route
table, would break onion sync in a way no existing test would catch (the proxy
would just start answering `unsupported_operation` and the client would fall
back to clearnet, which for PREFER_ONION users looks like nothing is wrong).
"""

from django.test import TestCase
from django.urls import NoReverseMatch, reverse

from security.services.dark_protocol_service import VAULT_OPERATION_ROUTES


class VaultSyncRouteContractTests(TestCase):
    def test_vault_sync_is_a_routable_proxy_operation(self):
        self.assertIn(
            'vault_sync',
            VAULT_OPERATION_ROUTES,
            'vault_sync dropped from VAULT_OPERATION_ROUTES — onion-routed '
            'sync would start returning unsupported_operation, and '
            'PREFER_ONION clients would silently fall back to clearnet.',
        )

    def test_vault_sync_posts_to_the_vault_sync_route(self):
        route = VAULT_OPERATION_ROUTES['vault_sync']

        # POST, not GET: the sync view reads its payload from the request body.
        self.assertEqual(route['method'], 'POST')
        self.assertEqual(route['route'], 'vault-sync')

    def test_vault_sync_needs_no_object_id(self):
        """Sync is a collection-level operation.

        A stray `needs_id` would make the dispatcher look for an item id the
        sync payload does not carry.
        """
        self.assertFalse(VAULT_OPERATION_ROUTES['vault_sync'].get('needs_id', False))

    def test_the_named_route_actually_reverses(self):
        """The route table names a URL by string; nothing checks it resolves.

        `reverse()` here is the check that the two halves still agree.
        """
        try:
            url = reverse(VAULT_OPERATION_ROUTES['vault_sync']['route'])
        except NoReverseMatch as exc:  # pragma: no cover - failure path
            self.fail(f"vault_sync names a route that does not reverse: {exc}")

        self.assertTrue(url.endswith('/sync/'), url)

    def test_every_declared_route_reverses(self):
        """Guard the whole table, not just the entry this feature needs."""
        for operation, config in VAULT_OPERATION_ROUTES.items():
            with self.subTest(operation=operation):
                kwargs = {'pk': 1} if config.get('needs_id') else {}
                try:
                    reverse(config['route'], kwargs=kwargs)
                except NoReverseMatch as exc:  # pragma: no cover - failure path
                    self.fail(f"{operation} names an unreversible route: {exc}")
