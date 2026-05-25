"""
Settings package entry point.

Phase C / C7 (2026-05): the historical 2200-line ``settings.py`` was
split into a package. ``DJANGO_SETTINGS_MODULE=password_manager.settings``
still works because Python resolves the package's ``__init__`` module.

Layout:
    base.py        — Django essentials (everything that was in settings.py).
    security.py    — Sentry, CSRF, security middleware, Argon2 params.
    blockchain.py  — BLOCKCHAIN_ANCHORING, SMART_CONTRACT_AUTOMATION,
                     BLOCKCHAIN_KEY_PROVIDER, blockchain feature flags.
    features.py    — Application feature flags (ambient auth, hidden vault,
                     stego vault, circadian TOTP, decentralized identity,
                     etc.).

The split is INCREMENTAL: this PR delivers the package skeleton plus a
documented surface for the named modules. Each named module currently
re-exports the relevant symbols from ``base`` so callers can write
``from password_manager.settings.blockchain import BLOCKCHAIN_ANCHORING``
without first knowing where the symbol lived in the legacy file. Future
PRs may move definitions physically into the named modules; doing so
will not change the import surface published here.

Order is fixed: ``base`` MUST be imported first because the other
modules read settings that ``base`` defines. The ``from .base import *``
below also publishes those same symbols at the package top level, so
``settings.DEBUG`` continues to resolve the way Django expects.
"""

# Star-imports are intentional — Django reads attributes off the settings
# module, so every public name in ``base`` must be reachable as
# ``password_manager.settings.<NAME>``.
from .base import *  # noqa: F401,F403

# Named modules re-export selected groups for organisational clarity.
# These imports execute AFTER ``base`` is fully loaded, so they can read
# any base-level symbol via ``from .base import X``. None of them should
# mutate symbols that ``base`` already defined.
from .security import *  # noqa: E402,F401,F403
from .blockchain import *  # noqa: E402,F401,F403
from .features import *  # noqa: E402,F401,F403
