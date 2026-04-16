# HiddenVaultBlob v1 — specification

Canonical, language-independent format for the cryptographic
plausible-deniability primitive used by the Password Manager. The same
bytes must be produced and consumed by the Python implementation
([password_manager/hidden_vault/envelope.py](password_manager/hidden_vault/envelope.py))
and the JS/TS implementations
([frontend/src/services/hiddenVault/hiddenVaultEnvelope.js](frontend/src/services/hiddenVault/hiddenVaultEnvelope.js),
[browser-extension/src/stego/hiddenVaultEnvelope.js](browser-extension/src/stego/hiddenVaultEnvelope.js),
[mobile/src/services/stego/hiddenVaultEnvelope.js](mobile/src/services/stego/hiddenVaultEnvelope.js)).

## Goals

1. **Cryptographic deniability.** A single opaque blob that encrypts
   *both* a real vault and a decoy vault under two independent master
   passwords. An adversary with full byte-level access to the blob
   cannot prove the real vault exists without trying the real
   password.
2. **Fixed size.** The blob size is determined by a tier, not by the
   plaintext size, so comparing byte lengths reveals nothing about
   plaintext lengths.
3. **Slot symmetry.** Both slot-0 and slot-1 are always written with
   valid-looking ciphertext, even when the user only configured one
   vault. The "unused" slot is encrypted under a fresh, discarded
   random key — making it cryptographically indistinguishable from the
   "used" slot.
4. **Password → slot is opaque.** The caller presents a password; the
   decoder tries both slots and returns whichever one verifies (or
   raises). Nobody examining the blob can tell which slot is "real".

## Non-goals

- Defense against compelled disclosure of both passwords.
- Defense against post-unlock side-channels (RAM inspection).
- Defense against steganalysis of the outer cover image (that is the
  `stegano_vault` layer's concern, not this envelope's).
- Partial updates: every encode rewrites the whole blob.

## Layout

All integers are little-endian. Sizes are in bytes. Total blob size is
fixed per tier.

```
offset  size   field            notes
------  ----   --------------   -------------------------------------
 0      8      magic            b"HVBLOBv1"
 8      1      version          0x01
 9      1      slot_count       always 2 in v1
10      1      tier             0=32KiB, 1=128KiB, 2=1MiB
11      1      kdf_id           0x01 = argon2id (only value in v1)
12      4      kdf_time_cost    uint32 LE, argon2id t (default 3)
16      4      kdf_memory_kib   uint32 LE, argon2id m_cost KiB (default 65536)
20      4      kdf_parallelism  uint32 LE, argon2id p (default 1)
24      16     outer_salt       per-blob random salt (distinct from slot domain tags)
40      2      slot_payload_len uint16 LE: K, the ciphertext+tag length
                                per slot. Same for both slots.
42      12     slot0_nonce      AES-256-GCM nonce, slot 0
54      K      slot0_ct_tag     AES-256-GCM(ct || 16-byte tag)
54+K    12     slot1_nonce
66+K    K      slot1_ct_tag
66+2K   pad    random_pad       fill with crypto random bytes to the
                                tier's fixed total size
```

Total tier sizes:

| tier | bytes         |
| ---- | ------------- |
| 0    | 32768         |
| 1    | 131072        |
| 2    | 1048576       |

## Key derivation

For each slot `i ∈ {0, 1}`:

```
domain_tag_i = b"HVBLOBv1/slot" || bytes([i])       # 14 bytes
salt_i       = outer_salt || domain_tag_i            # 30 bytes
K_i          = Argon2id(
                 password   = utf8(password_i),
                 salt       = salt_i,
                 t          = kdf_time_cost,
                 m_cost_KiB = kdf_memory_kib,
                 p          = kdf_parallelism,
                 hash_len   = 32,
               )
```

The **"unused slot"** is encrypted under a fresh random 32-byte key
that the encoder discards immediately (`os.urandom(32)` / WebCrypto
`getRandomValues`). No password derivation touches it.

## Plaintext framing

Before encryption each slot's plaintext is framed:

```
SLOT_PLAINTEXT = magic(4) b"HVS1" || length(4, uint32 LE) || payload(length bytes) || zero_pad
```

The frame is padded with `0x00` bytes up to `K - 16` (where `K` is the
ciphertext+tag length declared in `slot_payload_len` and `16` is the
GCM tag size). Padding is applied *inside* the encryption so the
ciphertext is always exactly `K - 16` bytes plus the 16-byte tag.
**Choose `K` per tier** such that
`K - 16 >= max_expected_payload + 8`. Recommended defaults:

| tier | K (bytes) |
| ---- | --------- |
| 0    | 16000     |
| 1    | 60000     |
| 2    | 490000    |

Decoder verifies the `HVS1` magic + length before returning the
payload, which also catches "wrong password" because a random key
produces random bytes with overwhelming probability of failing either
the GCM tag check or the `HVS1` frame check.

## Decode algorithm

```
def decode(blob: bytes, password: str) -> (slot_index, payload_bytes):
    header = parse_header(blob)
    for i in (0, 1):
        K_i = argon2id(password, outer_salt || domain_tag_i, ...)
        try:
            plain = AESGCM(K_i).decrypt(nonce_i, ct_tag_i, associated_data=None)
        except InvalidTag:
            continue
        if plain[:4] != b"HVS1":
            continue
        length = int.from_bytes(plain[4:8], "little")
        return i, plain[8:8 + length]
    raise WrongPasswordError
```

Both slots are always tried. Timing must be equalized in production
(both branches compute Argon2id + AES-GCM).

## Test vectors

The canonical reference test vectors are JSON at
[password_manager/hidden_vault/tests/vectors.json](password_manager/hidden_vault/tests/vectors.json).
Every implementation (Python, web JS, extension JS, React Native) runs
the vectors through its own encode/decode and asserts exact equality
on the following invariants, which are the only cross-language
guarantees (the blob bytes themselves are *not* deterministic because
they contain random nonces, salts, and padding):

1. `encode(password_real, payload_real, password_decoy, payload_decoy, tier) → blob`
   produces a blob of exactly `tier_bytes` bytes.
2. `decode(blob, password_real).payload_bytes == payload_real`.
3. `decode(blob, password_decoy).payload_bytes == payload_decoy`.
4. `decode(blob, "wrong-password")` raises.
5. `decode(blob, password_real).slot_index != decode(blob, password_decoy).slot_index`.

For determinism-sensitive tests, implementations expose an optional
`encode_deterministic(..., rng_seed=bytes)` that seeds all randomness
so byte-for-byte cross-language equality can be asserted as well. The
seed is *not* shipped in production.
