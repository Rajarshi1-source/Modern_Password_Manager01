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
