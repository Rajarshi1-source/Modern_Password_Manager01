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


def _read_pkce_required_in_subprocess(env_value):
    """Import settings in a fresh subprocess with OAUTH_PKCE_REQUIRED set
    to ``env_value`` (or removed entirely when ``env_value`` is None) and
    return the resulting bool. Runs in DEBUG so the production guards stay
    quiet. Deterministic regardless of the host process env / .env."""
    import subprocess
    import sys
    import textwrap

    code = textwrap.dedent("""
        import os, sys
        sys.argv = ['gunicorn', 'password_manager.wsgi:application']
        sys.path.insert(0, os.getcwd())
        os.environ['DJANGO_SETTINGS_MODULE'] = 'password_manager.settings'
        from django.conf import settings
        print('PKCE=' + str(settings.OAUTH_PKCE_REQUIRED))
    """)
    env = os.environ.copy()
    # Seed empty (not ``pop``) so base.py's load_dotenv() can't
    # repopulate it from a repo/local .env and break determinism — the
    # strip-first normalization reads '' as "unset" → secure default.
    env['OAUTH_PKCE_REQUIRED'] = ''
    env.update({'DEBUG': 'True', 'SECRET_KEY': 'test-secret'})
    if env_value is not None:
        env['OAUTH_PKCE_REQUIRED'] = env_value
    cwd = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    result = subprocess.run(
        [sys.executable, '-c', code],
        cwd=cwd, env=env, capture_output=True, text=True, timeout=30,
    )
    return result.stdout, result.stderr


