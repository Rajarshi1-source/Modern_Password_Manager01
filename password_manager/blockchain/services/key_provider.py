"""
Blockchain signing key abstraction (C7 follow-up).

Background
----------
The audit-fix C7 work shipped log demotion + a Sentry scrubber, but the
private-key material itself still lived in process memory as a hex
string read from ``os.environ['BLOCKCHAIN_PRIVATE_KEY']``. Any RCE in
any Django view could exfiltrate that key and (because of the C8
``authorizedSigners`` map) immediately mint signatures for the
CommitmentRegistry anchor pipeline.

This module introduces a ``KeyProvider`` interface so signing can be
delegated to an external custodian — typically AWS KMS holding a
secp256k1 key whose raw bytes never reach the Django process. The
``authorizedSigners`` map (added in PR #262) is the on-chain
prerequisite: rotating from ``EnvKeyProvider`` to ``KmsKeyProvider``
just means calling ``addAuthorizedSigner(new_address)`` then
``removeAuthorizedSigner(old_address)`` — no contract redeploy.

Providers
---------
* ``EnvKeyProvider`` — current behaviour. Reads
  ``BLOCKCHAIN_PRIVATE_KEY`` from the environment, holds it in
  memory, signs with ``eth_account.Account``. The default. Suitable
  for dev, single-tenant self-hosted, and CI.
* ``KmsKeyProvider`` — production-grade. Holds only the key's KMS ARN
  and the cached public address. Each sign request is a single
  ``kms:Sign`` call against AWS KMS; the private bytes never touch
  the Django process. Optional dependency: ``boto3``.

Selection
---------
The factory ``get_key_provider()`` picks based on settings:

    BLOCKCHAIN_KEY_PROVIDER = 'env'        # default
    BLOCKCHAIN_KEY_PROVIDER = 'kms'
    BLOCKCHAIN_KMS_KEY_ID = 'arn:aws:kms:us-east-1:...:key/...'

If unset, falls back to env-var behaviour to preserve backward compat.
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------

class KeyProvider(ABC):
    """
    Abstraction over an Ethereum-compatible signing key.

    The interface is deliberately narrow: callers can ask for the
    public address, sign an EIP-191 message hash, or sign a raw
    transaction dict. They cannot extract the private key — a
    ``KmsKeyProvider`` implementation literally does not have access
    to it.
    """

    @property
    @abstractmethod
    def address(self) -> str:
        """Checksum-cased EOA address for this signer."""

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """True iff this provider can actually sign right now."""

    @abstractmethod
    def sign_message(self, eip191_message) -> Any:
        """
        Sign an EIP-191 message (the ``encode_defunct(primitive=...)``
        output that ``eth_account`` produces).

        Returns an object with at least a ``.signature`` attribute,
        compatible with ``LocalAccount.sign_message``'s return type so
        callers don't need to special-case the provider.
        """

    @abstractmethod
    def sign_transaction(self, tx: dict, w3) -> bytes:
        """
        Sign a transaction dict and return its serialized raw bytes
        ready for ``w3.eth.send_raw_transaction``. The ``w3`` handle is
        passed in so providers that need chain metadata (chain id, etc.)
        can read it without re-importing global state.
        """

    @property
    def provider_kind(self) -> str:
        """Short label for logging/metrics — e.g. ``'env'``, ``'kms'``."""
        return self.__class__.__name__


# ---------------------------------------------------------------------------
# EnvKeyProvider — current behaviour, default
# ---------------------------------------------------------------------------

class EnvKeyProvider(KeyProvider):
    """
    Reads a hex-encoded private key from ``BLOCKCHAIN_PRIVATE_KEY``.

    Pros: zero infra, works in dev and CI.
    Cons: the raw key sits in process memory and is reachable by any
    RCE bug. Use ``KmsKeyProvider`` for production deployments.
    """

    def __init__(self, env_var: str = 'BLOCKCHAIN_PRIVATE_KEY') -> None:
        self._env_var = env_var
        self._private_key: Optional[str] = os.environ.get(env_var)
        self._account = None
        if self._private_key:
            from eth_account import Account  # local import: optional dep
            self._account = Account.from_key(self._private_key)
            logger.debug(
                "EnvKeyProvider initialized for address %s",
                self._account.address,
            )
        else:
            logger.warning(
                "EnvKeyProvider: %s is not set; signing operations will fail.",
                env_var,
            )

    @property
    def address(self) -> str:
        if not self._account:
            raise RuntimeError(
                f"EnvKeyProvider has no key (env var {self._env_var} unset)"
            )
        return self._account.address

    @property
    def is_available(self) -> bool:
        return self._account is not None

    def sign_message(self, eip191_message) -> Any:
        if not self._account:
            raise RuntimeError("EnvKeyProvider: no key available to sign")
        return self._account.sign_message(eip191_message)

    def sign_transaction(self, tx: dict, w3) -> bytes:
        if not self._private_key:
            raise RuntimeError("EnvKeyProvider: no key available to sign tx")
        signed = w3.eth.account.sign_transaction(tx, self._private_key)
        # web3.py renamed the attribute between releases; accept either.
        raw = getattr(signed, 'raw_transaction', None) \
            or getattr(signed, 'rawTransaction', None)
        if raw is None:
            raise RuntimeError(
                "EnvKeyProvider: signed tx had neither raw_transaction nor "
                "rawTransaction attribute"
            )
        return raw

    @property
    def provider_kind(self) -> str:
        return 'env'


# ---------------------------------------------------------------------------
# KmsKeyProvider — production path
# ---------------------------------------------------------------------------

class KmsKeyProvider(KeyProvider):
    """
    Delegates secp256k1 signing to AWS KMS.

    AWS KMS supports secp256k1 ECDSA signing under
    ``KeySpec='ECC_SECG_P256K1'``. The Django process holds only the
    key's ARN; the raw bytes never leave KMS. Each sign operation is
    a single ``kms:Sign`` call, billed per request.

    The public address is derived once from the key's exported public
    bytes and cached so we don't round-trip to AWS for every
    ``account.address`` access.

    Requires ``boto3``. If it isn't installed, instantiation fails
    fast so misconfigurations surface at startup, not at the first
    anchor.
    """

    def __init__(self, key_id: str, *, boto_client: Optional[Any] = None) -> None:
        if not key_id:
            raise ValueError("KmsKeyProvider: key_id is required")
        self._key_id = key_id

        if boto_client is None:
            try:
                import boto3  # type: ignore
            except ImportError as e:
                raise RuntimeError(
                    "KmsKeyProvider requires boto3. Install with "
                    "`pip install boto3` or set BLOCKCHAIN_KEY_PROVIDER='env'."
                ) from e
            boto_client = boto3.client('kms')
        self._kms = boto_client

        # Derive and cache the EOA address from the KMS public key.
        # Done once at construction so the hot path is one KMS call
        # per signature, not two.
        self._address: Optional[str] = None
        try:
            self._address = self._derive_address()
            logger.debug(
                "KmsKeyProvider initialized for address %s (KMS %s)",
                self._address, key_id,
            )
        except Exception as e:
            # Don't crash startup on a transient KMS failure — the
            # provider just reports unavailable until KMS recovers,
            # mirroring EnvKeyProvider's "missing env var" behaviour.
            logger.error(
                "KmsKeyProvider: failed to derive public address from "
                "KMS key %s: %s", key_id, e,
            )

    # -- public KeyProvider surface ------------------------------------

    @property
    def address(self) -> str:
        if not self._address:
            raise RuntimeError(
                f"KmsKeyProvider({self._key_id}) has no cached address; "
                "derivation failed at startup."
            )
        return self._address

    @property
    def is_available(self) -> bool:
        return self._address is not None

    def sign_message(self, eip191_message) -> Any:
        """
        EIP-191 message hash → KMS-signed signature wrapped to look
        like ``LocalAccount.sign_message``'s return type.
        """
        # eth_account.messages.SignableMessage carries the 32-byte hash
        # under `.body` for the standard EIP-191 personal_sign envelope.
        # We hash `version_E (\x45) || header || body` ourselves to keep
        # this independent of eth_account internals.
        from eth_account.messages import _hash_eip191_message
        message_hash = _hash_eip191_message(eip191_message)

        r, s, recovery_id = self._kms_sign_hash(message_hash)
        v = 27 + recovery_id  # personal_sign v space
        signature_bytes = r.to_bytes(32, 'big') + s.to_bytes(32, 'big') + bytes([v])
        return _SignedMessage(
            messageHash=message_hash,
            r=r,
            s=s,
            v=v,
            signature=signature_bytes,
        )

    def sign_transaction(self, tx: dict, w3) -> bytes:
        """
        EIP-1559 / legacy transaction → KMS-signed raw bytes.

        Implementation strategy: serialise the tx with eth_account, KMS-sign
        the resulting hash, then assemble the final RLP with the produced
        (r, s, v). This avoids re-implementing EIP-2718 envelope encoding.
        """
        from eth_account._utils.legacy_transactions import (
            serializable_unsigned_transaction_from_dict,
            encode_transaction,
        )

        unsigned = serializable_unsigned_transaction_from_dict(tx)
        message_hash = unsigned.hash()

        r, s, recovery_id = self._kms_sign_hash(message_hash)

        # For legacy transactions, v = chain_id * 2 + 35 + recovery_id
        # (EIP-155). For typed transactions, v = recovery_id (the
        # encode_transaction helper handles the difference internally
        # by inspecting the unsigned object's type).
        chain_id = tx.get('chainId') or w3.eth.chain_id
        if hasattr(unsigned, 'transaction_type'):
            v = recovery_id
        else:
            v = chain_id * 2 + 35 + recovery_id

        return encode_transaction(unsigned, vrs=(v, r, s))

    @property
    def provider_kind(self) -> str:
        return 'kms'

    # -- internals -----------------------------------------------------

    def _kms_sign_hash(self, message_hash: bytes):
        """Run a single kms:Sign call and decode the DER-encoded result."""
        resp = self._kms.sign(
            KeyId=self._key_id,
            Message=message_hash,
            MessageType='DIGEST',
            SigningAlgorithm='ECDSA_SHA_256',
        )
        der_sig = resp['Signature']
        r, s = _decode_der_signature(der_sig)
        # Normalize `s` to the lower half of the curve (EIP-2 / BIP-62).
        # KMS may return a high-s signature, which Ethereum rejects.
        _SECP256K1_N = 0xfffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141
        if s > _SECP256K1_N // 2:
            s = _SECP256K1_N - s

        # Recover recovery_id by trying both 0 and 1 and matching against
        # the known cached address. Cached at startup so this is O(1).
        from eth_keys import keys as eth_keys
        for recovery_id in (0, 1):
            sig_bytes = (
                r.to_bytes(32, 'big')
                + s.to_bytes(32, 'big')
                + bytes([recovery_id])
            )
            try:
                pubkey = eth_keys.Signature(sig_bytes).recover_public_key_from_msg_hash(
                    message_hash
                )
                if pubkey.to_checksum_address() == self._address:
                    return r, s, recovery_id
            except Exception:
                continue
        raise RuntimeError(
            "KmsKeyProvider: could not recover signer address from KMS "
            "signature; check key configuration."
        )

    def _derive_address(self) -> str:
        """Fetch the SubjectPublicKeyInfo from KMS and derive the EOA address."""
        resp = self._kms.get_public_key(KeyId=self._key_id)
        spki_der = resp['PublicKey']
        raw_pubkey = _spki_to_uncompressed_secp256k1(spki_der)

        # Ethereum address = lower 20 bytes of keccak256(pubkey-without-0x04-prefix)
        from eth_utils import keccak, to_checksum_address
        digest = keccak(raw_pubkey[1:])  # strip 0x04 prefix
        return to_checksum_address('0x' + digest[-20:].hex())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _SignedMessage:
    """
    Minimal LocalAccount.sign_message-compatible return type. Real
    eth_account.SignedMessage is a NamedTuple, but the only attribute
    callers actually use is ``.signature``; we mirror the full surface
    for safety.
    """

    __slots__ = ('messageHash', 'r', 's', 'v', 'signature')

    def __init__(self, messageHash, r, s, v, signature):
        self.messageHash = messageHash
        self.r = r
        self.s = s
        self.v = v
        self.signature = signature


def _decode_der_signature(der: bytes):
    """
    Minimal DER ECDSA signature decoder. KMS always returns
    DER-encoded sigs; we want the raw (r, s) integers.

    DER layout:
        0x30 LEN
          0x02 RLEN R_BYTES
          0x02 SLEN S_BYTES
    """
    if not der or der[0] != 0x30:
        raise ValueError("Invalid DER signature: missing SEQUENCE tag")
    # Skip outer header (2 bytes).
    offset = 2
    if der[offset] != 0x02:
        raise ValueError("Invalid DER signature: missing R INTEGER tag")
    r_len = der[offset + 1]
    r = int.from_bytes(der[offset + 2:offset + 2 + r_len], 'big')
    offset += 2 + r_len
    if der[offset] != 0x02:
        raise ValueError("Invalid DER signature: missing S INTEGER tag")
    s_len = der[offset + 1]
    s = int.from_bytes(der[offset + 2:offset + 2 + s_len], 'big')
    return r, s


def _spki_to_uncompressed_secp256k1(spki_der: bytes) -> bytes:
    """
    Extract the 65-byte uncompressed secp256k1 public key (0x04 || X || Y)
    from a DER-encoded SubjectPublicKeyInfo. We do this in pure Python
    rather than pulling in `cryptography` just for one parse — the SPKI
    format for secp256k1 is constant-length and easily indexed.
    """
    # secp256k1 SubjectPublicKeyInfo is always 88 bytes for an
    # uncompressed key. The actual 65-byte uncompressed pubkey starts
    # at the end of the BIT STRING header. Last 65 bytes is robust.
    if len(spki_der) < 65:
        raise ValueError("SPKI too short to contain a secp256k1 public key")
    uncompressed = spki_der[-65:]
    if uncompressed[0] != 0x04:
        raise ValueError(
            f"Expected uncompressed point prefix 0x04, got 0x{uncompressed[0]:02x}"
        )
    return uncompressed


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_singleton: Optional[KeyProvider] = None


def get_key_provider() -> KeyProvider:
    """
    Return the process-wide ``KeyProvider`` singleton.

    Selection order:
      1. ``settings.BLOCKCHAIN_KEY_PROVIDER`` (when 'env' or 'kms')
      2. Environment variable ``BLOCKCHAIN_KEY_PROVIDER``
      3. Default: 'env'

    For ``'kms'``, ``settings.BLOCKCHAIN_KMS_KEY_ID`` (or env
    ``BLOCKCHAIN_KMS_KEY_ID``) MUST be set to the KMS key ARN.
    """
    global _singleton
    if _singleton is not None:
        return _singleton

    kind = _read_setting('BLOCKCHAIN_KEY_PROVIDER', default='env').lower()
    if kind == 'kms':
        key_id = _read_setting('BLOCKCHAIN_KMS_KEY_ID', default='')
        if not key_id:
            raise RuntimeError(
                "BLOCKCHAIN_KEY_PROVIDER='kms' but BLOCKCHAIN_KMS_KEY_ID is unset"
            )
        _singleton = KmsKeyProvider(key_id)
    elif kind == 'env':
        _singleton = EnvKeyProvider()
    else:
        raise ValueError(
            f"Unknown BLOCKCHAIN_KEY_PROVIDER={kind!r}; "
            "expected 'env' or 'kms'."
        )

    logger.info(
        "Blockchain key provider: %s (address available: %s)",
        _singleton.provider_kind, _singleton.is_available,
    )
    return _singleton


def reset_key_provider_for_tests() -> None:
    """Test helper to clear the cached singleton between cases."""
    global _singleton
    _singleton = None


def _read_setting(name: str, *, default: str) -> str:
    """Read a config value from Django settings, falling back to env."""
    try:
        from django.conf import settings
        val = getattr(settings, name, None)
        if val is not None:
            return str(val)
    except Exception:
        pass
    return os.environ.get(name, default)
