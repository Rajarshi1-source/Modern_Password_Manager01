"""
Feature flag settings.

Phase C / C7 (2026-05): organisational facade over the application's
feature-flag surface. The product has accumulated a wide set of
opt-in / staged-rollout flags (ambient biometric fusion, hidden /
steganographic vaults, circadian TOTP, decentralized identity,
honeypot credentials, self-destruct passwords, …). Having them all
re-exported from one module makes "which flag controls X?" answerable
by reading this file rather than searching a 2200-line settings.py.

Definitions remain in ``base.py`` for now (see ``__init__.py``);
this module is the published contract that future PRs will move the
definitions to without changing the import surface.
"""

from .base import (  # noqa: F401
    # Ambient biometric fusion
    AMBIENT_AUTH,
    # Steganographic / hidden vaults
    STEGO_VAULT,
    HIDDEN_VAULT,
    # Smart-contract automation feature flags
    SMART_CONTRACT_UNLOCK_ONCHAIN_ENABLED,
    HONEYPOT_CREDENTIALS_ENABLED,
    SELF_DESTRUCT_PASSWORDS_ENABLED,
    # Circadian TOTP + Decentralized identity
    CIRCADIAN_TOTP_ENABLED,
    DECENTRALIZED_IDENTITY_ENABLED,
    VC_CHAIN_ANCHOR_ENABLED,
    # Personality-based authentication
    PERSONALITY_AUTH_ENABLED,
    PERSONALITY_AUTH_USE_PRESIDIO,
)
