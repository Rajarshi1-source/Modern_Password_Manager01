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
from django.urls import NoReverseMatch, resolve, reverse

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

        # The assertions above only check VAULT_OPERATION_ROUTES' OWN
        # metadata -- self-consistency, not reality. If `vault/urls.py`'s
        # `path('sync/', CrudVaultItemViewSet.as_view({'post': 'sync'}), ...)`
        # ever changed which HTTP method maps to `sync` without this dict
        # being updated to match, this test would still pass while the
        # actual onion-routed sync request got a 405. Resolve the real URL
        # and inspect the DRF ViewSet's own action mapping instead of
        # trusting the registry a second time -- `ViewSetMixin.as_view()`
        # attaches the exact `{method: action}` dict it was built from as
        # `view.actions`, a stable DRF introspection API (confirmed against
        # the installed `rest_framework.viewsets` source).
        resolved = resolve(reverse(route['route']))
        self.assertEqual(resolved.func.actions.get('post'), 'sync')

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

        # Full path, not just the trailing segment: `/sync/` alone would
        # still pass if `vault-sync` ever pointed at some other app's
        # same-named endpoint, which defeats the point of this contract test
        # (confirmed against the actual mount chain: password_manager/urls.py
        # -> api/urls.py `vault/` -> vault/urls.py `sync/`).
        self.assertTrue(url.endswith('/api/vault/sync/'), url)

    def test_every_declared_route_reverses(self):
        """Guard the whole table, not just the entry this feature needs.

        Reverses id-bearing routes positionally (`args=`), matching exactly
        how `_dispatch_vault_operation` itself calls `reverse()`
        (`dark_protocol_service.py`) rather than a `pk` kwarg: the two forms
        only agree while every id-bearing pattern's capture group happens to
        be named `pk`. A `kwargs={'pk': ...}` call would raise
        `NoReverseMatch` here on a pattern that renamed its capture group
        while production, calling positionally, kept working -- a false
        failure pointing at the wrong cause.
        """
        for operation, config in VAULT_OPERATION_ROUTES.items():
            with self.subTest(operation=operation):
                args = ['1'] if config.get('needs_id') else []
                try:
                    reverse(config['route'], args=args)
                except NoReverseMatch as exc:  # pragma: no cover - failure path
                    self.fail(f"{operation} names an unreversible route: {exc}")
