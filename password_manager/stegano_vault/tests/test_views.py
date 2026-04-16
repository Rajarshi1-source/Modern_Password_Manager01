"""API-level tests for ``stegano_vault`` endpoints.

Mounted at ``/api/stego/``. The server treats the opaque blob as
already encrypted client-side, so we only need to verify the HTTP
contract + authorization + feature-flag gating.
"""

from __future__ import annotations

import io

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient


pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    User = get_user_model()
    return User.objects.create_user(username="stego-user", password="pw1234!!")  # nosec


@pytest.fixture
def client(user):
    api = APIClient()
    api.force_authenticate(user=user)
    return api


@pytest.fixture
def anon_client():
    return APIClient()


def _png_bytes(width=32, height=32) -> bytes:
    img = Image.new("RGBA", (width, height), (10, 20, 30, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# /config/
# ---------------------------------------------------------------------------


def test_config_requires_auth(anon_client):
    resp = anon_client.get("/api/stego/config/")
    assert resp.status_code in (401, 403)


def test_config_returns_tier_info(client):
    resp = client.get("/api/stego/config/")
    assert resp.status_code == 200, resp.content
    data = resp.json()
    assert data["enabled"] is True
    assert data["tiers_bytes"] == [32768, 131072, 1048576]
    assert data["format"].startswith("PNG LSB")


# ---------------------------------------------------------------------------
# /embed/ + /extract/
# ---------------------------------------------------------------------------


def test_embed_extract_roundtrip(client):
    cover = _png_bytes(64, 64)
    blob = b"opaque-ciphertext-like-bytes" * 4

    embed_resp = client.post(
        "/api/stego/embed/",
        data={
            "cover": SimpleUploadedFile("cover.png", cover, content_type="image/png"),
            "blob": SimpleUploadedFile("blob.bin", blob, content_type="application/octet-stream"),
        },
        format="multipart",
    )
    assert embed_resp.status_code == 200, embed_resp.content
    assert embed_resp["Content-Type"].startswith("image/png")
    stego_png = b"".join(embed_resp.streaming_content) if hasattr(embed_resp, "streaming_content") else embed_resp.content

    extract_resp = client.post(
        "/api/stego/extract/",
        data={"image": SimpleUploadedFile("stego.png", stego_png, content_type="image/png")},
        format="multipart",
    )
    assert extract_resp.status_code == 200
    recovered = b"".join(extract_resp.streaming_content) if hasattr(extract_resp, "streaming_content") else extract_resp.content
    assert recovered == blob


def test_embed_missing_blob_is_400(client):
    cover = _png_bytes()
    resp = client.post(
        "/api/stego/embed/",
        data={"cover": SimpleUploadedFile("cover.png", cover, content_type="image/png")},
        format="multipart",
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# /store/ + /<id>/ + collection
# ---------------------------------------------------------------------------


def test_store_list_download_delete(client, user):
    stego_png = _png_bytes(48, 48)  # not a real stego image but bytes are opaque to server
    store_resp = client.post(
        "/api/stego/store/",
        data={
            "image": SimpleUploadedFile("stego.png", stego_png, content_type="image/png"),
            "label": "photo-1",
            "tier": "1",
            "cover_hash": "cafef00d" * 8,
        },
        format="multipart",
    )
    assert store_resp.status_code == 201, store_resp.content
    vault_id = store_resp.json()["id"]

    # Collection endpoint
    list_resp = client.get("/api/stego/")
    assert list_resp.status_code == 200
    assert any(v["id"] == vault_id for v in list_resp.json())

    # Download
    dl_resp = client.get(f"/api/stego/{vault_id}/")
    assert dl_resp.status_code == 200
    dl_bytes = b"".join(dl_resp.streaming_content) if hasattr(dl_resp, "streaming_content") else dl_resp.content
    assert dl_bytes == stego_png

    # Delete
    rm_resp = client.delete(f"/api/stego/{vault_id}/")
    assert rm_resp.status_code == 204

    # Gone
    assert client.get(f"/api/stego/{vault_id}/").status_code == 404


def test_store_owned_by_each_user(client, user):
    """A user cannot see another user's stego vaults."""
    User = get_user_model()
    other = User.objects.create_user(username="stego-other", password="pw1234!!")  # nosec
    other_client = APIClient()
    other_client.force_authenticate(user=other)

    stego_png = _png_bytes(32, 32)
    store_resp = client.post(
        "/api/stego/store/",
        data={
            "image": SimpleUploadedFile("mine.png", stego_png, content_type="image/png"),
            "label": "mine",
            "tier": "0",
        },
        format="multipart",
    )
    assert store_resp.status_code == 201
    vault_id = store_resp.json()["id"]

    # Other user sees an empty collection
    assert other_client.get("/api/stego/").json() == []
    # And cannot download or delete the target vault.
    assert other_client.get(f"/api/stego/{vault_id}/").status_code == 404
    assert other_client.delete(f"/api/stego/{vault_id}/").status_code == 404


def test_events_endpoint_reflects_operations(client):
    stego_png = _png_bytes()
    client.post(
        "/api/stego/store/",
        data={
            "image": SimpleUploadedFile("ev.png", stego_png, content_type="image/png"),
            "label": "ev",
            "tier": "0",
        },
        format="multipart",
    )
    resp = client.get("/api/stego/events/")
    assert resp.status_code == 200
    kinds = [ev["kind"] for ev in resp.json()]
    assert "store" in kinds
