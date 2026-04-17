"""Celery tasks for decentralized_identity."""

from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .models import RevocationList, VerifiableCredential
from .services.storage import (
    anchor_commitment,
    upload_to_arweave,
    upload_to_ipfs,
)

logger = logging.getLogger(__name__)


@shared_task(name="decentralized_identity.pin_vc_to_ipfs")
def pin_vc_to_ipfs(vc_id: str) -> dict:
    try:
        vc = VerifiableCredential.objects.get(pk=vc_id)
    except VerifiableCredential.DoesNotExist:
        return {"ok": False, "error": "not found"}
    cid = upload_to_ipfs(vc.jsonld_vc, str(vc.id))
    if cid:
        refs = dict(vc.storage_refs or {})
        refs["ipfs_cid"] = cid
        vc.storage_refs = refs
        vc.save(update_fields=["storage_refs"])
    return {"ok": cid is not None, "cid": cid}


@shared_task(name="decentralized_identity.upload_vc_to_arweave")
def upload_vc_to_arweave(vc_id: str) -> dict:
    try:
        vc = VerifiableCredential.objects.get(pk=vc_id)
    except VerifiableCredential.DoesNotExist:
        return {"ok": False, "error": "not found"}
    tx = upload_to_arweave(vc.jsonld_vc, str(vc.id))
    if tx:
        refs = dict(vc.storage_refs or {})
        refs["arweave_tx"] = tx
        vc.storage_refs = refs
        vc.save(update_fields=["storage_refs"])
    return {"ok": tx is not None, "tx": tx}


@shared_task(name="decentralized_identity.anchor_vc_on_chain")
def anchor_vc_on_chain(vc_id: str) -> dict:
    try:
        vc = VerifiableCredential.objects.get(pk=vc_id)
    except VerifiableCredential.DoesNotExist:
        return {"ok": False, "error": "not found"}
    tx = anchor_commitment(vc.jwt_vc, str(vc.id))
    if tx:
        refs = dict(vc.storage_refs or {})
        refs["chain_anchor_tx"] = tx
        vc.storage_refs = refs
        vc.save(update_fields=["storage_refs"])
    return {"ok": tx is not None, "tx": tx}


@shared_task(name="decentralized_identity.fanout_vc_storage")
def fanout_vc_storage(vc_id: str) -> dict:
    """Fan out all storage backends on issuance."""
    return {
        "ipfs": pin_vc_to_ipfs(vc_id),
        "arweave": upload_vc_to_arweave(vc_id),
        "chain": anchor_vc_on_chain(vc_id),
    }


@shared_task(name="decentralized_identity.rebuild_status_list")
def rebuild_status_list(list_id: str = "default") -> dict:
    """Rebuild a StatusList2021-compatible bitstring of revoked VCs."""
    rl, _ = RevocationList.objects.get_or_create(
        list_id=list_id, defaults={"size": 131072}
    )
    size = rl.size
    bits = bytearray((size + 7) // 8)
    for vc in VerifiableCredential.objects.exclude(revocation_list_index=None):
        idx = int(vc.revocation_list_index)
        if idx >= size:
            continue
        if vc.status != "active":
            bits[idx // 8] |= 1 << (idx % 8)
    import base64
    import gzip

    encoded = base64.b64encode(gzip.compress(bytes(bits))).decode("ascii")
    rl.encoded_list = encoded
    rl.save(update_fields=["encoded_list", "updated_at"])
    return {"size": size, "bytes": len(bits)}


@shared_task(name="decentralized_identity.rotate_issuer_key")
def rotate_issuer_key() -> dict:
    """Mark the current issuer key as rotated and mint a fresh one."""
    from .models import IssuerKey
    from .services.did_service import ensure_issuer_key

    active = IssuerKey.objects.filter(is_active=True).first()
    if active is not None:
        active.is_active = False
        active.rotated_at = timezone.now()
        active.save(update_fields=["is_active", "rotated_at"])
    new = ensure_issuer_key()
    return {"new_kid": new.kid}
