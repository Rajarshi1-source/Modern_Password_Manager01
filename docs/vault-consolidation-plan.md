# Vault Consolidation Plan — Remaining Items

Status as of 2026-06-18. Tracks the final two work items for making the
dashboard's vault list + edit work end-to-end against the single-source
`VaultContext`.

PR sequencing (increasing risk):

| PR | Scope | Risk | Verifiable in canny venv |
|----|-------|------|--------------------------|
| **PR D** | URLconf fix (Item 1) — backend only | Lowest | Yes (resolve matrix + APIClient tests) |
| **PR E** | Extract `vaultEnvelope` helper + reuse in `VaultItemsSection` (pure refactor) | Low | Frontend suite |
| **PR F** | Unify `VaultContext` crypto with `sessionVaultCrypto` (Item 2) | **Security-critical** — HELD pending explicit go-ahead | Unit tests + manual smoke test |

---

## Item 1 — Fix the vault URLconf (PR D)

### Verified problem (empirically, via `django.urls.resolve` / `reverse` in the canny venv)

`password_manager/vault/urls.py` had three independent routing defects:

1. **`path('', vault_root)` shadowed the list.** Registered at `^$` *before*
   the router include, so `GET /api/vault/` hit the browsable info view and
   never reached `ApiVaultItemViewSet.list`. (`POST /api/vault/` worked
   because `vault_root` is GET-only and fell through to the list route's
   `create`.)

2. **The empty-prefix `r''` ModelViewSet detail route is a greedy
   catch-all.** `^(?P<pk>[^/.]+)/$` matches any single path segment, and it
   was registered *before* `folders` / `backups` / `items`, so every sibling
   sub-route was captured as `detail(pk=...)`.

3. **`sync` was at the wrong URL.** `CrudVaultItemViewSet` was registered at
   `r'vault'` under an include already mounted at `/api/vault/`, so its
   `sync` action lived at `/api/vault/vault/sync/` (double `vault`). The
   frontend (`api.js`, `vaultService.js`) and the urls.py comment both
   expect `/api/vault/sync/` — which was a POST→405 dead route (detail
   catch-all, no POST). `search/` and the bare `shared-folders/` list were
   shadowed the same way (custom paths placed *after* the router include).

#### Before-fix resolve matrix (verified)

| Request | Resolved to | Should be |
|---------|-------------|-----------|
| `GET /api/vault/` | `vault-root` (info view) | items list |
| `/api/vault/folders/` | `api-vault-detail` (pk=folders) | folders list |
| `/api/vault/backups/` | `api-vault-detail` (pk=backups) | backups list |
| `/api/vault/items/` | `api-vault-detail` (pk=items) | items list |
| `/api/vault/sync/` | `api-vault-detail` (pk=sync) → 405 on POST | sync action |
| `/api/vault/get_salt/` | `api-vault-get-salt` ✅ | (works — action precedes detail) |
| `/api/vault/verify_auth/` | `api-vault-verify-auth` ✅ | (works) |
| `/api/vault/{uuid}/` | `api-vault-detail` ✅ | item detail (favorite PATCH path) |

`reverse()` cross-check confirmed `vault-sync` → `/api/vault/vault/sync/`
(double prefix) and that `vault-list` / `vault-detail` (the `r'vault'`
router names) and `/api/vault/vault/...` are referenced nowhere in the repo.

### Fix (implemented)

- Switch `DefaultRouter` → `SimpleRouter` (drops the auto API-root at `^$`
  so the `r''` list route can serve `/api/vault/`).
- Register explicit-prefix viewsets (`folders`, `backups`, `items`) first
  and the empty-prefix `r''` viewset **last**, so the detail catch-all is
  the final pattern tried.
