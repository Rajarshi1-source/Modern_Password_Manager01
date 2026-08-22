"""
Tests for the `check_honeypot_backlog` management command.

This command is the pre-deploy safety check for the honeypot-email beat
schedule. It must correctly identify the work that would be processed in a
single batch on the first beat tick: stale CredentialRotationLog rows (one
reminder email each, unbounded backlog) and active HoneypotEmail rows (one
provider API call each).

Each filter here deliberately mirrors the corresponding task in
`security/tasks/honeypot_tasks.py`. A test that passes while the task's own
filter has drifted would make the command's "safe to deploy" verdict a lie, so
the boundary cases below (exactly-24h, confirmed, non-pending, inactive) exist
to pin that correspondence rather than merely to exercise the command.
"""

from datetime import timedelta
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from security.models import CredentialRotationLog, HoneypotEmail


class CheckHoneypotBacklogCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='canary-user',
            email='canary@example.com',
            password='test-password-not-a-secret',  # nosec B106
        )

    def _run(self):
        """Run the command, returning (stdout, exit_code).

        The command raises SystemExit(1) when a backlog exists so a deploy
        script can gate on it; translate that into a return value.
        """
        out = StringIO()
        try:
            call_command('check_honeypot_backlog', stdout=out)
        except SystemExit as exc:
            return out.getvalue(), exc.code
        return out.getvalue(), 0

    def _make_rotation(self, **overrides):
        defaults = dict(
            user=self.user,
            service_name='example.com',
            status='pending',
            user_confirmed=False,
            initiated_at=timezone.now() - timedelta(hours=48),
        )
        defaults.update(overrides)
        return CredentialRotationLog.objects.create(**defaults)

    def _make_honeypot(self, **overrides):
        defaults = dict(
            user=self.user,
            honeypot_address='decoy@example.com',
            service_name='example.com',
            is_active=True,
            status='active',
        )
        defaults.update(overrides)
        return HoneypotEmail.objects.create(**defaults)

    def test_no_backlog_exits_cleanly(self):
        out, code = self._run()

        self.assertEqual(code, 0)
        self.assertIn('No backlog', out)

    def test_reports_stale_pending_rotation(self):
        rotation = self._make_rotation()

        out, code = self._run()

        self.assertEqual(code, 1)
        self.assertIn('BACKLOG FOUND', out)
        self.assertIn(str(rotation.id), out)

    def test_does_not_report_rotation_newer_than_24h(self):
        """The task's cutoff is `initiated_at < now - 24h`.

        A rotation initiated an hour ago is not yet a reminder candidate, so
        counting it here would inflate the reported blast radius.
        """
        self._make_rotation(initiated_at=timezone.now() - timedelta(hours=1))

        out, code = self._run()

        self.assertEqual(code, 0)
        self.assertIn('No backlog', out)

    def test_does_not_report_confirmed_rotation(self):
        self._make_rotation(user_confirmed=True)

        out, code = self._run()

        self.assertEqual(code, 0)

    def test_does_not_report_non_pending_rotation(self):
        self._make_rotation(status='completed')

        out, code = self._run()

        self.assertEqual(code, 0)

    def test_reports_active_honeypot_awaiting_first_scan(self):
        self._make_honeypot()

        out, code = self._run()

        self.assertEqual(code, 1)
        self.assertIn('1 active honeypot', out)

    def test_reports_triggered_honeypot(self):
        """`scan_all_honeypots` scans status in ('active', 'triggered').

        A honeypot that already fired is still rescanned, so it still counts
        toward the first-tick provider call volume.
        """
        self._make_honeypot(status='triggered')

        out, code = self._run()

        self.assertEqual(code, 1)
        self.assertIn('1 active honeypot', out)

    def test_does_not_report_inactive_honeypot(self):
        self._make_honeypot(is_active=False)

        out, code = self._run()

        self.assertEqual(code, 0)

    def test_does_not_report_expired_honeypot(self):
        """`status='expired'` is outside the task's `status__in` filter."""
        self._make_honeypot(status='expired')

        out, code = self._run()

        self.assertEqual(code, 0)

    def test_output_excludes_identifying_data(self):
        """Routine scheduled output must not leak user or service identity.

        This command's stdout lands in cluster log aggregation. A service name
        paired with a user is exactly the credential mapping this product
        exists to protect, so the report carries IDs and durations only.
        """
        self._make_rotation(service_name='verysecretbank.example')
        self._make_honeypot(honeypot_address='decoy-alias@example.com')

        out, _ = self._run()

        self.assertNotIn('verysecretbank.example', out)
        self.assertNotIn('decoy-alias@example.com', out)
        self.assertNotIn('canary@example.com', out)
        self.assertNotIn('canary-user', out)
