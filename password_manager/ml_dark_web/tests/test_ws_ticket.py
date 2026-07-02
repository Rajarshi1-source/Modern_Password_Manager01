"""
WebSocket auth ticket flow (Issue A: keep the long-lived token out of ws:// URLs).

Covers:
  * ws_ticket.issue_ticket / consume_ticket — single-use + miss.
  * POST /api/auth/ws-ticket/ — auth required; returns a ticket that resolves
    back to the caller.
  * TokenAuthMiddleware — ticket resolves to the user and is single-use; the
    ?token= path still authenticates (backward-compatible fallback); a request
    with neither is AnonymousUser.
"""
from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from ml_dark_web.middleware import TokenAuthMiddleware
from ml_dark_web.ws_ticket import consume_ticket, issue_ticket

User = get_user_model()


async def _noop_receive():
    return {'type': 'websocket.connect'}


async def _noop_send(message):
    return None


class WsTicketUtilTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username='bob', email='bob@example.com', password='pw1234pw1234'
        )

    def test_issue_then_consume_returns_user_id(self):
        ticket = issue_ticket(self.user.id)
        self.assertEqual(consume_ticket(ticket), self.user.id)

    def test_ticket_is_single_use(self):
        ticket = issue_ticket(self.user.id)
        self.assertEqual(consume_ticket(ticket), self.user.id)
        self.assertIsNone(consume_ticket(ticket))  # replay finds nothing

    def test_missing_ticket_returns_none(self):
        self.assertIsNone(consume_ticket('does-not-exist'))
        self.assertIsNone(consume_ticket(''))
        self.assertIsNone(consume_ticket(None))


class WsTicketEndpointTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username='carol', email='carol@example.com', password='pw1234pw1234'
        )

    def test_requires_authentication(self):
        resp = APIClient().post(reverse('ws-ticket'))
        self.assertIn(resp.status_code, (401, 403))

    def test_authenticated_returns_usable_ticket(self):
        client = APIClient()
        client.force_authenticate(user=self.user)
        resp = client.post(reverse('ws-ticket'))
        self.assertEqual(resp.status_code, 200)
        ticket = resp.data['ticket']
        self.assertTrue(ticket)
        # The issued ticket resolves back to the caller (and is consumed).
        self.assertEqual(consume_ticket(ticket), self.user.id)

    def test_drf_token_authorization_header_is_accepted(self):
        # The SPA api client sends "Authorization: Token <key>"; the DRF default
        # is JWT-only, so the endpoint must opt into TokenAuthentication or this
        # regresses to 401 (force_authenticate above bypasses auth classes).
        token = Token.objects.create(user=self.user)
        resp = APIClient().post(
            reverse('ws-ticket'), HTTP_AUTHORIZATION=f'Token {token.key}'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['ticket'])


class WsTicketMiddlewareTests(TransactionTestCase):
    # TransactionTestCase: get_user_from_* runs in a database_sync_to_async
    # thread whose connection must see the committed test user.
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username='dave', email='dave@example.com', password='pw1234pw1234'
        )
        self.mw = TokenAuthMiddleware(self._capture)
        self.captured = {}

    async def _capture(self, scope, receive, send):
        self.captured['user'] = scope['user']

    def test_ticket_resolves_to_user_and_is_single_use(self):
        ticket = issue_ticket(self.user.id)
        self.assertEqual(async_to_sync(self.mw.get_user_from_ticket)(ticket), self.user)
        # Consumed — a replay is anonymous.
        self.assertTrue(async_to_sync(self.mw.get_user_from_ticket)(ticket).is_anonymous)

    def test_invalid_ticket_is_anonymous(self):
        self.assertTrue(async_to_sync(self.mw.get_user_from_ticket)('bogus').is_anonymous)

    def test_token_fallback_still_authenticates(self):
        token = Token.objects.create(user=self.user)
        self.assertEqual(async_to_sync(self.mw.get_user_from_token)(token.key), self.user)

    def test_call_routes_ticket_to_scope_user(self):
        ticket = issue_ticket(self.user.id)
        scope = {'type': 'websocket', 'query_string': f'ticket={ticket}'.encode()}
        async_to_sync(self.mw)(scope, _noop_receive, _noop_send)
        self.assertEqual(self.captured['user'], self.user)

    def test_call_without_credentials_is_anonymous(self):
        scope = {'type': 'websocket', 'query_string': b''}
        async_to_sync(self.mw)(scope, _noop_receive, _noop_send)
        self.assertTrue(self.captured['user'].is_anonymous)
