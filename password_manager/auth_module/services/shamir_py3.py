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

    total = 0
    for i in range(k):
        num = 1
        den = 1
        for j in range(k):
            if j == i:
                continue
            num = (num * ((x - x_s[j]) % prime)) % prime
            den = (den * ((x_s[i] - x_s[j]) % prime)) % prime
        # Lagrange basis L_i(x) = num / den (mod prime)
        basis = (num * pow(den, prime - 2, prime)) % prime
        total = (total + y_s[i] * basis) % prime
    return total


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


# Each chunk fits safely in ``_PRIME`` (520 bits → 64 bytes → 128 hex chars).
# We split large secrets into fixed-size chunks so they fit in the field.
_CHUNK_HEX_LEN = 128


class ShamirSecretSharer:
    """
    Drop-in replacement for ``secretsharing.PlaintextToHexSecretSharer``.

    Shares encode the original hex length so arbitrarily-long secrets can be
    faithfully reconstructed regardless of leading zeros.  The on-wire format
    is ``"<index>-<total_hex_len>:<chunk_hex_1>.<chunk_hex_2>..."``.  Legacy
    single-chunk shares (``"<index>-<hex>"``) remain parseable.
    """

    @staticmethod
    def _chunk_hex(secret_hex: str) -> list[str]:
        """Pad and split the secret hex into ``_CHUNK_HEX_LEN``-sized blocks."""
        if len(secret_hex) % 2:
            secret_hex = '0' + secret_hex
        if not secret_hex:
            return ['']
        chunks: list[str] = []
        for i in range(0, len(secret_hex), _CHUNK_HEX_LEN):
            chunks.append(secret_hex[i:i + _CHUNK_HEX_LEN])
        return chunks

    @staticmethod
    def split_secret(secret_hex: str, threshold: int, n: int) -> list[str]:
        """Split *secret_hex* into *n* shares, *threshold* needed to recover."""
        prime = _PRIME
        # Normalize to even length so round-tripping via bytes.fromhex works.
        if len(secret_hex) % 2:
            secret_hex = '0' + secret_hex
        chunks = ShamirSecretSharer._chunk_hex(secret_hex)
        total_hex_len = len(secret_hex)

        per_chunk_points: list[list[tuple[int, int]]] = []
        for chunk in chunks:
            secret_int = int(chunk, 16) if chunk else 0
            if secret_int >= prime:
                raise ValueError(
                    f"Chunk {secret_int.bit_length()} bits >= prime {prime.bit_length()} bits"
                )
            per_chunk_points.append(_split(secret_int, threshold, n, prime))

        shares: list[str] = []
        for i in range(n):
            idx = i + 1
            parts = []
            for chunk_points in per_chunk_points:
                _, y = chunk_points[i]
                parts.append(f"{y:x}")
            shares.append(f"{idx}-{total_hex_len:x}:" + '.'.join(parts))
        return shares

    @staticmethod
    def recover_secret(shares: list[str]) -> str:
        """Recover the hex secret from *threshold* or more shares."""
        parsed: list[tuple[int, int, list[int]]] = []
        for share in shares:
            idx_s, payload = share.split('-', 1)
            if ':' in payload:
                length_hex, chunks_str = payload.split(':', 1)
                total_hex_len = int(length_hex, 16)
                chunk_strs = chunks_str.split('.') if '.' in chunks_str else [chunks_str]
            else:
                # Legacy single-chunk format; we will size output after recovery.
                total_hex_len = -1
                chunk_strs = [payload]
            chunk_ints = [int(c, 16) for c in chunk_strs]
            parsed.append((int(idx_s), total_hex_len, chunk_ints))

        chunk_count = max(len(chunks) for _, _, chunks in parsed)
        total_hex_len = max(length for _, length, _ in parsed)

        out_hex_chunks: list[str] = []
        for chunk_idx in range(chunk_count):
            points = []
            for idx, _, chunks in parsed:
                if chunk_idx < len(chunks):
                    points.append((idx, chunks[chunk_idx]))
            value = _recover(points, _PRIME)
            h = f"{value:x}"

            # For a chunk before the last one, pad to full chunk width so byte
            # alignment is preserved.  The last chunk consumes whatever hex
            # length remains in ``total_hex_len``.
            if total_hex_len > 0 and chunk_idx < chunk_count - 1:
                target = _CHUNK_HEX_LEN
            elif total_hex_len > 0:
                remaining = total_hex_len - _CHUNK_HEX_LEN * (chunk_count - 1)
                target = max(remaining, 0)
            else:
                target = len(h) + (len(h) % 2)

            if len(h) < target:
                h = '0' * (target - len(h)) + h
            if len(h) % 2:
                h = '0' + h
            out_hex_chunks.append(h)

        result = ''.join(out_hex_chunks)
        if len(result) % 2:
            result = '0' + result
        return result
