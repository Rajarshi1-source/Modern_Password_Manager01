"""
Unit tests for `fhe_sharing.services.pre_service`.

If pyUmbral isn't installed we only exercise the graceful-fallback
paths. When it IS installed we run a full roundtrip.
"""

import pytest

from fhe_sharing.services.pre_service import (
    PreService,
    UmbralUnavailableError,
    ReencryptionError,
    get_pre_service,
    is_available,
)


def test_singleton_returns_same_instance():
    a = get_pre_service()
    b = get_pre_service()
    assert a is b
    assert isinstance(a, PreService)


def test_suite_constant():
    svc = PreService()
    assert svc.SUITE == "umbral-v1"


def test_reencrypt_raises_when_umbral_unavailable(monkeypatch):
    import fhe_sharing.services.pre_service as mod

    monkeypatch.setattr(mod, "_UMBRAL_AVAILABLE", False)
    svc = PreService()
    with pytest.raises(UmbralUnavailableError):
        svc.reencrypt(b"capsule", b"kfrag")


def test_verify_kfrag_raises_when_umbral_unavailable(monkeypatch):
    import fhe_sharing.services.pre_service as mod

    monkeypatch.setattr(mod, "_UMBRAL_AVAILABLE", False)
    svc = PreService()
    with pytest.raises(UmbralUnavailableError):
        svc.verify_kfrag(b"kf", b"pk", b"pk", b"pk")


def test_wrap_result_roundtrip():
    svc = PreService()
    r = svc.wrap_result(b"cap", b"ct", b"cf")
    assert r.capsule == b"cap"
    assert r.ciphertext == b"ct"
    assert r.cfrag == b"cf"


# ------------------------------------------------------------------ #
# Real pyUmbral roundtrip — skipped if library is not installed.      #
# ------------------------------------------------------------------ #

_skip_if_no_umbral = pytest.mark.skipif(
    not is_available(),
    reason="pyUmbral is not installed",
)


@_skip_if_no_umbral
def test_real_umbral_roundtrip():
    import umbral

    sk_o = umbral.SecretKey.random()
    pk_o = sk_o.public_key()
    sk_signer = umbral.SecretKey.random()
    signer = umbral.Signer(sk_signer)
    verifying_pk = sk_signer.public_key()

    sk_r = umbral.SecretKey.random()
    pk_r = sk_r.public_key()

    plaintext = b"super-secret-p@ssword"
    capsule, ciphertext = umbral.encrypt(pk_o, plaintext)

    kfrags = umbral.generate_kfrags(
        delegating_sk=sk_o,
        receiving_pk=pk_r,
        signer=signer,
        threshold=1,
        shares=1,
    )
    kfrag = kfrags[0]

    svc = PreService()
    cfrag_bytes = svc.reencrypt(
        capsule_bytes=bytes(capsule),
        kfrag_bytes=bytes(kfrag),
    )
    assert isinstance(cfrag_bytes, bytes) and len(cfrag_bytes) > 0

    cfrag = umbral.CapsuleFrag.from_bytes(cfrag_bytes)
    verified = cfrag.verify(
        capsule=capsule,
        verifying_pk=verifying_pk,
        delegating_pk=pk_o,
        receiving_pk=pk_r,
    )
    recovered = umbral.decrypt_reencrypted(
        receiving_sk=sk_r,
        delegating_pk=pk_o,
        capsule=capsule,
        verified_cfrags=[verified],
        ciphertext=ciphertext,
    )
    assert recovered == plaintext


@_skip_if_no_umbral
def test_real_umbral_verify_kfrag_positive():
    import umbral

    sk_o = umbral.SecretKey.random()
    pk_o = sk_o.public_key()
    sk_signer = umbral.SecretKey.random()
    signer = umbral.Signer(sk_signer)
    verifying_pk = sk_signer.public_key()
    sk_r = umbral.SecretKey.random()
    pk_r = sk_r.public_key()

    kfrag = umbral.generate_kfrags(
        delegating_sk=sk_o,
        receiving_pk=pk_r,
        signer=signer,
        threshold=1,
        shares=1,
    )[0]

    svc = PreService()
    assert svc.verify_kfrag(
        kfrag_bytes=bytes(kfrag),
        delegating_pk_bytes=bytes(pk_o),
        receiving_pk_bytes=bytes(pk_r),
        verifying_pk_bytes=bytes(verifying_pk),
    ) is True


@_skip_if_no_umbral
def test_real_umbral_verify_kfrag_mismatched_keys_rejected():
    import umbral

    sk_o = umbral.SecretKey.random()
    sk_signer = umbral.SecretKey.random()
    signer = umbral.Signer(sk_signer)
    sk_r = umbral.SecretKey.random()
    pk_r = sk_r.public_key()

    kfrag = umbral.generate_kfrags(
        delegating_sk=sk_o,
        receiving_pk=pk_r,
        signer=signer,
        threshold=1,
        shares=1,
    )[0]

    wrong_pk = umbral.SecretKey.random().public_key()
    svc = PreService()
    assert svc.verify_kfrag(
        kfrag_bytes=bytes(kfrag),
        delegating_pk_bytes=bytes(wrong_pk),
        receiving_pk_bytes=bytes(pk_r),
        verifying_pk_bytes=bytes(sk_signer.public_key()),
    ) is False
