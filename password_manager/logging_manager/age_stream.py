"""
Streaming encryption to an age X25519 recipient (https://age-encryption.org/v1).

Database backups are encrypted to a PUBLIC key (``age1...``) so the cluster
that writes them never holds the key that reads them. The output is a
standard age file: decrypt it anywhere with ``age -d -i key.txt`` or rage.

Only what the backup needs is implemented: one X25519 recipient, binary
(not armored) output, and the matching decryptor for the restore drill.
Built on ``cryptography`` (already pinned), so no new dependency.
"""

import base64
import hashlib
import hmac
import os

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

VERSION_LINE = b'age-encryption.org/v1'
X25519_LABEL = b'age-encryption.org/v1/X25519'
CHUNK = 64 * 1024
_TAG = 16
_RAW = serialization.Encoding.Raw, serialization.PublicFormat.Raw


class AgeError(ValueError):
    pass


# ---------------------------------------------------------------- bech32 (BIP 173)

_CHARSET = 'qpzry9x8gf2tvdw0s3jn54khce6mua7l'
_GEN = (0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3)


def _polymod(values):
    chk = 1
    for v in values:
        top = chk >> 25
        chk = (chk & 0x1ffffff) << 5 ^ v
        for i in range(5):
            chk ^= _GEN[i] if (top >> i) & 1 else 0
    return chk


def _hrp_expand(hrp):
    return [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp]


def _convertbits(data, frombits, tobits, pad):
    acc = bits = 0
    out = []
    maxv = (1 << tobits) - 1
    for value in data:
        acc = (acc << frombits) | value
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            out.append((acc >> bits) & maxv)
    if pad and bits:
        out.append((acc << (tobits - bits)) & maxv)
    elif not pad and (bits >= frombits or (acc << (tobits - bits)) & maxv):
        raise AgeError('invalid bech32 padding')
    return out


def bech32_decode(text, expected_hrp):
    if text.lower() != text and text.upper() != text:
        raise AgeError('mixed-case bech32')
    text = text.lower()
    hrp, sep, data = text.rpartition('1')
    if not sep or hrp != expected_hrp.lower() or len(data) < 6:
        raise AgeError(f'expected a {expected_hrp} bech32 string')
    try:
        values = [_CHARSET.index(c) for c in data]
    except ValueError:
        raise AgeError('invalid bech32 character') from None
    if _polymod(_hrp_expand(hrp) + values) != 1:
        raise AgeError('bad bech32 checksum')
    return bytes(_convertbits(values[:-6], 5, 8, False))


def bech32_encode(hrp, payload):
    data = _convertbits(payload, 8, 5, True)
    polymod = _polymod(_hrp_expand(hrp) + data + [0] * 6) ^ 1
    checksum = [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]
    return hrp + '1' + ''.join(_CHARSET[d] for d in data + checksum)


# ---------------------------------------------------------------- keys

def parse_recipient(recipient: str) -> X25519PublicKey:
    key = bech32_decode(recipient.strip(), 'age')
    if len(key) != 32:
        raise AgeError('age recipient must be 32 bytes')
    return X25519PublicKey.from_public_bytes(key)


def parse_identity(text: str) -> X25519PrivateKey:
    """Accept an ``AGE-SECRET-KEY-1...`` line or an age-keygen key file."""
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            key = bech32_decode(line, 'AGE-SECRET-KEY-')
            if len(key) != 32:
                raise AgeError('age identity must be 32 bytes')
            return X25519PrivateKey.from_private_bytes(key)
    raise AgeError('no age identity found')


def generate_identity():
    """(identity_string, recipient_string), like ``age-keygen``. For tests and docs."""
    private = X25519PrivateKey.generate()
    secret = private.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                                   serialization.NoEncryption())
    public = private.public_key().public_bytes(*_RAW)
    return bech32_encode('age-secret-key-', secret).upper(), bech32_encode('age', public)


# ---------------------------------------------------------------- primitives

def _b64(data):
    return base64.b64encode(data).rstrip(b'=')


def _unb64(data):
    if data.endswith(b'=') or b'\n' in data:
        raise AgeError('non-canonical base64')
    out = base64.b64decode(data + b'=' * (-len(data) % 4), validate=True)
    if _b64(out) != data:
        raise AgeError('non-canonical base64')
    return out


def _hkdf(ikm, salt, info):
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=info).derive(ikm)


def _wrap_body(body):
    encoded = _b64(body)
    lines = [encoded[i:i + 64] for i in range(0, len(encoded), 64)]
    if not lines or len(lines[-1]) == 64:
        lines.append(b'')
    return b'\n'.join(lines) + b'\n'


def _chunk_nonce(counter, last):
    return counter.to_bytes(11, 'big') + (b'\x01' if last else b'\x00')


# ---------------------------------------------------------------- encryption