- Move `vault_root` off `^$` to `meta/` (`name='vault-root'` preserved, so
  `api/urls.py`'s `reverse('vault-root')` still works).
- Drop the `r'vault'` `CrudVaultItemViewSet` ModelViewSet registration
  (pure cruft — double-`vault` routes used nowhere) and mount its `sync`
  action explicitly at `/api/vault/sync/` (`name='vault-sync'` preserved).
- Place all custom `path()` routes (`sync/`, `search/`, `create_backup/`,
  `restore_backup/`, `shared-folders/`, `api-auth/`) **before** the router
  include so none can be shadowed by the detail catch-all.

This keeps every endpoint the frontend already uses working — `GET/POST
/api/vault/`, `…/{id}/` retrieve/update/**favorite PATCH**/delete, the
`detail=False` actions (`get_salt`, `verify_auth`, `statistics`,
`check_initialization`), `sync`, `folders`, `backups`, `search`,
`shared-folders` — while removing the shadowing.

### Tests
- `VaultUrlconfRoutingTests` (APIClient + `resolve()`): asserts every row of
  the matrix resolves to the intended view, `GET /api/vault/` returns the
  user's items (scoped, excludes other users), and the favorite PATCH /
  folders / backups / sync routes still work.
- Gate: `canny\Scripts\python.exe manage.py test vault` (full module).

### Risk & rollback
Pure URLconf change; trivially revertable. The `resolve()` matrix test is
the regression gate. **Frontend impact: none.**

---

## Item 2 — Unify `VaultContext` crypto with `sessionVaultCrypto` (PR F — HELD)

> **Held pending explicit go-ahead** — this is the security-critical change
> (it touches the primary vault's encrypt/decrypt). Do not start without
> sign-off.

### Verified problem
`VaultContext` routes crypto through `vaultService` (`this.cryptoService` +
`this.encryptionKey`), which is only initialized by `vaultService.initialize()`
via `context.unlockVault()` — **never called**. So `decryptItem` /
`addItem` / `updateItem` throw on the null key, and `isUnlocked` is never
true (dashboard `canEdit` is hard-false). The working crypto is
`sessionVaultCrypto` (v2) + `sessionVaultCryptoV3` (v3), used by `/vault`.

### Design (file-by-file)
1. **Extract** the proven v2→v3 decrypt logic from `App.jsx`'s
   `VaultItemsSection.decryptOne` into `frontend/src/services/vaultEnvelope.js`
   (`decryptEnvelope` / `encryptEnvelope`). Reuse in `VaultItemsSection`
   (no behavior change) **and** `VaultContext` — single source of crypto
   truth, unit-testable. *(This extraction is PR E.)*
2. `VaultContext.decryptItem(itemId)`: `decryptEnvelope(item.encrypted_data)`,
   cache in the existing `decryptedItems` Map, handle `_legacyPlaintext` /
   decrypt failure (don't open the editor on failure). Stop calling
   `vaultService.decryptItemOnDemand`.
3. `VaultContext.updateItem(item)`: gate on `sessionVaultCrypto.hasSessionKey()`;
   `encrypted_data = await encryptEnvelope(item.data)`; `axios.put('/api/vault/<id>/', …)`
   via the default authenticated axios; update `items` + invalidate the
   `decryptedItems` cache entry; broadcast `vault:updated`. Stop calling
   `vaultService.saveVaultItem`.
4. `canEdit` / `isUnlocked`: derive from `sessionVaultCrypto.hasSessionKey()`.
5. Field-shape reconciliation: map `url`↔`website` on edit (add flow stores
   `website`; `PasswordItemForm` emits `url`).
6. Retire the dead `vaultService` crypto path once nothing calls it.

### Tests
- Unit (vitest) for `vaultEnvelope`: v2 success; v2 `_legacyPlaintext` → v3
  fallback; v3 failure → keep v2; decrypt error; `encryptEnvelope` delegates.
- Unit for `context.updateItem`: PUT `/api/vault/{id}/` with `encrypted_data`
  (never plaintext), gated on `hasSessionKey()`, cache invalidated.
- Regression: full frontend suite stays green.

### Risk & mitigations (security-critical)
Reuse the already-working v2/v3 logic verbatim (write no new crypto); land
behind unit tests; **required manual smoke test** before merge (unlock →
dashboard lists items → edit a password → re-open to confirm round-trip →
confirm `/vault` reflects it). **Depends on Item 1** (dashboard must list
items to edit them).