class PkceDefaultTests(TestCase):
    """Audit Group D / #10: OAUTH_PKCE_REQUIRED now defaults to True
    (the 2026-07 cutover). Public clients are protected against
    authorization-code interception unless an operator explicitly opts
    out via OAUTH_PKCE_REQUIRED=false."""

    def test_pkce_required_defaults_true_when_unset(self):
        stdout, stderr = _read_pkce_required_in_subprocess(None)
        self.assertIn('PKCE=True', stdout, msg=stderr)

    def test_pkce_required_blank_value_stays_true(self):
        # PR #286 review (CodeRabbit): a blank value must NOT silently
        # disable PKCE — it reads as "unset" → secure default True.
        stdout, stderr = _read_pkce_required_in_subprocess('   ')
        self.assertIn('PKCE=True', stdout, msg=stderr)

    def test_pkce_required_explicit_false_is_honored(self):
        stdout, stderr = _read_pkce_required_in_subprocess('false')
        self.assertIn('PKCE=False', stdout, msg=stderr)


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
    # Seed the keys we control to empty strings so the subprocess sees
    # only what ``env_overrides`` sets.
    # PR #276 review (CodeRabbit): include every env var any of the
    # production guards in base.py reads, not just the ones the JWT
    # guard cares about. Without USE_REDIS_CACHE in this list, a CI
    # runner that exports USE_REDIS_CACHE=True at the host level
    # would silently bypass the "USE_REDIS_CACHE unset" test case —
    # making the guard test environment-dependent and useless.
    # PR #280 review (CodeRabbit): seed empty strings rather than
    # ``pop``-ing. base.py calls ``load_dotenv()`` at import, which
    # populates any var *absent* from the environment from a repo or
    # local ``.env`` file — so a popped key could be silently
    # repopulated, making these subprocess assertions depend on
    # filesystem state. ``load_dotenv`` does not override a var that
    # is already present (even when empty), and every guard normalises
    # via ``(... or '').strip()``, so an empty string reads as "unset".
    for k in (
        'DEBUG',
        'JWT_PRIVATE_KEY',
        'USE_REDIS_CHANNELS',
        'USE_REDIS_CACHE',
        'SECRET_KEY',
        # Audit Group A / commit 2 (2026-05): new production guard
        # on DATA_ENCRYPTION_KEY. Seed so a CI runner that exports
        # the env var at the host level doesn't silently bypass the
        # "DATA_ENCRYPTION_KEY unset" test case — same rationale as
        # USE_REDIS_CACHE above.
        'DATA_ENCRYPTION_KEY',
        # Audit Group B (2026-05): production guards on the cert-signing
        # secrets — seed so a host-level export can't bypass the
        # "cert secret unset" test cases.
        'GENETIC_CERT_SECRET',
        'QUANTUM_CERT_SECRET',
    ):
        env[k] = ''
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
        ownership-cache guard doesn't intercept this test,
        DATA_ENCRYPTION_KEY=<anything> so the audit-Group-A guard
        added in commit 2 doesn't either, and the Group-B cert-signing
        secrets so their guard (last in the chain) stays quiet. The
        point of this test is to confirm the JWT_PRIVATE_KEY guard
        alone goes quiet — so every later guard must be silenced too.
        """
        _rc, stdout, stderr = _run_settings_import_in_subprocess({
            'DEBUG': 'False',
            'SECRET_KEY': 'test-secret',
            'USE_REDIS_CHANNELS': 'True',
            'USE_REDIS_CACHE': 'True',
            'JWT_PRIVATE_KEY': 'real-jwt-private-key-material',
            'DATA_ENCRYPTION_KEY': 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=',
            'GENETIC_CERT_SECRET': 'genetic-cert-secret-material',
            'QUANTUM_CERT_SECRET': 'quantum-cert-secret-material',
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
        # Seed empty (not ``pop``) so load_dotenv can't repopulate from
        # a repo/local .env — see _run_settings_import_in_subprocess.
        for k in ('DEBUG', 'JWT_PRIVATE_KEY', 'USE_REDIS_CHANNELS', 'USE_REDIS_CACHE', 'DATA_ENCRYPTION_KEY'):
            env[k] = ''
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
        # Seed empty (not ``pop``) so load_dotenv can't repopulate from
        # a repo/local .env — see _run_settings_import_in_subprocess.
        for k in ('DEBUG', 'JWT_PRIVATE_KEY', 'USE_REDIS_CHANNELS', 'DATA_ENCRYPTION_KEY'):
            env[k] = ''
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
            # Group B cert-signing secrets — their guard sits last in
            # the chain, so it must also be satisfied for a clean load.
            'GENETIC_CERT_SECRET': 'genetic-cert-secret-material',
            'QUANTUM_CERT_SECRET': 'quantum-cert-secret-material',
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

    def test_malformed_data_encryption_key_fails_fast_at_startup(self):
        """PR #280 review (CodeRabbit): a non-empty but malformed
        DATA_ENCRYPTION_KEY (bad base64 / wrong decoded length) must
        fail at module load, not boot the app and defer the error to
        the first encrypt/decrypt. This validation runs in *every*
        mode when the key is set — so DEBUG=True here isolates it from
        the DEBUG-gated presence guard at the bottom of base.py."""
        _rc, stdout, stderr = _run_settings_import_in_subprocess({
            'DEBUG': 'True',
            'SECRET_KEY': 'dev-secret',
            'DATA_ENCRYPTION_KEY': 'not-valid-base64!!!',
        })
        self.assertIn('SETTINGS_FAILED', stdout + stderr)
        self.assertIn('DATA_ENCRYPTION_KEY', stdout + stderr)

    def test_short_data_encryption_key_fails_fast_at_startup(self):
        """Valid base64 that decodes to the wrong length (16 bytes,
        not the 32 AES-256 needs) is also rejected at startup."""
        import base64 as _b64
        _rc, stdout, stderr = _run_settings_import_in_subprocess({
            'DEBUG': 'True',
            'SECRET_KEY': 'dev-secret',
            'DATA_ENCRYPTION_KEY': _b64.b64encode(b'A' * 16).decode(),
        })
        self.assertIn('SETTINGS_FAILED', stdout + stderr)
        self.assertIn('DATA_ENCRYPTION_KEY', stdout + stderr)

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
        # Seed empty (not ``pop``) so load_dotenv can't repopulate from
        # a repo/local .env — see _run_settings_import_in_subprocess.
        for k in (
            'DEBUG', 'JWT_PRIVATE_KEY', 'USE_REDIS_CHANNELS',
            'USE_REDIS_CACHE', 'DATA_ENCRYPTION_KEY',
        ):
            env[k] = ''
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


class CertSigningSecretGuardTest(TestCase):
    """Audit Group B (2026-05): production guards on the genetic /
    quantum certificate-signing secrets (finding #3). Mirrors the
    JWT_PRIVATE_KEY / DATA_ENCRYPTION_KEY guard pattern — fail closed
    at module import when DEBUG=False and the env var is unset/blank,
    exempt during DEBUG / TESTING / ``manage.py check``.

    These guards sit LAST in the chain, so every earlier guard
    (JWT_PRIVATE_KEY, DATA_ENCRYPTION_KEY, USE_REDIS_CACHE) must be
    satisfied first or it would intercept these assertions.
    """

    # Satisfies every guard ahead of the cert-secret guards.
    _PRECEDING_GUARDS = {
        'DEBUG': 'False',
        'SECRET_KEY': 'test-secret',
        'JWT_PRIVATE_KEY': 'jwt-secret-material',
        'USE_REDIS_CHANNELS': 'True',
        'USE_REDIS_CACHE': 'True',
        'DATA_ENCRYPTION_KEY': 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=',
    }

    def test_guard_fires_in_production_without_genetic_cert_secret(self):
        """DEBUG=False + every earlier guard satisfied + no
        GENETIC_CERT_SECRET => fail closed."""
        _rc, stdout, stderr = _run_settings_import_in_subprocess({
            **self._PRECEDING_GUARDS,
            'QUANTUM_CERT_SECRET': 'quantum-cert-secret-material',
            # GENETIC_CERT_SECRET intentionally unset
        })
        self.assertIn('SETTINGS_FAILED', stdout + stderr)
        self.assertIn('GENETIC_CERT_SECRET', stdout + stderr)

    def test_guard_fires_in_production_without_quantum_cert_secret(self):
        """GENETIC set so the loop advances to QUANTUM_CERT_SECRET,
        which is the one left unset."""
        _rc, stdout, stderr = _run_settings_import_in_subprocess({
            **self._PRECEDING_GUARDS,
            'GENETIC_CERT_SECRET': 'genetic-cert-secret-material',
            # QUANTUM_CERT_SECRET intentionally unset
        })
        self.assertIn('SETTINGS_FAILED', stdout + stderr)
        self.assertIn('QUANTUM_CERT_SECRET', stdout + stderr)

    def test_guard_fires_with_whitespace_only_cert_secret(self):
        """``.strip()`` normalization — a whitespace-only value reads
        as missing, matching the JWT_PRIVATE_KEY guard."""
        _rc, stdout, stderr = _run_settings_import_in_subprocess({
            **self._PRECEDING_GUARDS,
            'GENETIC_CERT_SECRET': '   ',  # whitespace-only
            'QUANTUM_CERT_SECRET': 'quantum-cert-secret-material',
        })
        self.assertIn('SETTINGS_FAILED', stdout + stderr)
        self.assertIn('GENETIC_CERT_SECRET', stdout + stderr)

    def test_guard_silent_when_both_cert_secrets_set(self):
        """DEBUG=False + both cert secrets set + every other guard
        satisfied => settings load cleanly."""
        _rc, stdout, stderr = _run_settings_import_in_subprocess({
            **self._PRECEDING_GUARDS,
            'GENETIC_CERT_SECRET': 'genetic-cert-secret-material',
            'QUANTUM_CERT_SECRET': 'quantum-cert-secret-material',
        })
        self.assertIn('SETTINGS_LOADED', stdout)

    def test_guard_silent_in_debug_mode(self):
        """Dev mode falls back to SECRET_KEY for cert signing — no
        guard fire even with both secrets unset."""
        _rc, stdout, stderr = _run_settings_import_in_subprocess({
            'DEBUG': 'True',
            'SECRET_KEY': 'dev-secret',
            # cert secrets intentionally unset — dev path
        })
        self.assertIn('SETTINGS_LOADED', stdout)
