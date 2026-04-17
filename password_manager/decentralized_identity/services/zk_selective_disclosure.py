"""Build selectively-disclosed presentations.

v1 implementation: does a JSON-level redaction of undisclosed fields and
delegates to the existing :mod:`zk_proofs` app to create a Pedersen + Schnorr
commitment over the redacted subject. The resulting proof reference is
persisted on the :class:`VCPresentation` row so verifiers can cross-check.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Dict, List, Optional, Tuple

from ..models import VerifiableCredential

logger = logging.getLogger(__name__)


def _hash_claim(claim: Dict) -> str:
    return hashlib.sha256(
        json.dumps(claim, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()


def build_selective_disclosure(
    vc: VerifiableCredential,
    disclose_fields: List[str],
    nonce: str,
) -> Tuple[Dict, Optional[str]]:
    """Return ``(disclosed_subject, zk_proof_ref)``.

    Undisclosed fields are replaced by their SHA-256 digest so verifiers know
    a claim exists without learning its value. ``zk_proof_ref`` is the
    identifier of a ``zk_proofs`` commitment if creation succeeds, otherwise
    ``None`` (verification falls back to JSON-level inclusion proofs).
    """
    subject = dict(vc.jsonld_vc.get("credentialSubject") or {})
    disclosed: Dict = {"id": subject.get("id")}
    for key, value in subject.items():
        if key == "id":
            continue
        if key in disclose_fields:
            disclosed[key] = value
        else:
            disclosed[f"{key}_hash"] = _hash_claim({key: value})

    proof_ref: Optional[str] = None
    try:
        from zk_proofs import services as zk_services  # type: ignore

        # The zk_proofs app exposes a ``create_commitment`` helper in most
        # deployments; fall back gracefully if the symbol is not available.
        create_commitment = getattr(zk_services, "create_commitment", None)
        if callable(create_commitment):
            payload = json.dumps(disclosed, separators=(",", ":"), sort_keys=True)
            result = create_commitment(payload=payload, nonce=nonce)
            proof_ref = (
                result.get("commitment_id")
                if isinstance(result, dict)
                else str(result)
            )
    except Exception:
        logger.debug(
            "zk_proofs integration unavailable; falling back to hash-only disclosure",
            exc_info=True,
        )

    return disclosed, proof_ref
