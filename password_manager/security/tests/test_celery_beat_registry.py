"""
Guard: every Celery beat entry must name a task that is actually registered.

`@shared_task` derives a task's name from the module that DEFINES it, so a beat
entry written from a design doc rather than from the live registry silently
names a task that does not exist. Beat still publishes the message -- the
scheduler falls back to `send_task` for a name it cannot resolve locally -- and
the worker rejects it as `NotRegistered`. Nothing raises in beat, nothing shows
up as a failed task, and the job simply never runs.

Three genetic/DNA entries sat broken that way (`security.tasks.<func>` instead
of `security.tasks.breach_tasks.<func>`). This module is the check that would
have caught them.
"""

import functools
import json
import os
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase


@functools.lru_cache(maxsize=1)
def _worker_registry():
    """The task names a REAL worker process would register, and nothing else.

    Deliberately spawned as a clean subprocess rather than read off the
    already-running test process's `app.tasks`. `@shared_task` registers a
    function the moment its module is imported, into a registry shared by
    every `Celery()` instance in the process -- so once anything imports
    `security/tasks/dark_protocol_tasks.py` (e.g. a `test_dark_protocol.py`
    test reaching into it directly, inside a test body, well after this
    module has been collected), those tasks look "registered" for the rest of
    the pytest run even though `dark_protocol` is not in `INSTALLED_APPS` and
    no autodiscovery path ever imports that module in production. Running the
    exact registration sequence a worker runs (`autodiscover_tasks()` +
    `import security.tasks`) in a fresh interpreter sidesteps that pollution
    entirely: this subprocess never imports the test suite, so it can only
    end up with what a real worker would have.
    """
    script = (
        "import django, json, os\n"
        "django.setup()\n"
        "from password_manager.celery import app\n"
        "app.autodiscover_tasks(force=True)\n"
        "import security.tasks\n"  # noqa: E501 -- re-exports register the real dotted names
        "print(json.dumps(sorted(app.tasks)))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        env={**os.environ, "DJANGO_SETTINGS_MODULE": settings.SETTINGS_MODULE},
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Failed to snapshot the worker task registry in a subprocess:\n"
            + result.stderr
        )
    # The script's own output is the last line; Django/app startup can log to
    # stdout too, so take the last line rather than assuming stdout is bare.
    last_line = result.stdout.strip().splitlines()[-1]
    return frozenset(json.loads(last_line))


# Beat entries that are known-broken for reasons OUTSIDE this change's scope.
# Each names a task no worker can resolve today, so each is a job that has never
# run. They are quarantined rather than fixed here because every one of them
# belongs to a different feature area and fixing it means turning that feature's
# scheduled work on -- a decision that needs its own review.
#
#   * `ml_security` and `shared` have no `tasks.py` at all.
#   * `update-threat-intel` points at `ml_security.tasks.update_threat_intelligence`,
#     but the task exists as `security.tasks.update_threat_intelligence`.
#   * The Dark Protocol tasks are defined in `security/tasks/dark_protocol_tasks.py`,
#     which `security/tasks/__init__.py` never imports; `dark_protocol` is also
#     not in INSTALLED_APPS, so the `dark_protocol.*` prefix cannot resolve
#     either.
#
# `test_quarantine_list_has_not_rotted` below fails if one of these is fixed or
# removed without also updating this dict, so the list cannot quietly go stale.
KNOWN_UNREGISTERED = {
    'analyze-password-strength-daily': 'ml_security.tasks.analyze_all_passwords',
    'update-threat-intel': 'ml_security.tasks.update_threat_intelligence',
    'cleanup-expired-sessions': 'shared.tasks.cleanup_expired_sessions',
    'dark-protocol-rotate-paths': 'dark_protocol.rotate_network_paths',
    'dark-protocol-health-check': 'dark_protocol.health_check_nodes',
    'dark-protocol-cover-traffic': 'dark_protocol.generate_cover_traffic',
    'dark-protocol-cleanup': 'dark_protocol.cleanup_expired_sessions',
    'dark-protocol-traffic-analysis': 'dark_protocol.analyze_traffic_patterns',
}


class CeleryBeatScheduleRegistryTests(SimpleTestCase):
    """Every scheduled task name must resolve against the live registry."""

    def _beat_schedule(self):
        from password_manager.celery import app

        return app.conf.beat_schedule

    def test_every_beat_entry_names_a_registered_task(self):
        registered = _worker_registry()
        beat_schedule = self._beat_schedule()

        unresolved = {
            entry: config['task']
            for entry, config in beat_schedule.items()
            if config['task'] not in registered
            and entry not in KNOWN_UNREGISTERED
        }

        self.assertEqual(
            unresolved,
            {},
            'These beat entries name tasks that are not in the registry, so the '
            'worker will reject every tick as NotRegistered and the jobs will '
            'never run. `@shared_task` names a task after the module that '
            'DEFINES it -- check the real name against the registry rather than '
            'assuming the package path. Unresolved: {}'.format(unresolved),
        )

    def test_genetic_and_dna_entries_resolve(self):
        """The three entries this module was written for, named explicitly.

        Kept separate from the sweep above so a regression points straight at
        the cause instead of at a generic list.
        """
        registered = _worker_registry()
        beat_schedule = self._beat_schedule()

        expected = {
            'check-genetic-evolution-daily':
                'security.tasks.breach_tasks.daily_genetic_evolution_check',
            'cleanup-genetic-trials':
                'security.tasks.breach_tasks.cleanup_expired_genetic_trials',
            'refresh-dna-tokens-weekly':
                'security.tasks.breach_tasks.refresh_dna_tokens',
        }

        for entry, task_name in expected.items():
            with self.subTest(entry=entry):
                self.assertIn(entry, beat_schedule)
                self.assertEqual(beat_schedule[entry]['task'], task_name)
                self.assertIn(task_name, registered)

    def test_quarantine_list_has_not_rotted(self):
        """A quarantined entry must still exist AND still be unregistered.

        Without this, fixing one of the eight would leave a stale exemption
        behind that silently excuses a future regression on the same entry.
        """
        registered = _worker_registry()
        beat_schedule = self._beat_schedule()

        stale = {}
        for entry, task_name in KNOWN_UNREGISTERED.items():
            config = beat_schedule.get(entry)
            if config is None:
                stale[entry] = 'entry no longer exists — drop it from KNOWN_UNREGISTERED'
            elif config['task'] != task_name:
                stale[entry] = (
                    'now scheduled as {!r} — update or drop the exemption'
                    .format(config['task'])
                )
            elif task_name in registered:
                stale[entry] = 'task is registered now — drop it from KNOWN_UNREGISTERED'

        self.assertEqual(
            stale,
            {},
            'KNOWN_UNREGISTERED is out of date: {}'.format(stale),
        )
