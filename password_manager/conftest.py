"""Project-wide pytest fixtures and patches.

Applied to every test run. Keeps legacy tests working after model / API
changes in the codebase.
"""
from __future__ import annotations

import uuid

import pytest


_PATCH_SENTINEL = "_pwmgr_conftest_patched"


def _patch_user_manager() -> None:
    """Auto-derive ``username`` from ``email`` when tests omit it.

    Many test files predate the switch to email-based identifiers and call
    ``User.objects.create_user(email=..., password=...)``. Django's default
    ``UserManager`` still requires ``username``; rather than rewrite dozens of
    test modules, we patch the manager to fall back to the email local part
    (or a random uuid) when no username is supplied.
    
    The patch is idempotent: re-invocation is a no-op. Without this guard,
    each call would wrap the previous wrapper, building a chain that blows
    the recursion limit once enough tests have run.
    """
    from django.contrib.auth.models import UserManager

    if getattr(UserManager.create_user, _PATCH_SENTINEL, False):
        return
    
    original_create_user = UserManager.create_user
    original_create_superuser = UserManager.create_superuser

    def _derive_username(email: str | None) -> str:
        if email:
            base = email.split('@', 1)[0]
            return f"{base}_{uuid.uuid4().hex[:6]}"
        return f"user_{uuid.uuid4().hex[:10]}"

    def create_user(self, username=None, email=None, password=None, **extra_fields):
        if not username:
            username = _derive_username(email)
        return original_create_user(
            self, username=username, email=email, password=password, **extra_fields
        )

    def create_superuser(self, username=None, email=None, password=None, **extra_fields):
        if not username:
            username = _derive_username(email)
        return original_create_superuser(
            self, username=username, email=email, password=password, **extra_fields
        )

    setattr(create_user, _PATCH_SENTINEL, True)
    setattr(create_superuser, _PATCH_SENTINEL, True)

    UserManager.create_user = create_user
    UserManager.create_superuser = create_superuser


def pytest_configure(config):  # noqa: D401 - pytest hook
    """Apply compatibility patches before tests collect."""
    _patch_user_manager()


@pytest.fixture(autouse=True)
def _ensure_user_manager_patched():
    """Idempotent safety net in case plugins reload the manager module."""
    _patch_user_manager()
    yield


@pytest.fixture(autouse=True)
def _clear_django_caches():
    """Isolate every test from the process-global cache.

    Under ``TESTING`` (``settings/base.py``) both cache aliases are
    ``LocMemCache``, which lives in the pytest process and is never reset
    between tests. Django rolls the DATABASE back per test; it does nothing
    for the cache, so anything written there leaks into every later test in
    the run.

    The concrete failure this fixes: DRF's ``SimpleRateThrottle`` keeps its
    request history in exactly that cache. ``settings/base.py`` already clears
    ``DEFAULT_THROTTLE_CLASSES`` under ``TESTING``, but the recovery views set
    ``throttle_classes`` explicitly (``auth_module/wrapped_dek_view.py``,
    ``recovery_factor_view.py``, ``time_locked_view.py``), so that override
    never reaches them. ``RecoveryThrottle`` allows 3/hour keyed on
    ``<view class>_<user.id>`` -- and on SQLite the PK sequence rolls back with
    each test's transaction, so every test's fresh user gets the SAME id and
    therefore the same throttle bucket. The 4th request in a class was refused
    with a 429, failing six tests in ``auth_module/tests/test_layered_recovery.py``
    that pass individually.

    That the same suite is green on CI is not evidence of isolation: CI runs
    PostgreSQL, whose sequences are non-transactional, so ``nextval`` does not
    roll back and each test happens to land in a different bucket. The
    IP-keyed throttles (``RecoveryInitiateThrottle``,
    ``RecoveryCompleteThrottle``, keyed on ``get_ident`` -- constant
    ``127.0.0.1`` for every test) have no such accidental protection and would
    bite on any backend once enough tests hit them. Clearing the cache fixes
    the class rather than the six symptoms.

    Cleared on BOTH sides: before, so a leak from an earlier test cannot reach
    this one; after, so a test that fails midway cannot leave state behind for
    the next.
    """
    from django.core.cache import caches
    from django.conf import settings

    def _clear_all():
        for alias in settings.CACHES:
            try:
                caches[alias].clear()
            except Exception:  # noqa: BLE001 - a broken alias must not fail tests
                pass

    _clear_all()
    yield
    _clear_all()
