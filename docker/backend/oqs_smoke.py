"""
Build-time smoke test for the liboqs C library + liboqs-python pairing.

Run by docker/backend/Dockerfile in the production stage, against the shipped
venv. CI builds this image but never runs it (see PR #545), so a wrapper that
cannot load the library, a C/Python version drift (ctypes mis-casts), or a
KEM missing from OQS_MINIMAL_BUILD would otherwise only show up in
production. Every failure exits non-zero and fails the image build.

Usage: python oqs_smoke.py <liboqs version> <liboqs-python version>
"""

import ctypes.util
import sys
import warnings

# liboqs-python warns (UserWarning) when the C and Python versions differ
# and when its own package metadata is missing; both are build errors here.
warnings.simplefilter('error', UserWarning)

import oqs  # noqa: E402

EXPECTED_KEMS = {
    # New data: FIPS 203.
    'ML-KEM-512', 'ML-KEM-768', 'ML-KEM-1024',
    # Legacy round-3 Kyber: decrypt-only for data written before ML-KEM, plus
    # LatticeCryptoEngine configurations that name kyber-* explicitly.
    'Kyber512', 'Kyber768', 'Kyber1024',
}
SIZES_768 = (1184, 2400, 1088, 32)  # pk, sk, ct, ss: same for ML-KEM-768 and Kyber768


def fail(message):
    print(f'oqs smoke test FAILED: {message}', file=sys.stderr)
    sys.exit(1)


def round_trip(alg):
    with oqs.KeyEncapsulation(alg) as kem:
        public_key = kem.generate_keypair()
        secret_key = kem.export_secret_key()
    with oqs.KeyEncapsulation(alg) as kem:
        ciphertext, shared_secret = kem.encap_secret(public_key)
    with oqs.KeyEncapsulation(alg, secret_key) as kem:
        if kem.decap_secret(ciphertext) != shared_secret:
            fail(f'{alg}: decapsulation did not reproduce the shared secret')
    return public_key, secret_key, ciphertext, shared_secret


def main(expected_c, expected_py):
    # The backend imports liboqs-python only when this lookup finds the C
    # library (shared/oqs_loader.py), so that it never downloads and builds
    # liboqs at runtime. If the shipped image's loader cache misses it, every
    # PQC path would fail closed in production.
    if not (ctypes.util.find_library('oqs') or ctypes.util.find_library('liboqs')):
        fail('ctypes.util.find_library cannot find liboqs (run ldconfig after copying it)')

    if oqs.oqs_version() != expected_c:
        fail(f'liboqs is {oqs.oqs_version()}, expected {expected_c}')
    if oqs.oqs_python_version() != expected_py:
        fail(f'liboqs-python is {oqs.oqs_python_version()}, expected {expected_py}')

    enabled = set(oqs.get_enabled_kem_mechanisms())
    if enabled != EXPECTED_KEMS:
        fail(
            f'enabled KEMs differ from OQS_MINIMAL_BUILD: missing '
            f'{sorted(EXPECTED_KEMS - enabled)}, unexpected {sorted(enabled - EXPECTED_KEMS)}'
        )

    for alg in sorted(EXPECTED_KEMS):
        material = round_trip(alg)
        if alg in ('ML-KEM-768', 'Kyber768'):
            sizes = tuple(len(x) for x in material)
            if sizes != SIZES_768:
                fail(f'{alg}: sizes {sizes}, expected {SIZES_768}')

    # The two 768 variants must NOT interoperate: a Kyber768 encapsulation
    # to an ML-KEM-768 key does not decapsulate to the same secret. If it
    # did, the backend's per-record KEM labels would be meaningless.
    public_key, secret_key, _, _ = round_trip('ML-KEM-768')
    with oqs.KeyEncapsulation('Kyber768') as kem:
        ciphertext, shared_secret = kem.encap_secret(public_key)
    with oqs.KeyEncapsulation('ML-KEM-768', secret_key) as kem:
        if kem.decap_secret(ciphertext) == shared_secret:
            fail('Kyber768 and ML-KEM-768 interoperated; expected them not to')

    print(
        f'oqs smoke test OK: liboqs {oqs.oqs_version()}, liboqs-python '
        f'{oqs.oqs_python_version()}, KEMs {", ".join(sorted(enabled))}'
    )


if __name__ == '__main__':
    if len(sys.argv) != 3:
        fail('usage: oqs_smoke.py <liboqs version> <liboqs-python version>')
    main(sys.argv[1], sys.argv[2])
