# PR #262 — Audit-fix cutover runbook

This document is the explicit step-by-step for operators rolling out the
12 audit fixes from PR #262. It exists to mitigate the two redeploy-shaped
risks called out in the PR body:

1. **`TimeLockedVault` storage-layout change** — new `oracleMaxStaleness`
   field in the `Vault` struct. Existing on-chain `Vault` rows in the old
   contract cannot be migrated; the new contract must be redeployed.
2. **`CommitmentRegistry` authorization-model change** — `anchorCommitment`
   is no longer `onlyOwner`; it now verifies the signature against an
   `authorizedSigners` mapping. The signature payload itself is also
   domain-separated by `(chainid, contract_address)`. Old signatures will
   not validate against the new contract; new signatures will not validate
   against the old one.

Both changes are bounded — see the **Data risks** section at the bottom —
but the cutover ordering matters. Follow these steps in order.

---

## Pre-flight (before changing anything)

1. **Snapshot DB.** Capture a logical dump of `BlockchainAnchor`,
   `MerkleProof`, `PendingCommitment`, `SmartContractVault`,
   `UserSalt` (both `auth_module` and `vault`), `SignInChallenge`.
   ```bash
   pg_dump --table='blockchain_anchors' --table='merkle_proofs' \
           --table='pending_commitments' --table='smart_contract_vaults' \
           --table='auth_module_usersalt' --table='vault_usersalt' \
           --table='decentralized_identity_signinchallenge' \
           "$DATABASE_URL" > pre_pr262.sql
   ```

2. **Verify the *current* `BLOCKCHAIN_ENABLED` state.** If `False`,
   skip every blockchain-related step below and proceed to step 4
   (Django migrate) only.
   ```bash
   python manage.py shell -c "from django.conf import settings; print(settings.BLOCKCHAIN_ANCHORING.get('ENABLED'))"
   ```

3. **Confirm a clean Git checkout of PR #262.**
   ```bash
   git fetch origin && git checkout claude/security-audit-2026-05
   git log -1 --format='%H %s'   # expect: feat(blockchain): C7 follow-up …
   ```

---

## Step 1 — Deploy the new contracts (testnet first)

Deploy in this order so the Django side sees the *new* addresses
everywhere:

```bash
cd contracts
# Use a wallet funded with Arbitrum Sepolia ETH.
export BLOCKCHAIN_PRIVATE_KEY=0x…   # operator's deploy key, not the hot signer

# 1. CommitmentRegistry — the deployer becomes both `owner` and the
#    initial authorizedSigner.
npx hardhat run scripts/deploy.js --network arbitrumSepolia

# 2. TimeLockedVault — new storage layout with `oracleMaxStaleness`.
npx hardhat run scripts/deploy-timelocked-vault.js --network arbitrumSepolia

# 3. VaultAuditLog — required for the C11 reveal-anchor path.
npx hardhat run scripts/deploy-vault-audit-log.js --network arbitrumSepolia
```

Each script prints the contract address. **Stash them.**

---

## Step 2 — Update environment variables

```bash
# Update the env file the Django app reads — operator-specific.
COMMITMENT_REGISTRY_ADDRESS_TESTNET=0x…       # from step 1 (1)
TIMELOCKED_VAULT_ADDRESS=0x…                  # from step 1 (2)
VAULT_AUDIT_LOG_ADDRESS=0x…                   # from step 1 (3)  — required
```