class AgeEncryptor:
    """File-like writer: ``write()`` plaintext, ``close()`` to finish.

    Holds at most one 64 KiB chunk of plaintext. ``close()`` must be called,
    because the final chunk is marked as last; a file that was never closed
    fails to decrypt instead of silently truncating.
    """

    def __init__(self, out, recipient: str):
        self._out = out
        file_key = os.urandom(16)

        ephemeral = X25519PrivateKey.generate()
        share = ephemeral.public_key().public_bytes(*_RAW)
        recipient_key = parse_recipient(recipient)
        shared = ephemeral.exchange(recipient_key)
        if shared == b'\x00' * 32:
            raise AgeError('low-order recipient key')
        wrap_key = _hkdf(shared, share + recipient_key.public_bytes(*_RAW), X25519_LABEL)
        wrapped = ChaCha20Poly1305(wrap_key).encrypt(b'\x00' * 12, file_key, None)

        header = (VERSION_LINE + b'\n-> X25519 ' + _b64(share) + b'\n'
                  + _wrap_body(wrapped) + b'---')
        mac = hmac.new(_hkdf(file_key, b'', b'header'), header, hashlib.sha256).digest()
        nonce = os.urandom(16)
        out.write(header + b' ' + _b64(mac) + b'\n' + nonce)

        self._aead = ChaCha20Poly1305(_hkdf(file_key, nonce, b'payload'))
        self._buf = bytearray()
        self._counter = 0
        self._closed = False

    def write(self, data):
        if self._closed:
            raise ValueError('write to closed AgeEncryptor')
        self._buf += data
        # Keep a chunk back: the last chunk is flagged, and must not be empty
        # unless the whole file is.
        while len(self._buf) > CHUNK:
            self._emit(bytes(self._buf[:CHUNK]), last=False)
            del self._buf[:CHUNK]
        return len(data)

    def _emit(self, chunk, last):
        self._out.write(self._aead.encrypt(_chunk_nonce(self._counter, last), chunk, None))
        self._counter += 1

    def flush(self):
        pass

    def close(self):
        if not self._closed:
            self._emit(bytes(self._buf), last=True)
            self._buf.clear()
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *exc):
        # Only finish the file on success; an aborted backup stays undecryptable.
        if exc_type is None:
            self.close()
        return False


# ---------------------------------------------------------------- decryption

def _read_line(stream):
    line = stream.readline(4096)
    if not line.endswith(b'\n'):
        raise AgeError('truncated or oversized header line')
    return line[:-1]


def decrypt_stream(src, identity: str):
    """Yield plaintext chunks of the age file ``src`` (binary file object)."""
    private = parse_identity(identity)
    our_public = private.public_key().public_bytes(*_RAW)

    header = bytearray()
    line = _read_line(src)
    if line != VERSION_LINE:
        raise AgeError('not an age v1 file')
    header += line + b'\n'

    file_key = None
    while True:
        line = _read_line(src)
        if line.startswith(b'---'):
            if not line.startswith(b'--- '):
                raise AgeError('malformed header MAC line')
            header += b'---'
            mac = _unb64(line[4:])
            break
        if not line.startswith(b'-> '):
            raise AgeError('malformed stanza')
        header += line + b'\n'
        args = line[3:].split(b' ')
        body = bytearray()
        while True:
            body_line = _read_line(src)
            header += body_line + b'\n'
            if len(body_line) > 64:
                raise AgeError('stanza body line too long')
            body += body_line
            if len(body_line) < 64:
                break
        if file_key is not None or args[0] != b'X25519':
            continue
        if len(args) != 2:
            raise AgeError('malformed X25519 stanza')
        share = _unb64(args[1])
        if len(share) != 32:
            raise AgeError('malformed X25519 share')
        shared = private.exchange(X25519PublicKey.from_public_bytes(share))
        wrap_key = _hkdf(shared, share + our_public, X25519_LABEL)
        try:
            file_key = ChaCha20Poly1305(wrap_key).decrypt(b'\x00' * 12, _unb64(bytes(body)), None)
        except Exception:
            continue  # stanza for another recipient

    if file_key is None:
        raise AgeError('no stanza matches this identity')
    expected = hmac.new(_hkdf(file_key, b'', b'header'), bytes(header), hashlib.sha256).digest()
    if not hmac.compare_digest(mac, expected):
        raise AgeError('header MAC mismatch')

    nonce = src.read(16)
    if len(nonce) != 16:
        raise AgeError('truncated payload nonce')
    aead = ChaCha20Poly1305(_hkdf(file_key, nonce, b'payload'))

    counter = 0
    current = src.read(CHUNK + _TAG)
    while True:
        following = src.read(CHUNK + _TAG)
        last = not following
        if len(current) < _TAG or (not last and len(current) != CHUNK + _TAG):
            raise AgeError('truncated payload')
        try:
            plain = aead.decrypt(_chunk_nonce(counter, last), current, None)
        except Exception:
            raise AgeError('payload authentication failed (corrupt or truncated)') from None
        if last and not plain and counter:
            raise AgeError('empty final chunk')
        yield plain
        if last:
            return
        counter += 1
        current = following
