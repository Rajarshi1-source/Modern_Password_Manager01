"""
Phase D / D1 (2026-05): JWT_PRIVATE_KEY production-guard regression test.

The settings module raises ImproperlyConfigured at import time when
production-mode bootstrap (WSGI/ASGI, not ``manage.py check``) sees
``DEBUG=False`` without ``JWT_PRIVATE_KEY`` set. The guard prevents
accidentally signing JWTs with ``SECRET_KEY`` — a key whose disclosure
via Django debug pages or settings introspection would let an attacker
forge JWTs for every user.

These tests import settings in a subprocess so the
ImproperlyConfigured fires deterministically (the parent process's
settings are already loaded and cached).
"""

import os
import subprocess
import sys
import textwrap

from django.test import TestCase


def _run_settings_import_in_subprocess(env_overrides, argv0='gunicorn'):
    """Run a fresh ``import django.conf.settings`` with the given env.

    Returns (returncode, stdout, stderr). Used so the production guard
    actually executes — calling settings inside the current test
    process would just hit Django's cached LazySettings.
    """
    code = textwrap.dedent(f"""
        import os, sys
        sys.argv = [{argv0!r}, 'password_manager.wsgi:application']
        sys.path.insert(0, os.getcwd())
        os.environ['DJANGO_SETTINGS_MODULE'] = 'password_manager.settings'
        try:
            from django.conf import settings
            _ = settings.DEBUG  # force load
            print('SETTINGS_LOADED')
        except Exception as e:
            print('SETTINGS_FAILED:' + type(e).__name__ + ':' + str(e)[:200])
    """)
    env = os.environ.copy()
    # Wipe the keys we control so subprocess sees only what we set.
    # PR #276 review (CodeRabbit): include every env var any of the
    # production guards in base.py reads, not just the ones the JWT
    # guard cares about. Without USE_REDIS_CACHE in this list, a CI
    # runner that exports USE_REDIS_CACHE=True at the host level
    # would silently bypass the "USE_REDIS_CACHE unset" test case —
    # making the guard test environment-dependent and useless.
    for k in (
        'DEBUG',
        'JWT_PRIVATE_KEY',
        'USE_REDIS_CHANNELS',
        'USE_REDIS_CACHE',
        'SECRET_KEY',
        # Audit Group A / commit 2 (2026-05): new production guard
        # on DATA_ENCRYPTION_KEY. Wipe so a CI runner that exports
        # the env var at the host level doesn't silently bypass the
        # "DATA_ENCRYPTION_KEY unset" test case — same rationale as
        # USE_REDIS_CACHE above.
        'DATA_ENCRYPTION_KEY',
    ):
        env.pop(k, None)
    env.update(env_overrides)
    cwd = os.path.join(os.path.dirname(__file__), '..', '..')
    cwd = os.path.abspath(cwd)
    result = subprocess.run(
        [sys.executable, '-c', code],
        cwd=cwd, env=env,
        capture_output=True, text=True, timeout=30,
    )
    return result.returncode, result.stdout, result.stderr


