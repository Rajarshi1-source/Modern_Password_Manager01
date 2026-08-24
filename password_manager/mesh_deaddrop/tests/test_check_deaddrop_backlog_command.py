"""
Tests for the `check_deaddrop_backlog` management command.

This command is the pre-deploy safety check for the mesh dead-drop beat
schedule. Four of those entries have never run, so the first tick after they
are merged processes the whole accumulated backlog at once -- most visibly
`check_expired_deaddrops`, which sends one real email per past-expiry drop.

Each filter here deliberately mirrors the corresponding task in
`mesh_deaddrop/tasks/deaddrop_tasks.py`. A test that passes while the task's
own filter has drifted would make the command's "safe to deploy" verdict a
lie, so the boundary cases below (future expiry, already-expired status,
inactive) exist to pin that correspondence rather than merely to exercise the
command. Same discipline, and the same reason, as
`security/tests/test_check_honeypot_backlog_command.py`.
"""

import uuid
from datetime import timedelta
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from mesh_deaddrop.models import DeadDrop, DeadDropAccess, MeshNode


class CheckDeaddropBacklogCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='deaddrop-user',
            email='deaddrop@example.com',
            password='test-password-not-a-secret',  # noqa: S106
        )

    def _run(self):
        """Run the command, returning (stdout, exit_code).

        The command raises SystemExit(1) when a mailing/deleting backlog
        exists so a deploy script can gate on it; translate that into a
        return value.
        """
        out = StringIO()
        try:
            call_command('check_deaddrop_backlog', stdout=out)
        except SystemExit as exc:
            return out.getvalue(), exc.code
        return out.getvalue(), 0

    def _make_drop(self, **overrides):
        defaults = dict(
            owner=self.user,
            title='drop',
            latitude='51.500000',
            longitude='-0.120000',
            encrypted_secret=b'x',
            secret_hash='hash',
            status='active',
            is_active=True,
            expires_at=timezone.now() - timedelta(days=2),
        )
        defaults.update(overrides)
        return DeadDrop.objects.create(**defaults)

    def _make_node(self, *, stale):
        node = MeshNode.objects.create(
            public_key='pk', device_name='node', ble_address=str(uuid.uuid4())[:17],
            is_online=True,
        )
        # `last_seen` is auto_now=True, so it cannot be set through create().
        # A queryset .update() writes the column directly, bypassing the
        # auto-timestamp -- the only way to age a row in a test.
        MeshNode.objects.filter(pk=node.pk).update(
            last_seen=timezone.now() - timedelta(minutes=30 if stale else 1)
        )
        return node

    # -- the clean case ---------------------------------------------------

    def test_no_backlog_exits_zero(self):
        out, code = self._run()

        self.assertEqual(code, 0)
        self.assertIn('No backlog', out)

    def test_stale_nodes_alone_do_not_fail_the_deploy_gate(self):
        """`check_mesh_node_health` neither mails nor deletes, so it is
        reported as context but must not set a non-zero exit code -- gating a
        deploy on it would block for something that is purely corrective."""
        self._make_node(stale=True)

        out, code = self._run()

        self.assertEqual(code, 0)
        self.assertIn('No backlog', out)
        self.assertIn('marked offline', out)

    # -- the real hazard: one email per past-expiry drop -------------------

    def test_expired_drop_is_reported_and_gates_the_deploy(self):
        drop = self._make_drop()

        out, code = self._run()

        self.assertEqual(code, 1)
        self.assertIn('BACKLOG FOUND', out)
        self.assertIn(str(drop.id), out)

    def test_report_carries_no_identifying_metadata(self):
        """Stdout lands in cluster log aggregation. IDs and durations only --
        never titles, owners, or coordinates, which together would map a
        person to a physical location this product exists to protect."""
        drop = self._make_drop(title='Behind the third oak, Hyde Park')

        out, _ = self._run()

        self.assertIn(str(drop.id), out)
        self.assertNotIn('Behind the third oak', out)
        self.assertNotIn(self.user.username, out)
        self.assertNotIn('51.5', out)

    # -- boundary cases pinning the task's own filter ----------------------

    def test_future_expiry_is_not_backlog(self):
        self._make_drop(expires_at=timezone.now() + timedelta(days=1))

        _, code = self._run()

        self.assertEqual(code, 0)

    def test_already_expired_status_is_not_backlog(self):
        """`check_expired_deaddrops` filters status__in=[pending, distributed,
        active]. A drop already marked 'expired' has had its email sent and
        must not be counted again."""
        self._make_drop(status='expired')

        _, code = self._run()

        self.assertEqual(code, 0)

    def test_inactive_drop_is_not_backlog(self):
        self._make_drop(is_active=False)

        _, code = self._run()

        self.assertEqual(code, 0)

    # -- the deletion backlog ---------------------------------------------

    def test_old_access_logs_are_reported(self):
        """`cleanup_old_access_logs` hard-deletes rows past 90 days. Only
        DeadDropAccess is exercised here: FragmentTransfer is queried with an
        identical cutoff and shape, and covering one of the two pins the
        cutoff correspondence without dragging in the fragment fixture chain.
        """
        drop = self._make_drop(expires_at=timezone.now() + timedelta(days=1))
        access = DeadDropAccess.objects.create(
            dead_drop=drop, claimed_latitude='51.500000',
            claimed_longitude='-0.120000', result='success',
        )
        # `access_time` is auto_now_add=True -- same .update() reason as above.
        DeadDropAccess.objects.filter(pk=access.pk).update(
            access_time=timezone.now() - timedelta(days=120)
        )

        out, code = self._run()

        self.assertEqual(code, 1)
        self.assertIn('1 access', out)

    def test_recent_access_logs_are_not_backlog(self):
        drop = self._make_drop(expires_at=timezone.now() + timedelta(days=1))
        DeadDropAccess.objects.create(
            dead_drop=drop, claimed_latitude='51.500000',
            claimed_longitude='-0.120000', result='success',
        )

        _, code = self._run()

        self.assertEqual(code, 0)

    # -- the unbounded-output guard ---------------------------------------

    def test_large_backlog_reports_true_total_and_truncates_the_sample(self):
        """The summary count must be the TRUE total even when the per-row
        detail list is capped -- otherwise the report understates the email
        volume it exists to warn about."""
        from mesh_deaddrop.management.commands.check_deaddrop_backlog import (
            MAX_DEADDROP_SAMPLES,
        )

        overflow = 7
        for _ in range(MAX_DEADDROP_SAMPLES + overflow):
            self._make_drop()

        out, code = self._run()

        self.assertEqual(code, 1)
        self.assertIn(f'{MAX_DEADDROP_SAMPLES + overflow} dead drop(s)', out)
        self.assertIn(f'... and {overflow} more', out)
        self.assertEqual(out.count('DeadDrop '), MAX_DEADDROP_SAMPLES)
