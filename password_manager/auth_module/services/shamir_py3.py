"""Pure Python 3 Shamir Secret Sharing.

Implements ``PlaintextToHexSecretSharer``-compatible split/recover for a
hex-encoded plaintext secret over GF(p) where p is the 521-bit Mersenne prime
(2^521 - 1). This replaces the unmaintained ``secretsharing`` package which
uses the Python 2-only ``long`` built-in.

API intentionally mirrors ``secretsharing.PlaintextToHexSecretSharer``:

    shares = ShamirSecretSharer.split_secret(secret_hex, threshold, n)
    secret_hex = ShamirSecretSharer.recover_secret(shares[:threshold])

Each share is a string ``"<index>-<hex_data>"``.
"""

import secrets as _secrets
from functools import reduce as _reduce

# 2^521 - 1, the 13th Mersenne prime (521 bits).
# Accommodates secrets up to 520 bits (~65 bytes) which exceeds any realistic
# private key or passphrase. This replaces the 127-bit prime that was too
# small for 256-bit (and larger) secrets.
_PRIME = (1 << 521) - 1


def _eval_poly(coeffs, x, prime):
    """Horner's method: evaluate polynomial with given coefficients at x mod prime."""
    acc = 0
    for c in reversed(coeffs):
        acc = (acc * x + c) % prime
    return acc


def _lagrange_interpolate(x, x_s, y_s, prime):
    """Lagrange interpolation: recover f(x) given points (x_s, y_s) mod prime."""
    k = len(x_s)
    assert k == len(y_s)

    def _PI(vals):
        return _reduce(lambda a, b: a * b % prime, vals, 1)

    nums = []
    dens = []
    for i in range(k):
        others = [x_s[j] for j in range(k) if j != i]
        nums.append(_PI([(x - o) % prime for o in others]))
        dens.append(_PI([(x_s[i] - o) % prime for o in others]))

    den = _PI(dens)
    # Combine via CRT / Fermat's little theorem (inverse mod prime)
    num = sum(
        _lagrange_basis(nums[i], dens[i], y_s[i], prime) for i in range(k)
    ) % prime
    return (num * pow(den, prime - 2, prime)) % prime


def _lagrange_basis(num_i, den_i, y_i, prime):
    return num_i * pow(den_i, prime - 2, prime) * y_i % prime


def _split(secret_int, threshold, n, prime):
    if threshold > n:
        raise ValueError("threshold must be <= n")
    coeffs = [secret_int] + [
        int.from_bytes(_secrets.token_bytes(16), 'big') % prime
        for _ in range(threshold - 1)
    ]
    points = [(i, _eval_poly(coeffs, i, prime)) for i in range(1, n + 1)]
    return points


def _recover(points, prime):
    x_s = [p[0] for p in points]
    y_s = [p[1] for p in points]
    return _lagrange_interpolate(0, x_s, y_s, prime)


class ShamirSecretSharer:
    """
    Drop-in replacement for ``secretsharing.PlaintextToHexSecretSharer``.

    All secrets are hex strings; shares are ``"<int_index>-<hex_value>"``.
    """

    @staticmethod
    def split_secret(secret_hex: str, threshold: int, n: int) -> list[str]:
        """Split *secret_hex* into *n* shares, *threshold* needed to recover."""
        secret_int = int(secret_hex, 16)
        prime = _PRIME
        if secret_int >= prime:
            raise ValueError(
                f"Secret {secret_int.bit_length()} bits >= prime {prime.bit_length()} bits; "
                "use a larger prime or a shorter secret"
            )
        points = _split(secret_int, threshold, n, prime)
        return [f"{x}-{y:x}" for x, y in points]

    @staticmethod
    def recover_secret(shares: list[str]) -> str:
        """Recover the hex secret from *threshold* or more shares."""
        points = []
        for share in shares:
            idx_s, val_s = share.split('-', 1)
            points.append((int(idx_s), int(val_s, 16)))
        value = _recover(points, _PRIME)
        # Preserve even number of hex digits so bytes.fromhex works.
        h = f"{value:x}"
        if len(h) % 2:
            h = '0' + h
        return h
