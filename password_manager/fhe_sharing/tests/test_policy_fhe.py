"""
Unit tests for `fhe_sharing.services.policy_fhe_service`.

Policy gates must degrade to `allowed=True` when TenSEAL is not
installed so the PRE-backed autofill path is never blocked in dev.
"""

from fhe_sharing.services.policy_fhe_service import (
    PolicyDecision,
    PolicyFheService,
    get_policy_fhe_service,
)


def test_singleton():
    a = get_policy_fhe_service()
    b = get_policy_fhe_service()
    assert a is b


def test_strength_threshold_degrades_to_permit_when_no_cipher():
    svc = PolicyFheService()
    decision = svc.check_strength_threshold(encrypted_length=None, threshold=12)
    assert isinstance(decision, PolicyDecision)
    assert decision.allowed is True
    assert decision.gate == "strength_threshold"
    assert decision.reason in {"fhe_policy_unavailable", "ok_stub"}


def test_breach_distance_degrades_to_permit_when_no_cipher():
    svc = PolicyFheService()
    decision = svc.check_breach_distance(encrypted_distance=None, min_distance=3)
    assert decision.allowed is True
    assert decision.gate == "breach_distance"


def test_strength_threshold_with_bytes_input_doesnt_leak_plaintext():
    svc = PolicyFheService()
    decision = svc.check_strength_threshold(
        encrypted_length=b"\x00" * 64,
        threshold=8,
    )
    assert decision.allowed is True
    assert "password" not in decision.reason.lower()
