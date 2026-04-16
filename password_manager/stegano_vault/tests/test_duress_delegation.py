"""End-to-end test for the duress-code -> stego-vault delegation path.

The story we assert:

1. User encodes a ``HiddenVaultBlob`` with ``decoy_password`` and a
   JSON decoy payload, then LSB-embeds it into a PNG.
2. A ``StegoVault`` row is created holding those PNG bytes.
3. A ``DuressCode`` row is created, flagged
   ``delegate_to_hidden_vault=True`` and linked to the stego vault.
4. ``DuressCodeService.activate_duress_mode`` is called with the
   same decoy password as ``unlock_password``.
5. The returned ``decoy_vault`` dict must carry ``source="hidden_vault"``
   and the items list we encoded.
"""

from __future__ import annotations

import io
import json

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from PIL import Image

from hidden_vault import TIERS, encode as hv_encode
from stegano_vault.models import StegoVault
from stegano_vault.services import embed_blob_in_png
from security.models.duress_models import DuressCode, DuressCodeConfiguration
from security.services.duress_code_service import DuressCodeService


pytestmark = pytest.mark.django_db


# Argon2 parameters tuned way down so the unit test stays fast
# regardless of host. They match the same knobs the service writes
# into the blob header, so decode() on the same password succeeds.
FAST_KDF = {"kdf_time": 1, "kdf_mem_kib": 1024, "kdf_par": 1}


def _make_cover_png(width=256, height=256) -> bytes:
    """Produce a cover PNG large enough to fit a TIER0 hidden vault."""
    img = Image.new("RGBA", (width, height))
    pixels = []
    for y in range(height):
        for x in range(width):
            pixels.append(((x * 3) % 256, (y * 5) % 256, ((x * y) % 256), 255))
    img.putdata(pixels)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def user():
    User = get_user_model()
    return User.objects.create_user(username="duress-stego", password="pw1234!!")  # nosec


def test_duress_activation_pulls_decoy_from_stego_vault(user):
    decoy_password = "F4keP@ss"
    decoy_payload = {
        "items": [
            {"name": "public-email", "secret": "hunter2"},
            {"name": "throwaway-social", "secret": "hunter3"},
        ]
    }

    # 1. Encode the hidden-vault blob (decoy only, no real slot).
    blob = hv_encode(
        decoy_password=decoy_password,
        decoy_payload=json.dumps(decoy_payload).encode("utf-8"),
        tier=TIERS.TIER0_32K,
        **FAST_KDF,
    )

    # 2. Embed into a PNG cover + persist as StegoVault.
    # TIER0 is 32 KiB; at 3 bits/pixel we need >= ~87,381 pixels => 320*320 is safe.
    cover = _make_cover_png(320, 320)
    stego_png = embed_blob_in_png(cover, blob)

    sv = StegoVault.objects.create(
        user=user,
        label="test-stego",
        image_mime="image/png",
        blob_size_tier=0,
    )
    sv.image.save(f"{sv.id}.png", ContentFile(stego_png), save=True)

    # 3. Configure + create a duress code delegating to it.
    DuressCodeConfiguration.objects.create(user=user, is_enabled=True)
    duress = DuressCode.objects.create(
        user=user,
        code_hash="placeholder",  # irrelevant here: we bypass matching
        threat_level="medium",
        delegate_to_hidden_vault=True,
        hidden_vault_slot=1,
        stego_vault=sv,
        action_config={
            "show_decoy": True,
            "preserve_evidence": False,
            "alert_authorities": False,
        },
    )

    # 4. Activate duress mode with the decoy password as unlock_password.
    service = DuressCodeService()
    result = service.activate_duress_mode(
        user=user,
        duress_code=duress,
        request_context={"ip_address": "127.0.0.1"},  # nosec B104
        is_test=True,
        unlock_password=decoy_password,
    )

    assert result["activated"] is True
    assert result["decoy_vault"] is not None, result
    decoy = result["decoy_vault"]
    assert decoy.get("source") == "hidden_vault", decoy
    assert decoy.get("slot_index") == 1
    names = [item["name"] for item in decoy.get("items", [])]
    assert "public-email" in names
    assert "throwaway-social" in names


def test_duress_activation_falls_back_when_password_wrong(user):
    """If the unlock_password does not decrypt the hidden vault we should
    fall back to the legacy DecoyVault path instead of surfacing an error."""
    blob = hv_encode(
        decoy_password="the-real-one",
        decoy_payload=b'{"items":[]}',
        tier=TIERS.TIER0_32K,
        **FAST_KDF,
    )
    cover = _make_cover_png(320, 320)
    stego_png = embed_blob_in_png(cover, blob)

    sv = StegoVault.objects.create(user=user, label="wrong-pass", blob_size_tier=0)
    sv.image.save(f"{sv.id}.png", ContentFile(stego_png), save=True)

    DuressCodeConfiguration.objects.create(user=user, is_enabled=True)
    duress = DuressCode.objects.create(
        user=user,
        code_hash="placeholder",
        threat_level="medium",
        delegate_to_hidden_vault=True,
        hidden_vault_slot=1,
        stego_vault=sv,
        action_config={
            "show_decoy": True,
            "preserve_evidence": False,
            "alert_authorities": False,
        },
    )

    service = DuressCodeService()
    result = service.activate_duress_mode(
        user=user,
        duress_code=duress,
        request_context={"ip_address": "127.0.0.1"},  # nosec B104
        is_test=True,
        unlock_password="definitely-not-the-password",
    )

    assert result["activated"] is True
    decoy = result["decoy_vault"]
    # Legacy fallback: we should *not* have source="hidden_vault"
    assert decoy is None or decoy.get("source") != "hidden_vault"
