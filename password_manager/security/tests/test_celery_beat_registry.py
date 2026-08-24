"""
Guard: every Celery beat entry must name a task that is actually registered.

`@shared_task` derives a task's name from the module that DEFINES it, so a beat
entry written from a design doc rather than from the live registry silently
names a task that does not exist. Beat still publishes the message -- the
scheduler falls back to `send_task` for a name it cannot resolve locally -- and
the worker rejects it as `NotRegistered`. Nothing raises in beat, nothing shows
up as a failed task, and the job simply never runs.

An audit of all 42 entries once found 11 broken this way, for three different
underlying reasons -- all now fixed, and asserted explicitly below rather than
just falling out of the whole-schedule sweep, so a regression on any one of
them points straight at its cause instead of at a generic list:

- 3 genetic/DNA entries scheduled `security.tasks.<func>` instead of the real
  `security.tasks.breach_tasks.<func>` (wrong module prefix).
- 5 Dark Protocol entries scheduled the CORRECT name
  (`dark_protocol.<func>`, matching each task's explicit `name=`) but nothing
  ever imported `dark_protocol_tasks.py`, so the decorators never registered
  it (missing import, not a wrong name).
- 1 entry (`update-threat-intel`) scheduled `ml_security.tasks.update_threat_intelligence`
  for a task that is actually `security.tasks.update_threat_intelligence`
  (wrong app prefix).

The remaining 2 of the original 11 were handled differently:
`cleanup-expired-sessions` named a task that genuinely did not exist yet
(`shared` had no `tasks.py`) -- implemented rather than renamed, since Django
ships this exact cleanup as `clearsessions`. `analyze-password-strength-daily`
was removed outright: no such task exists anywhere, and writing one would mean
the server decrypting every user's stored passwords, which conflicts with the
zero-knowledge design `daily_predictive_scan` (security/tasks/breach_tasks.py)
already documents for this exact kind of daily analysis.
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
# Currently empty: the 11 broken entries an earlier audit found have all been
# fixed (or, for `analyze-password-strength-daily`, deliberately removed --
# see the module docstring). Kept as a named, exported quarantine point rather
# than deleted outright, so the NEXT broken beat entry this guard test catches
# has an obvious, already-wired place to go if it turns out to need one.
#
# `test_quarantine_list_has_not_rotted` below fails if an entry sitting here
# gets fixed or removed without also updating this dict, so the list cannot
# quietly go stale.
KNOWN_UNREGISTERED = {}


class CeleryBeatScheduleRegistryTests(SimpleTestCase):
    """Every scheduled task name must resolve against the live registry."""

    def _beat_schedule(self):
        from password_manager.celery import app

        # `app.finalize()` is REQUIRED here, not incidental tidying.
        #
        # Not every beat entry is in the static dict passed to `app.conf.update()`
        # in celery.py. Feature modules that cannot be imported at module scope
        # (they touch the Django app registry before `django.setup()` finishes)
        # contribute their entries from an `@app.on_after_finalize` handler
        # instead -- currently Time-Lock and Honeypot. That signal fires on
        # finalization, which in a real worker/beat process happens during
        # startup, but in a test process happens only when something forces it.
        #
        # Reading `app.conf.beat_schedule` without finalizing therefore returns
        # a schedule MISSING exactly the entries most likely to be broken -- the
        # deferred ones. That is not a hypothetical: before this call was added,
        # the four `time_lock.*` entries were absent from every assertion in
        # this file, including `test_every_beat_entry_names_a_registered_task`,
        # so the very bug class this suite exists to catch was invisible for the
        # entries fixed in PR #483.
        #
        # Idempotent -- Celery guards on `self.finalized`, so repeated calls
        # across test methods are free and the signal fires once.
        app.finalize()

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

    def test_update_threat_intel_entry_resolves(self):
        """Was `ml_security.tasks.update_threat_intelligence` (wrong app
        prefix); the task is `security.tasks.update_threat_intelligence`."""
        registered = _worker_registry()
        beat_schedule = self._beat_schedule()

        self.assertEqual(
            beat_schedule['update-threat-intel']['task'],
            'security.tasks.update_threat_intelligence',
        )
        self.assertIn('security.tasks.update_threat_intelligence', registered)

    def test_dark_protocol_entries_resolve(self):
        """Four of the five Dark Protocol entries: correct names, missing
        import.

        Each `@shared_task` already carried the right `name=`; nothing
        imported `dark_protocol_tasks.py`, so none of the five ever
        registered. Fixed via the import in `security/tasks/__init__.py` --
        these beat entries needed no change at all.

        `dark-protocol-health-check` is deliberately NOT among the four
        checked here -- see `test_health_check_nodes_entry_stays_removed`
        below for why.
        """
        registered = _worker_registry()
        beat_schedule = self._beat_schedule()

        expected = {
            'dark-protocol-rotate-paths': 'dark_protocol.rotate_network_paths',
            'dark-protocol-cover-traffic': 'dark_protocol.generate_cover_traffic',
            'dark-protocol-cleanup': 'dark_protocol.cleanup_expired_sessions',
            'dark-protocol-traffic-analysis': 'dark_protocol.analyze_traffic_patterns',
        }

        for entry, task_name in expected.items():
            with self.subTest(entry=entry):
                self.assertEqual(beat_schedule[entry]['task'], task_name)
                self.assertIn(task_name, registered)

    def test_health_check_nodes_entry_stays_removed(self):
        """`dark-protocol-health-check` must not silently reappear.

        CodeRabbit, PR #482 round 4: `health_check_nodes` (dark_protocol_tasks.py)
        queries every `status='active'` DarkProtocolNode with no opt-in/config
        gate, decides reachability via `random.random() > 0.05` (an explicit
        simulation stub, not a real ping), and marks a node `status='inactive'`
        -- a real, persistent mutation -- after 3 simulated failures in a
        rolling 5-minute window. Scheduled every minute, a real node WILL
        eventually rack up 3 unlucky coin flips purely by chance, at which
        point this task takes it offline for a reason that has nothing to do
        with whether it's actually reachable. The task is registered (and
        still directly callable/tested, e.g. `test_dark_protocol.py`'s
        `test_health_check_task`) but deliberately not beat-scheduled until
        it does a real check or gets a config gate on the mutation. This
        asserts it stays unscheduled rather than being silently reintroduced.
        """
        beat_schedule = self._beat_schedule()
        self.assertNotIn('dark-protocol-health-check', beat_schedule)

    def test_cleanup_expired_django_sessions_entry_resolves(self):
        """`shared.tasks.cleanup_expired_sessions` -- shared had no
        `tasks.py` at all; implemented in `shared/tasks.py` rather than
        renamed, since it names a real, standard piece of Django hygiene."""
        registered = _worker_registry()
        beat_schedule = self._beat_schedule()

        self.assertEqual(
            beat_schedule['cleanup-expired-sessions']['task'],
            'shared.tasks.cleanup_expired_sessions',
        )
        self.assertIn('shared.tasks.cleanup_expired_sessions', registered)

    def test_dead_password_strength_entry_was_removed_not_fixed(self):
        """`analyze-password-strength-daily` must not silently reappear.

        No task ever backed this name; renaming it to something real would
        require the server to decrypt vault passwords to score them, which
        conflicts with the zero-knowledge design this codebase already
        commits to for daily password-risk analysis (see
        `daily_predictive_scan`). Removed rather than fixed -- this asserts
        it stays gone rather than being silently reintroduced by a future
        merge.
        """
        beat_schedule = self._beat_schedule()
        self.assertNotIn('analyze-password-strength-daily', beat_schedule)

    def test_honeypot_entries_resolve(self):
        """The six scheduled honeypot-email (breach canary) entries.

        This feature was broken in BOTH ways the other tests in this file
        cover separately, which is why it needs its own case:

          * unregistered, like Dark Protocol -- nothing in production imported
            `honeypot_tasks.py` (only tests did, by module path), so its nine
            `@shared_task`s never registered. `autodiscover_tasks()` does not
            help: it imports the `security.tasks` package, so a submodule this
            package's __init__ never names stays unimported.
          * unscheduled, like Time-Lock -- there were no `honeypot-*` beat
            entries at all.

        Fixing either alone would have been inert: an entry naming an
        unregistered task is discarded by the worker, and a registered task
        with no entry is never enqueued. This test asserts both halves.
        """
        registered = _worker_registry()
        beat_schedule = self._beat_schedule()

        expected = {
            'honeypot-scan-all': 'security.scan_all_honeypots',
            'honeypot-process-pending-rotations': 'security.process_pending_rotations',
            'honeypot-analyze-breach-patterns': 'security.analyze_breach_patterns',
            'honeypot-cleanup-expired': 'security.cleanup_expired_honeypots',
            'honeypot-generate-stats': 'security.generate_honeypot_stats',
            'honeypot-send-breach-digest': 'security.send_breach_digest',
        }

        for entry, task_name in expected.items():
            with self.subTest(entry=entry):
                self.assertIn(
                    entry,
                    beat_schedule,
                    f'{entry} missing from beat_schedule — is '
                    'HONEYPOT_BEAT_SCHEDULE still merged in celery.py?',
                )
                self.assertEqual(beat_schedule[entry]['task'], task_name)
                self.assertIn(task_name, registered)

    def test_honeypot_scan_all_matches_its_own_docstring_cadence(self):
        """`scan_all_honeypots`'s docstring says "every 15-30 minutes" -- the
        actual detection loop, since `HoneypotEmail.last_checked_at` is
        never re-read on any other schedule. A beat interval outside that
        range silently breaks the task's own stated contract without
        raising anywhere, exactly like the name-mismatch bugs the rest of
        this file guards against, just one level up (right task, wrong
        cadence instead of wrong name)."""
        beat_schedule = self._beat_schedule()

        schedule = beat_schedule['honeypot-scan-all']['schedule']
        seconds = schedule.total_seconds() if hasattr(schedule, 'total_seconds') else schedule

        self.assertGreaterEqual(seconds, 900, 'faster than the documented 15-minute floor')
        self.assertLessEqual(seconds, 1800, 'slower than the documented 30-minute ceiling')

    def test_argument_taking_honeypot_tasks_stay_unscheduled(self):
        """Three honeypot tasks take a required id and must never be scheduled.

        `check_honeypot_activity(honeypot_id)`, `check_all_user_honeypots(user_id)`
        and `correlate_with_hibp(breach_id)` are fan-out targets, invoked BY the
        scheduled tasks with an argument. A beat entry for any of them enqueues
        a no-argument call that raises TypeError on the worker every single
        tick -- a failure mode that looks like a broken worker rather than a
        bad schedule, so it is worth pinning explicitly.
        """
        beat_schedule = self._beat_schedule()

        must_not_be_scheduled = {
            'security.check_honeypot_activity',
            'security.check_all_user_honeypots',
            'security.correlate_with_hibp',
        }

        scheduled = {
            config['task']
            for config in beat_schedule.values()
            if 'task' in config
        }

        self.assertEqual(
            must_not_be_scheduled & scheduled,
            set(),
            'argument-taking honeypot task(s) scheduled with no argument',
        )

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

    def test_mesh_deaddrop_entries_resolve(self):
        """The five mesh dead-drop entries, four of which never ran.

        `deaddrop_tasks.py` has always defined these, and its tasks have
        always REGISTERED correctly (unlike Honeypot's -- `mesh_deaddrop/
        tasks/__init__.py` star-imports the module, so `autodiscover_tasks()`
        reaches it). Only the scheduling half was missing: nothing merged that
        module's CELERY_BEAT_SCHEDULE, so four fully-implemented tasks were
        never enqueued. `flush-pending-sync` ran only because it was also
        hand-written into celery.py's static schedule.
        """
        registered = _worker_registry()
        beat_schedule = self._beat_schedule()

        expected = {
            'check-expired-deaddrops': 'mesh_deaddrop.check_expired_deaddrops',
            'check-mesh-node-health': 'mesh_deaddrop.check_mesh_node_health',
            'cleanup-old-access-logs': 'mesh_deaddrop.cleanup_old_access_logs',
            'cleanup-location-cache': 'mesh_deaddrop.cleanup_location_cache',
            'flush-pending-sync': 'mesh_deaddrop.flush_pending_sync',
        }

        for entry, task_name in expected.items():
            with self.subTest(entry=entry):
                self.assertIn(
                    entry,
                    beat_schedule,
                    f'{entry} missing from beat_schedule — is '
                    'MESH_DEADDROP_BEAT_SCHEDULE still merged in celery.py?',
                )
                self.assertEqual(beat_schedule[entry]['task'], task_name)
                self.assertIn(task_name, registered)

    def test_mesh_deaddrop_static_and_merged_entries_agree(self):
        """`flush-pending-sync` is defined TWICE, deliberately.

        celery.py keeps it in the static schedule (so it survives an import
        failure of the merged dict) while `deaddrop_tasks.py` also defines it.
        The merge overwrites the static value, so the duplication is only safe
        while the two agree exactly -- otherwise the static entry is dead
        weight that silently reads as the live config.

        Compared against celery.py's ACTUAL static entry, not a hand-copied
        literal -- an earlier version of this test compared MESH_SCHEDULE
        against an inline dict typed out here, which meant this test would
        happily keep passing even if the static entry in celery.py drifted,
        as long as nobody also touched this file. Read from source via `ast`
        rather than the live `app.conf.beat_schedule`: by the time any test in
        this class calls `_beat_schedule()`, `app.finalize()` has already run
        the merge, which overwrites `app.conf.beat_schedule['flush-pending-
        sync']` in place -- there is no post-import way left in this process
        to see the PRE-merge static value, since Celery's `conf.update()`
        stores the dict by reference rather than copying it. Parsing the
        source text sidesteps that entirely, and matches the pattern already
        used one test below (`test_every_module_beat_schedule_is_merged`) for
        the identical class of problem.
        """
        import ast
        import pathlib

        from mesh_deaddrop.tasks import CELERY_BEAT_SCHEDULE as MESH_SCHEDULE

        celery_py = pathlib.Path(settings.BASE_DIR) / 'password_manager' / 'celery.py'
        tree = ast.parse(celery_py.read_text(encoding='utf-8'), filename=str(celery_py))

        static_entry = None
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == 'update'):
                continue
            for kw in node.keywords:
                if kw.arg != 'beat_schedule' or not isinstance(kw.value, ast.Dict):
                    continue
                for key, value in zip(kw.value.keys, kw.value.values):
                    if (isinstance(key, ast.Constant)
                            and key.value == 'flush-pending-sync'
                            and isinstance(value, ast.Dict)):
                        static_entry = {
                            k.value: v.value
                            for k, v in zip(value.keys, value.values)
                            if isinstance(k, ast.Constant) and isinstance(v, ast.Constant)
                        }

        self.assertIsNotNone(
            static_entry,
            "couldn't find a static 'flush-pending-sync' entry in "
            'celery.py — has it been moved or renamed?',
        )
        self.assertEqual(
            MESH_SCHEDULE['flush-pending-sync'],
            static_entry,
            'the merged flush-pending-sync no longer matches the static entry '
            'in celery.py — reconcile them or drop the static duplicate',
        )

    def test_argument_taking_deaddrop_tasks_stay_unscheduled(self):
        """Fan-out targets must never get a beat entry.

        The three `notify_*` tasks take a required dead-drop id and are
        invoked BY `check_expired_deaddrops`. `rebalance_orphaned_fragments`
        takes no argument but is likewise a fan-out target, called by
        `check_mesh_node_health` only when it actually marks nodes offline --
        scheduling it independently would run a rebalance sweep on a cadence
        nothing asked for. Same guard, same reasoning, as the honeypot case.
        """
        beat_schedule = self._beat_schedule()

        must_not_be_scheduled = {
            'mesh_deaddrop.notify_owner_deaddrop_expired',
            'mesh_deaddrop.notify_recipient_deaddrop_ready',
            'mesh_deaddrop.notify_owner_deaddrop_collected',
            'mesh_deaddrop.rebalance_orphaned_fragments',
        }

        scheduled = {
            config['task']
            for config in beat_schedule.values()
            if 'task' in config
        }

        self.assertEqual(
            must_not_be_scheduled & scheduled,
            set(),
            'fan-out mesh_deaddrop task(s) scheduled directly',
        )

    def test_every_module_beat_schedule_is_merged(self):
        """The generalised guard for this entire bug class.

        Three separate features have now shipped a module-level
        CELERY_BEAT_SCHEDULE that nothing merged -- Time-Lock (PR #483),
        Honeypot (PR #486), and Mesh Dead Drop (this change). Each was found
        by hand, one at a time, long after the feature was "done". The
        per-feature tests above pin the entries we already know about; this
        one closes the class, exactly as
        docs/privacy-features-gap-remediation-plan.md §4.4 proposed: discover
        every such dict in the tree and assert its entries actually reach the
        live schedule.

        Deliberately checks that each entry ARRIVES, not HOW. `personality_auth`
        is the reason: its two entries are hand-copied into celery.py's static
        schedule rather than merged from its module, which is a drift hazard
        but not an orphan -- the tasks do run. Demanding a merge would fail a
        working feature; demanding arrival catches the one thing that actually
        breaks a user (a task that never runs).

        The dicts are discovered by walking the source tree, not from a list
        kept here, so a NEW feature module that repeats this mistake fails
        this test the day it lands rather than whenever someone next audits.
        """
        import ast
        import pathlib

        beat_schedule = self._beat_schedule()
        repo_root = pathlib.Path(settings.BASE_DIR)

        # Parse rather than import: importing every module that defines a
        # schedule would drag half the app into this process and pollute the
        # shared @shared_task registry, the exact contamination
        # `_worker_registry()` spawns a subprocess to avoid.
        missing = {}
        found_modules = []
        for path in sorted(repo_root.rglob('*.py')):
            if any(part in {'migrations', 'node_modules', '.venv', 'canny'}
                   for part in path.parts):
                continue
            try:
                tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
            except (SyntaxError, UnicodeDecodeError):  # pragma: no cover
                continue

            for node in tree.body:
                if not isinstance(node, ast.Assign):
                    continue
                names = {t.id for t in node.targets if isinstance(t, ast.Name)}
                if 'CELERY_BEAT_SCHEDULE' not in names:
                    continue
                if not isinstance(node.value, ast.Dict):  # pragma: no cover
                    continue

                rel = path.relative_to(repo_root).as_posix()
                found_modules.append(rel)
                for key, value in zip(node.value.keys, node.value.values):
                    if not isinstance(key, ast.Constant):  # pragma: no cover
                        continue
                    entry = key.value
                    task_name = None
                    if isinstance(value, ast.Dict):
                        for k, v in zip(value.keys, value.values):
                            if (isinstance(k, ast.Constant) and k.value == 'task'
                                    and isinstance(v, ast.Constant)):
                                task_name = v.value
                    if entry not in beat_schedule:
                        missing[f'{rel}::{entry}'] = (
                            'defined but never reaches app.conf.beat_schedule'
                        )
                    elif task_name and beat_schedule[entry]['task'] != task_name:
                        missing[f'{rel}::{entry}'] = (
                            'live schedule runs {!r}, module defines {!r}'
                            .format(beat_schedule[entry]['task'], task_name)
                        )

        # Guard the guard: if the walk silently stops finding anything (a
        # moved tree, a broken rglob), the assertion below would pass
        # vacuously and this whole test would become decorative.
        self.assertGreaterEqual(
            len(found_modules), 4,
            'expected to discover at least the 4 known module-level '
            'CELERY_BEAT_SCHEDULE dicts, found: {}'.format(found_modules),
        )

        self.assertEqual(
            missing,
            {},
            'module-level CELERY_BEAT_SCHEDULE entries that never run: {}'
            .format(missing),
        )
