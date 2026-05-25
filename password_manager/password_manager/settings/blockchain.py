"""
Blockchain-related settings.

Phase C / C7 (2026-05): organisational facade over the blockchain
configuration. The goal is so that "where do I configure the
BLOCKCHAIN_ANCHORING dict / smart-contract addresses / key provider?"
has one obvious answer: this module.

The actual symbol definitions stay in ``base.py`` for now (see
``__init__.py`` for the rationale). This module re-exports the public
surface so callers can write::

    from password_manager.settings.blockchain import BLOCKCHAIN_ANCHORING

without first knowing what file the symbol physically lives in. A
future PR may move definitions into this module; the re-export list
below is the published contract.

Also defined here (NEW in Phase C / C6): ``BLOCKCHAIN_PROOF_VERIFY_SAMPLE``
— the per-run cap on Merkle proofs the ``verify_random_proofs`` Celery
beat task spot-checks against the on-chain ``verifyCommitment`` view.
Kept low because each proof costs one RPC round-trip; the daily run
just needs to be a tripwire, not an exhaustive sweep.
"""

import os

from .base import (  # noqa: F401
    BLOCKCHAIN_KEY_PROVIDER,
    BLOCKCHAIN_KMS_KEY_ID,
    BLOCKCHAIN_ANCHORING,
    SMART_CONTRACT_AUTOMATION,
    SMART_CONTRACT_UNLOCK_ONCHAIN_ENABLED,
)

# Phase C / C6: number of random proofs to verify per beat-task run.
# Set via env var BLOCKCHAIN_PROOF_VERIFY_SAMPLE; default 50.
BLOCKCHAIN_PROOF_VERIFY_SAMPLE = int(
    os.environ.get('BLOCKCHAIN_PROOF_VERIFY_SAMPLE', '50')
)