class JWTSigningKeyGuardTest(TestCase):

    def test_guard_fires_in_production_without_jwt_private_key(self):
        """DEBUG=False + WSGI bootstrap + no JWT_PRIVATE_KEY => fail."""
        _rc, stdout, stderr = _run_settings_import_in_subprocess({
            'DEBUG': 'False',
            'SECRET_KEY': 'test-secret',
            'USE_REDIS_CHANNELS': 'True',
            # JWT_PRIVATE_KEY intentionally unset
        })
        self.assertIn('SETTINGS_FAILED', stdout + stderr)
        self.assertIn('JWT_PRIVATE_KEY', stdout + stderr)

    def test_guard_silent_when_jwt_private_key_is_set(self):
        """DEBUG=False + JWT_PRIVATE_KEY set => settings load cleanly.

        Also needs USE_REDIS_CACHE=True so the unrelated PR-#276
        ownership-cache guard doesn't intercept this test, and
        DATA_ENCRYPTION_KEY=<anything> so the audit-Group-A guard
        added in commit 2 doesn't either. The point of this test is
        to confirm the JWT_PRIVATE_KEY guard alone goes quiet — so
        every later guard must be silenced too.
        """
        _rc, stdout, stderr = _run_settings_import_in_subprocess({
            'DEBUG': 'False',
            'SECRET_KEY': 'test-secret',
            'USE_REDIS_CHANNELS': 'True',
            'USE_REDIS_CACHE': 'True',
            'JWT_PRIVATE_KEY': 'real-jwt-private-key-material',
            'DATA_ENCRYPTION_KEY': 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=',
        })
        self.assertIn('SETTINGS_LOADED', stdout)

    def test_guard_fires_when_use_redis_cache_unset_in_production(self):
        """PR #276 review (Codex P1): the dark-web scan-ownership IDOR
        fix relies on a shared cache backend across workers. The
        startup guard refuses to boot a non-DEBUG deployment without
        ``USE_REDIS_CACHE=True``.

        Needs DATA_ENCRYPTION_KEY set (audit Group A / commit 2) so
        that guard, which now sits between JWT_PRIVATE_KEY and
        USE_REDIS_CACHE, doesn't intercept this test.
        """
        _rc, stdout, stderr = _run_settings_import_in_subprocess({
            'DEBUG': 'False',
            'SECRET_KEY': 'test-secret',
            'JWT_PRIVATE_KEY': 'jwt-secret-material',
            'DATA_ENCRYPTION_KEY': 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=',
            'USE_REDIS_CHANNELS': 'True',
            # USE_REDIS_CACHE intentionally unset
        })
        self.assertIn('SETTINGS_FAILED', stdout + stderr)
        self.assertIn('USE_REDIS_CACHE', stdout + stderr)

    def test_use_redis_cache_guard_silent_during_manage_py_check(self):
        """``manage.py check`` is exempt — same maintenance-bypass
        clause used by every other production guard."""
        import subprocess, textwrap
        code = textwrap.dedent("""
            import os, sys
            sys.argv = ['manage.py', 'check']
            sys.path.insert(0, os.getcwd())
            os.environ['DJANGO_SETTINGS_MODULE'] = 'password_manager.settings'
            try:
                from django.conf import settings
                _ = settings.DEBUG
                print('SETTINGS_LOADED')
            except Exception as e:
                print('SETTINGS_FAILED:' + type(e).__name__ + ':' + str(e)[:200])
        """)
        env = os.environ.copy()
        for k in ('DEBUG', 'JWT_PRIVATE_KEY', 'USE_REDIS_CHANNELS', 'USE_REDIS_CACHE', 'DATA_ENCRYPTION_KEY'):
            env.pop(k, None)
        env.update({
            'DEBUG': 'False',
            'SECRET_KEY': 'test-secret',
            'USE_REDIS_CHANNELS': 'True',
            # USE_REDIS_CACHE still unset — maintenance bypass should let it pass.
            # DATA_ENCRYPTION_KEY also unset — same maintenance bypass.
        })
        cwd = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', '..')
        )
        result = subprocess.run(
            [sys.executable, '-c', code],
            cwd=cwd, env=env,
            capture_output=True, text=True, timeout=30,
        )
        self.assertIn('SETTINGS_LOADED', result.stdout)

    def test_guard_fires_with_whitespace_only_jwt_private_key(self):
        """PR #275 review (CodeRabbit): pin the .strip() normalization.

        ``os.environ.get('JWT_PRIVATE_KEY')`` returns whitespace
        unchanged. Without the ``(... or '').strip()`` in the guard,
        a value of ``"   "`` would (a) bypass the fail-closed check
        and (b) become the live HS256 signing key — three spaces is a
        trivially-guessable JWT secret. Treat whitespace-only values
        identically to "env var missing".
        """
        _rc, stdout, stderr = _run_settings_import_in_subprocess({
            'DEBUG': 'False',
            'SECRET_KEY': 'test-secret',
            'USE_REDIS_CHANNELS': 'True',
            'JWT_PRIVATE_KEY': '   ',  # whitespace-only
        })
        self.assertIn('SETTINGS_FAILED', stdout + stderr)
        self.assertIn('JWT_PRIVATE_KEY', stdout + stderr)

    def test_guard_silent_during_manage_py_check(self):
        """``python manage.py check`` is exempt — settings load even
        without JWT_PRIVATE_KEY so CI's deploy-check doesn't break."""
        # Simulate argv[0]='manage.py' + argv[1]='check'
        code = textwrap.dedent("""
            import os, sys
            sys.argv = ['manage.py', 'check']
            sys.path.insert(0, os.getcwd())
            os.environ['DJANGO_SETTINGS_MODULE'] = 'password_manager.settings'
            try:
                from django.conf import settings
                _ = settings.DEBUG
                print('SETTINGS_LOADED')
            except Exception as e:
                print('SETTINGS_FAILED:' + type(e).__name__ + ':' + str(e)[:200])
        """)
        env = os.environ.copy()
        for k in ('DEBUG', 'JWT_PRIVATE_KEY', 'USE_REDIS_CHANNELS', 'DATA_ENCRYPTION_KEY'):
            env.pop(k, None)
        env.update({
            'DEBUG': 'False',
            'SECRET_KEY': 'test-secret',
            'USE_REDIS_CHANNELS': 'True',
            # JWT_PRIVATE_KEY + DATA_ENCRYPTION_KEY both unset —
            # maintenance bypass should let it pass anyway.
        })
        cwd = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', '..')
        )
        result = subprocess.run(
            [sys.executable, '-c', code],
            cwd=cwd, env=env,
            capture_output=True, text=True, timeout=30,
        )
        self.assertIn('SETTINGS_LOADED', result.stdout)

    def test_guard_silent_in_debug_mode(self):
        """Dev mode uses the SECRET_KEY fallback — no guard fire."""
        _rc, stdout, stderr = _run_settings_import_in_subprocess({
            'DEBUG': 'True',
            'SECRET_KEY': 'dev-secret',
            # JWT_PRIVATE_KEY intentionally unset — dev path
        })
        self.assertIn('SETTINGS_LOADED', stdout)


