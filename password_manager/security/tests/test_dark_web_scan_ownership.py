"""
Phase E / E2 (2026-05): regression tests for the scan-task ownership
check in ``DarkWebViewSet``.

Before E2, ``scan_status`` blindly trusted any ``task_id`` query
parameter and pulled the result from Celery's result backend. An
authenticated user holding another user's leaked task_id (frontend
telemetry, browser history, server logs) could read the breach-scan
result that belonged to someone else — a classic IDOR.

These tests confirm:
  * scan_vault stores ``scan_task_owner:<id>`` in the cache with the
    submitter's user id.
  * scan_status returns 404 (not 403) for task_ids the cache doesn't
    attribute to the requesting user.
  * scan_status returns 404 for unknown task_ids too — so an attacker
    can't enumerate valid task_ids via 404-vs-403 side channel.

Tests mock ``scan_user_vault.delay`` and ``scan_user_vault.AsyncResult``
so the cache logic is exercised without standing up a Celery worker.
"""

from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

User = get_user_model()


# URL paths are hard-coded rather than ``reverse()``'d because the
# router-action URL-name format isn't worth a second test setup. The
# `dark-web` viewset is registered at ``/api/security/dark-web/`` in
# ``security/urls.py:44``; the ``@action`` decorators expose
# ``scan_vault`` and ``scan_status`` under their method names with
# underscores preserved.
_SCAN_VAULT_URL = '/api/security/dark-web/scan_vault/'
_SCAN_STATUS_URL = '/api/security/dark-web/scan_status/'


class _FakeAsyncResult:
    """Stand-in for ``celery.AsyncResult`` — all tests want either
    'SUCCESS' or 'PENDING' without touching Redis."""

    def __init__(self, task_id, *, state='PENDING', result=None):
        self.id = task_id
        self.state = state
        self.result = result


class DarkWebScanOwnershipTests(APITestCase):

    def setUp(self):
        cache.clear()
        self.user_a = User.objects.create_user(
            username='userA', email='a@example.com', password='pw-a-1234',
        )
        self.user_b = User.objects.create_user(
            username='userB', email='b@example.com', password='pw-b-1234',
        )
        self.client = APIClient()

    @mock.patch('security.api.darkWebEndpoints.scan_user_vault')
    def test_scan_vault_records_owner_in_cache(self, mock_task):
        """POST scan_vault → cache[scan_task_owner:<task_id>] = user.id."""
        fake_task = mock.MagicMock()
        fake_task.id = 'task-abc-123'
        mock_task.delay.return_value = fake_task

        self.client.force_authenticate(user=self.user_a)
        response = self.client.post(_SCAN_VAULT_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['task_id'], 'task-abc-123')
        self.assertEqual(
            cache.get('scan_task_owner:task-abc-123'),
            self.user_a.id,
        )

    @mock.patch('security.api.darkWebEndpoints.scan_user_vault')
    def test_scan_status_owner_can_read_result(self, mock_task):
        """Sanity: the task's owner gets the result back."""
        cache.set('scan_task_owner:owned-task-1', self.user_a.id, timeout=60)
        mock_task.AsyncResult.return_value = _FakeAsyncResult(
            'owned-task-1', state='SUCCESS', result={'breaches': []},
        )

        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(
            _SCAN_STATUS_URL, {'task_id': 'owned-task-1'},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'completed')

    @mock.patch('security.api.darkWebEndpoints.scan_user_vault')
    def test_scan_status_rejects_other_users_task_id(self, mock_task):
        """The IDOR fix: user B cannot read user A's scan result via
        a leaked task_id."""
        cache.set('scan_task_owner:owned-task-2', self.user_a.id, timeout=60)
        # AsyncResult MUST NOT be called when ownership fails — but if
        # the bug ever regresses, having it ready returns a SUCCESS
        # payload that would make the failure obvious.
        mock_task.AsyncResult.return_value = _FakeAsyncResult(
            'owned-task-2', state='SUCCESS', result={'breaches': ['leaked']},
        )

        self.client.force_authenticate(user=self.user_b)
        response = self.client.get(
            _SCAN_STATUS_URL, {'task_id': 'owned-task-2'},
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        # Confirm the AsyncResult lookup never happened — the cache
        # check should short-circuit before any Celery state is read.
        mock_task.AsyncResult.assert_not_called()

    @mock.patch('security.api.darkWebEndpoints.scan_user_vault')
    def test_scan_status_returns_404_for_unknown_task_id(self, mock_task):
        """An attacker probing valid-vs-invalid task_ids must see the
        same 404 for "not yours" and "doesn't exist" — otherwise the
        status code becomes an enumeration side channel."""
        # Cache is empty — no owner record for this task_id.
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(
            _SCAN_STATUS_URL,
            {'task_id': 'made-up-task-id-9999'},
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        mock_task.AsyncResult.assert_not_called()

    def test_scan_status_requires_task_id_param(self):
        """Pre-E2 behaviour preserved: missing task_id → 400."""
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(_SCAN_STATUS_URL)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