`VAULT_AUDIT_LOG_ADDRESS` is **no longer** allowed to silently fall
back to `TIMELOCKED_VAULT_ADDRESS` (that fallback was deleted in
PR #262 because every audit broadcast was reverting against a contract
that doesn't have the `anchorUnlock(bytes32)` selector). If unset,
`OnchainUnlockService.enabled` reports False and the feature degrades
gracefully — DB unlocks still succeed; only the on-chain audit anchor
is skipped.

---

## Step 3 — Hot signer setup (optional, recommended for prod)

If you're moving to a KMS-backed signer (the C7 follow-up):

```bash
# In .env / k8s secret:
BLOCKCHAIN_KEY_PROVIDER=kms
BLOCKCHAIN_KMS_KEY_ID=arn:aws:kms:us-east-1:…:key/…

# Confirm the KMS-derived address with a one-shot Django shell:
python manage.py shell -c "from blockchain.services.key_provider import get_key_provider; p = get_key_provider(); print(p.provider_kind, p.address)"

# Authorize the new signer on the freshly-deployed registry:
#   (any account holding gas can broadcast this; the call is `onlyOwner`.)
npx hardhat console --network arbitrumSepolia
> const c = await ethers.getContractAt("CommitmentRegistry", process.env.COMMITMENT_REGISTRY_ADDRESS_TESTNET)
> await c.addAuthorizedSigner("0x…")        // the KMS-derived address
> await c.removeAuthorizedSigner(await c.owner())   // optional: revoke the deployer key once the KMS signer is in
```

The `authorizedSignerCount > 1` guard in `removeAuthorizedSigner`
prevents the registry from being bricked here.

---

## Step 4 — Migrate the Django DB

```bash
python manage.py migrate
```

Four new migrations apply:

| App | Migration | What it does |
|---|---|---|
| blockchain | `0003_hash_algo_verifiable` | Adds `hash_algo` (default `'keccak256'`) and `verifiable` (default `True`) to `BlockchainAnchor` and `MerkleProof`. Backfills **existing rows** to `hash_algo='sha256', verifiable=False`. |
| decentralized_identity | `0003_signinchallenge_binding_token` | Adds `binding_token` column (default `''`). Pre-fix challenges keep verifying without a cookie for one release; new challenges set the cookie. |
| smart_contracts | `0003_reveal_nonce_commitment` | Adds `reveal_nonce` + `reveal_commitment` to `SmartContractVault` (both default empty). Populated lazily on first reveal. |
| vault | `0010_backfill_user_salt_auth_hash` | Copies `auth_module.UserSalt.auth_hash` into `vault.UserSalt.auth_hash` for every row where the vault side was empty. **No re-registration is required**. |

---

## Step 5 — Verify the migration succeeded

```bash
python manage.py verify_audit_migration
```

This command exits non-zero if any of the following invariants are
violated, so it's safe to wire into a deployment gate:

- Every `BlockchainAnchor` row has a non-null `hash_algo`.
- Pre-existing `BlockchainAnchor` rows are flagged `verifiable=False`
  (audit-fix C1 expects exactly this — those proofs were built with
  SHA-256 and cannot be reproduced by the new keccak256 verifier).
- `MerkleProof.verifiable` mirrors its anchor's `verifiable`.
- Every `vault.UserSalt` row that has a populated `auth_module.UserSalt`
  counterpart now has a matching non-empty `auth_hash` (audit-fix C10
  backfill).
- The configured contract addresses, if any, point at *non-empty*
  bytecode on-chain (no zero-byte placeholder addresses).
- If `SMART_CONTRACT_UNLOCK_ONCHAIN_ENABLED=True` then
  `VAULT_AUDIT_LOG_ADDRESS` is set (no silent fallback to the
  TimeLockedVault address).

---

## Step 6 — Re-anchor pending behavioural commitments

Only needed if `BLOCKCHAIN_ENABLED=true`:

```bash
python manage.py rehash_pending_commitments
```

This deletes stale SHA-256-hashed `PendingCommitment` rows and
re-enqueues them with `add_commitment(..., auto_anchor=False)` so the
re-enqueue can't trigger a mixed-hash batch mid-transaction. The
command preserves the original row if `add_commitment` fails, so it
is idempotent and safe to re-run.

The next normal anchor batch (whether by Celery schedule or a manual
`BlockchainAnchorService.anchor_pending_batch()` call) will then
produce a fresh keccak256 Merkle root that the on-chain verifier can
reconstruct.

---

## Step 7 — Smoke

```bash
# Sentry posture: warm up a Sentry-instrumented worker and trigger a
# logger.error with a fake 0x-prefixed hex blob. Confirm the event
# arrives with `0x<redacted>` substituted.
python manage.py shell -c "import logging; logging.getLogger('sentry-test').error('test %s', '0x' + 'a'*64)"

# DID sign-in: hit /api/decentralized-identity/sign-in/challenge/ and
# verify the response sets a `did_signin_binding` cookie with
# HttpOnly+Secure+SameSite=Strict.

# Vault verify_auth: confirm an authenticated request with an empty
# auth_hash returns 400 vault_not_initialized (NOT 200, NOT silently
# accepting the caller's hash).
```

---

## Rollback

The contract redeploy is the only step that isn't fully reversible from
config alone:

| What to roll back | How |
|---|---|
| Django code | `git revert` the PR and redeploy. |
| Settings | Restore `VAULT_AUDIT_LOG_ADDRESS=''` and the **old** `COMMITMENT_REGISTRY_ADDRESS_TESTNET` / `TIMELOCKED_VAULT_ADDRESS`. The Django side will talk to the old contracts again. |
| Migrations | `manage.py migrate blockchain 0002`, `manage.py migrate vault 0009`, etc. All four new migrations have safe reverse operations or no-op reverses. |
| Old hash anchors | They're already flagged `verifiable=False`; verify_commitment surfaces `status: legacy_hash_mismatch`. No data loss. |

The KMS signer is rotation-safe: if you switch back to env-based
signing, just `addAuthorizedSigner(env_address)` then
`removeAuthorizedSigner(kms_address)`. The `authorizedSignerCount > 1`
guard prevents you from accidentally locking yourself out.

---

## Data risks (recap)

* **Existing `BlockchainAnchor` rows continue to exist** and are flagged
  `verifiable=False`; the verify endpoint returns
  `status: 'legacy_hash_mismatch'` for them with a human-readable
  explanation. No data loss. (See migration `blockchain/0003`.)
* **Existing `vault.UserSalt` rows with empty `auth_hash` are
  backfilled** from `auth_module.UserSalt` via migration `vault/0010`.
  No re-registration needed. Rows where neither side has a populated
  auth_hash stay empty and `verify_auth` correctly refuses with
  `vault_not_initialized` (which is the intended C10 behaviour).