class DataEncryptionKeyGuardTest(TestCase):
    """Audit Group A / commit 2 (2026-05): production guard on
    ``DATA_ENCRYPTION_KEY``. Mirrors the JWT_PRIVATE_KEY guard
    pattern — fails closed at module import when DEBUG=False and
    the env var is unset/blank, exempt during DEBUG / TESTING /
    ``manage.py check``."""

    def test_guard_fires_in_production_without_data_encryption_key(self):
        """DEBUG=False + WSGI bootstrap + no DATA_ENCRYPTION_KEY => fail.

        JWT_PRIVATE_KEY and USE_REDIS_CACHE are set so the earlier
        guards pass and ``DATA_ENCRYPTION_KEY`` is the one under test.
        """
        _rc, stdout, stderr = _run_settings_import_in_subprocess({
            'DEBUG': 'False',
            'SECRET_KEY': 'test-secret',
            'JWT_PRIVATE_KEY': 'jwt-secret-material',
            'USE_REDIS_CHANNELS': 'True',
            'USE_REDIS_CACHE': 'True',
            # DATA_ENCRYPTION_KEY intentionally unset
        })
        self.assertIn('SETTINGS_FAILED', stdout + stderr)
        self.assertIn('DATA_ENCRYPTION_KEY', stdout + stderr)

    def test_guard_fires_with_whitespace_only_data_encryption_key(self):
        """Same ``.strip()`` normalization as the JWT_PRIVATE_KEY
        guard — whitespace-only env values are treated as missing,
        otherwise a value of ``"   "`` would (a) bypass the
        fail-closed check and (b) silently route through the
        ``settings.SECRET_KEY[:32]`` fallback used by the legacy
        read path in ``crypto_service``."""
        _rc, stdout, stderr = _run_settings_import_in_subprocess({
            'DEBUG': 'False',
            'SECRET_KEY': 'test-secret',
            'JWT_PRIVATE_KEY': 'jwt-secret-material',
            'USE_REDIS_CHANNELS': 'True',
            'USE_REDIS_CACHE': 'True',
            'DATA_ENCRYPTION_KEY': '   ',  # whitespace-only
        })
        self.assertIn('SETTINGS_FAILED', stdout + stderr)
        self.assertIn('DATA_ENCRYPTION_KEY', stdout + stderr)

    def test_guard_silent_when_data_encryption_key_is_set(self):
        """DEBUG=False + DATA_ENCRYPTION_KEY set + every other prod
        guard satisfied => settings load cleanly."""
        _rc, stdout, stderr = _run_settings_import_in_subprocess({
            'DEBUG': 'False',
            'SECRET_KEY': 'test-secret',
            'JWT_PRIVATE_KEY': 'jwt-secret-material',
            'USE_REDIS_CHANNELS': 'True',
            'USE_REDIS_CACHE': 'True',
            # 32 random bytes, base64-encoded. The settings guard
            # only checks presence — the actual decode happens in
            # crypto_service._get_master_key() at first use.
            'DATA_ENCRYPTION_KEY': 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=',
        })
        self.assertIn('SETTINGS_LOADED', stdout)

    def test_guard_silent_in_debug_mode(self):
        """Dev mode falls back to ``SECRET_KEY[:32]`` — no guard fire."""
        _rc, stdout, stderr = _run_settings_import_in_subprocess({
            'DEBUG': 'True',
            'SECRET_KEY': 'dev-secret',
            # DATA_ENCRYPTION_KEY intentionally unset — dev path
        })
        self.assertIn('SETTINGS_LOADED', stdout)

    def test_guard_silent_during_manage_py_check(self):
        """``python manage.py check`` is exempt — same maintenance
        bypass as JWT_PRIVATE_KEY / USE_REDIS_CACHE. Without this,
        CI's deploy-check would fail before the env var is
        available."""
        code = textwrap.dedent("""
            import os, sys
            sys.argv = ['manage.py', 'check']
            sys.path.insert(0, os.getcwd())
            os.environ['DJANGO_SETTINGS_MODULE'] = 'password_manager.settings'
            try:
                from django.conf import settings
                _ = settings.DEBUG
                print('SETTINGS_LOADED')
            except Exception as e:
                print('SETTINGS_FAILED:' + type(e).__name__ + ':' + str(e)[:200])
        """)
        env = os.environ.copy()
        for k in (
            'DEBUG', 'JWT_PRIVATE_KEY', 'USE_REDIS_CHANNELS',
            'USE_REDIS_CACHE', 'DATA_ENCRYPTION_KEY',
        ):
            env.pop(k, None)
        env.update({
            'DEBUG': 'False',
            'SECRET_KEY': 'test-secret',
            'USE_REDIS_CHANNELS': 'True',
            # DATA_ENCRYPTION_KEY still unset — maintenance bypass
        })
        cwd = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', '..')
        )
        result = subprocess.run(
            [sys.executable, '-c', code],
            cwd=cwd, env=env,
            capture_output=True, text=True, timeout=30,
        )
        self.assertIn('SETTINGS_LOADED', result.stdout)
