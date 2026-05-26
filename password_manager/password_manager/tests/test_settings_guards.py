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
    # Wipe the keys we control so subprocess sees only what we set
    for k in ('DEBUG', 'JWT_PRIVATE_KEY', 'USE_REDIS_CHANNELS', 'SECRET_KEY'):
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
        rc, stdout, stderr = _run_settings_import_in_subprocess({
            'DEBUG': 'False',
            'SECRET_KEY': 'test-secret',
            'USE_REDIS_CHANNELS': 'True',
            # JWT_PRIVATE_KEY intentionally unset
        })
        self.assertIn('SETTINGS_FAILED', stdout + stderr)
        self.assertIn('JWT_PRIVATE_KEY', stdout + stderr)

    def test_guard_silent_when_jwt_private_key_is_set(self):
        """DEBUG=False + JWT_PRIVATE_KEY set => settings load cleanly."""
        rc, stdout, stderr = _run_settings_import_in_subprocess({
            'DEBUG': 'False',
            'SECRET_KEY': 'test-secret',
            'USE_REDIS_CHANNELS': 'True',
            'JWT_PRIVATE_KEY': 'real-jwt-private-key-material',
        })
        self.assertIn('SETTINGS_LOADED', stdout)

    def test_guard_fires_with_whitespace_only_jwt_private_key(self):
        """PR #275 review (CodeRabbit): pin the .strip() normalization.

        ``os.environ.get('JWT_PRIVATE_KEY')`` returns whitespace
        unchanged. Without the ``(... or '').strip()`` in the guard,
        a value of ``"   "`` would (a) bypass the fail-closed check
        and (b) become the live HS256 signing key — three spaces is a
        trivially-guessable JWT secret. Treat whitespace-only values
        identically to "env var missing".
        """
        rc, stdout, stderr = _run_settings_import_in_subprocess({
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
        for k in ('DEBUG', 'JWT_PRIVATE_KEY', 'USE_REDIS_CHANNELS'):
            env.pop(k, None)
        env.update({
            'DEBUG': 'False',
            'SECRET_KEY': 'test-secret',
            'USE_REDIS_CHANNELS': 'True',
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
        rc, stdout, stderr = _run_settings_import_in_subprocess({
            'DEBUG': 'True',
            'SECRET_KEY': 'dev-secret',
            # JWT_PRIVATE_KEY intentionally unset — dev path
        })
        self.assertIn('SETTINGS_LOADED', stdout)
