"""API-level tests for ambient_auth endpoints."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient


pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    User = get_user_model()
    u = User.objects.create_user(username="ambient-user", password="pw1234!!")  # nosec
    return u


@pytest.fixture
def client(user):
    api = APIClient()
    api.force_authenticate(user=user)
    return api


def _payload():
    return {
        "surface": "web",
        "schema_version": 1,
        "device_fp": "fp-xyz",
        "local_salt_version": 1,
        "signal_availability": {"ambient_light": True, "network_class": True},
        "coarse_features": {"light_bucket": "indoor", "connection_class": "wifi"},
        "embedding_digest": "bb" * 16,
    }


def test_ingest_endpoint_succeeds(client):
    resp = client.post(
        "/api/ambient/ingest/",
        data=_payload(),
        format="json",
    )
    assert resp.status_code in (200, 201), resp.data


def test_ingest_rejects_raw_wifi_bssids(client):
    bad = _payload()
    bad["coarse_features"]["wifi_bssids"] = [
        "AA:BB:CC:DD:EE:01",
        "AA:BB:CC:DD:EE:02",
        "AA:BB:CC:DD:EE:03",
        "AA:BB:CC:DD:EE:04",
        "AA:BB:CC:DD:EE:05",
    ]
    resp = client.post("/api/ambient/ingest/", data=bad, format="json")
    assert resp.status_code in (400, 422), resp.data


def test_requires_auth():
    api = APIClient()
    resp = api.post("/api/ambient/ingest/", data=_payload(), format="json")
    assert resp.status_code in (401, 403)


def test_contexts_list_empty_initially(client):
    resp = client.get("/api/ambient/contexts/")
    assert resp.status_code == 200
    assert isinstance(resp.data, list)


def test_config_endpoint(client):
    resp = client.get("/api/ambient/config/")
    assert resp.status_code == 200
    assert "enabled" in resp.data
