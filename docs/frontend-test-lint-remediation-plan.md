# Frontend Lint + Unit-Test Remediation Plan

Branch: `fix/frontend-lint-tests` (from `main` @ 984faa6)
Status: **PLAN ONLY — no code changed yet.** Every number and root cause below was
measured by running `npm run lint` and `npm run test:unit` in this worktree.

Guiding constraints (from the request):
- Fix lint bugs, syntax errors, and the 42 unit-test failures **properly**.
- Where a test asserts a frontend↔backend contract, align the fix with the
  **actual backend implementation** (don't invent response shapes).
- Keep **production-code** changes as minimal as possible.

---

## 0. Headline

`npm run test:unit` → **42 failed / 193 passed (235)** across **15 files**, plus
**11 collection errors**. `npm run lint` → **132 errors / 657 warnings (789)**.

**~90% of the test failures are test-infrastructure issues — runner config, the
`jest`→`vi` global, a missing canvas mock, wrong import paths, an incomplete
mock, a stale CRA template, and JSX-in-`.js`.** They are fixed in *test/config
files*, **not** production components. Only **one** production file needs a
one-line change (add a named `export`). This is exactly the "minimal code
changes" outcome.

Also note: the CI `frontend-ci` lint and test steps are `continue-on-error: true`
(non-blocking) — so this work is about correctness/signal hygiene, not unblocking
the merge gate. The **build** job is the real gate and already passes.

---

## 1. Root-cause buckets (measured)

| # | Bucket | Failures/errors | Touches prod code? |
|---|--------|-----------------|--------------------|
| A | Test runner config & env | ~28 | No |
| B | Syntax / wrong-import in test files | ~5 files | No (1 test rename) |
| C | Mock / service-contract drift (backend-aware) | ~21 | 1 line (`export`) |
| D | UI query drift (test vs current markup) | ~15 | No |

(Buckets overlap a file count; the per-item fixes below are what matter.)

---

## 2. Bucket A — Test runner config & environment (fix centrally, 0 prod code)

These are the highest-leverage fixes: a handful of edits to `vitest.config.js`
and `src/setupTests.js` clear ~28 failures/errors at once.

### A0. Reconcile the duplicated config
`vite.config.js` has a `test:` block (with `include`/`exclude`) **and** there's a
separate `vitest.config.js`. `vitest run` uses **`vitest.config.js`**, which has
**no `include`/`exclude`** — so the `vite.config.js` test settings are dead and
e2e specs leak in. **Fix:** make `vitest.config.js` canonical; add `include`/
`exclude` there (and delete the now-dead `test:` block from `vite.config.js`).

### A1. Playwright e2e leaking into vitest (18 errors)
`src/tests/e2e/predictive_intent.e2e.test.js` → `Playwright Test did not expect
test.describe() to be called here.` Vitest is collecting Playwright specs.
**Fix:** add to `vitest.config.js` `test.exclude`:
```js
exclude: ['**/node_modules/**', '**/dist/**', '**/e2e/**', '**/*.e2e.*', 'e2e/**']
```

### A2. `jest is not defined` (5 files)
`adaptive_password.test.tsx`, `GeneticOAuthCallback.test.jsx`,
`GeneticDiceButton.test.jsx`, `entanglement.test.jsx`,
`EntropyHistoryChart.test.jsx` use `jest.fn/mock/spyOn` but the runner is vitest.
**Minimal central fix** (one place, instead of editing 5 files): in
`src/setupTests.js`:
```js
import { vi } from 'vitest';
globalThis.jest = vi; // compat shim for tests written against jest's API
```
(`vi` is API-compatible for `fn/mock/spyOn/clearAllMocks/useFakeTimers`.) If any
test uses a jest-only API that `vi` lacks, fix that call site individually.

### A3. Canvas not implemented (3 — EntropyHistoryChart & other chart tests)
`HTMLCanvasElement.prototype.getContext (without installing the canvas npm
package) is not implemented.` jsdom has no canvas; chart components need it.
**Fix:** add a lightweight stub in `setupTests.js`:
```js
HTMLCanvasElement.prototype.getContext = () => null;
```
(or add `vitest-canvas-mock` if real 2d ops are asserted — not needed if tests
only assert the chart mounts).

### A4. `createRoot(...): Target container is not a DOM element` (3)
Originates from `App.test.js` (see B1) — resolved together with it.

---

## 3. Bucket B — Syntax / wrong-import in test files (targeted, 0 prod code)

### B1. `src/App.test.js` — RollupError: Parse failure at 5:9
It's a **`.js` file containing JSX** (`render(<App />)`) — the React plugin only
applies the JSX loader to `.jsx`/`.tsx`, so `.js` JSX fails to parse. It's also
the **stale Create-React-App template** (`getByText(/learn react/i)`), which the
app has never rendered. **Fix:** rename `App.test.js` → `App.test.jsx` **and**
replace the meaningless assertion with a minimal smoke test (render under the
app's providers/router), or remove the file if a real App smoke test already
exists elsewhere. (This also clears the A4 `createRoot` errors.)

### B2. `src/services/quantumService.test.js` — Failed to resolve `../quantumService`
The test sits at `src/services/quantumService.test.js`; `../quantumService`
points at `src/quantumService` (nonexistent). **Fix:** `../quantumService` →
`./quantumService` (the file is `src/services/quantumService.js`).

### B3. `src/__tests__/adaptive_password.test.tsx` — Failed to resolve `@testing-library/react-hooks`
That package is deprecated/uninstalled; `renderHook` now ships in
`@testing-library/react` (already a dependency). **Fix:** import `renderHook`
from `@testing-library/react` and drop the `react-hooks` import (plus the A2
`jest` shim covers its `jest.*` calls).

### B4. `src/services/quantum/kyberService.test.js` — Failed to resolve entry for `pqc-kyber`
`pqc-kyber`'s `package.json` has no resolvable entry under vite's resolver
(`kyberService.js:166`). **Fix (test-only, minimal):** `vi.mock('pqc-kyber', …)`
in the test with a stub of the small surface it uses, so the unit test exercises
`kyberService`'s logic without the WASM/ESM-broken package. (App build already
handles `pqc-kyber` via the `manualChunks` config; do **not** change the app
import.)

---

## 4. Bucket C — Mock / service-contract drift (align with backend)

These tests exercise frontend services that call backend endpoints. The fix is to
make the **mocked response shape match the real backend contract**, so the test
validates the true contract rather than a guess.

### C1. ChemicalStorage — `default.getProviders is not a function` (11)
`ChemicalStorage.test.jsx:24` `vi.mock('../services/chemicalStorageService')`
provides a `default` object that **omits `getProviders`**, but
`ChemicalStorageModal` calls it on mount. The real service **does** implement
`getProviders()` (`chemicalStorageService.js:338`). **Fix (test-only):** add
`getProviders: vi.fn().mockResolvedValue(<shape>)` to the mock. **Backend
alignment:** read `chemicalStorageService.getProviders` and the Django endpoint
it hits; mirror that response shape (the project's API envelope is
`{ success, data|<fields>, message }` per `password_manager/api_utils.py`).

### C2. zkProof — `encodePoint is not a function` (6)
`commitmentSchnorrProvider.js:130` defines `const encodePoint = …` and the test
does a **named** `import { encodePoint }`, but the module only re-exports it via a
default/object export → named import is `undefined`. **Fix (1 line, prod):**
change line 130 to `export const encodePoint = (point) => point.toRawBytes(true);`
(keep the existing aggregate export). This is the *only* production-code change in
the plan, and it's purely widening visibility for the test. (Not a `@noble/curves`
API problem — `toRawBytes` is valid on the pinned `^1.6.0`.)

### C3. `Cannot read properties of undefined (reading 'data')` (4 — AIAssistant et al.)
Axios mocks resolve to `undefined`, but the service reads `response.data`.
**Fix (test-only):** mocks must resolve `{ data: <payload> }`. **Backend
alignment:** match `<payload>` to the corresponding DRF view/serializer response
(e.g. `ai_assistant` views) so the assertion reflects the real contract.

> `GeneticOAuthCallback.test.jsx` is in this bucket and is **contract-relevant to
> our recent backend change**: PR #290 made `oidc_callback` emit `error` +
> `error_description` (+ `message`) query params. Verify the test asserts on
> `error_description` (the key the component reads) and update it to match the
> backend's current param contract.

---

## 5. Bucket D — UI query drift (test vs current markup)

Component markup evolved; queries are now ambiguous or stale. All test-only.

- **`Found multiple elements with text /encode/i`** (7 — `ultrasonic/fsk.test.js`,
  `entanglement`): replace `getByText(/encode/i)` with a scoped/role-based query
  (`getByRole`, `getAllByText(...)[n]`, or `within(section)`).
- **`Unable to find …`** "Quantum Certificate", "128", "/locked/i", "/error
  correction/i", "/50%/i" (`QuantumCertificateModal`, `QuantumDiceButton`,
  `GeneticDiceButton`, `entanglement`): the text moved or renders async. Fix per
  test: await `findBy*` for async content, or update the query string to the
  current copy. Keep component markup unchanged unless a query reveals a real
  regression.

---

## 6. Lint plan (132 errors; 657 warnings are non-blocking)

Focus on the **132 errors** (warnings are `continue-on-error` and dominated by
`security/detect-object-injection` (346) + `no-unused-vars` (226), which are
advisory):

- **`react/no-unescaped-entities` — 89 (bulk):** unescaped `'`/`"`/`>` in JSX
  text. Fix by escaping (`&apos;`, `&quot;`) or wrapping in `{'…'}`. Not
  auto-fixable by eslint; do it file-by-file across the flagged files (a scripted
  codemod is possible but review each — apostrophes in user-facing copy).
- **`react/no-unknown-property` — 31:** these are **react-three-fiber** intrinsics
  (`<mesh>`, `position`, `args`, `intensity`, …) in the 3D dashboard components,
  which the standard React plugin doesn't recognize. Correct fix: scope an eslint
  override (e.g. `eslint-plugin-react-three-fiber` or a per-file
  `/* eslint-disable react/no-unknown-property */`) for the R3F files only — **not**
  a markup change.
- **`react/display-name` — 1:** add a `displayName` (or name the component).

---

## 7. Suggested PR slicing
1. **PR-A (config/env, biggest win, zero prod code):** A0–A4 + B1–B3
   (`vitest.config.js`, `setupTests.js`, App test rename, import-path fixes).
   Should clear ~33 of the failures/errors.
2. **PR-B (mocks/contracts):** C1–C3 + B4 (test mocks aligned to backend shapes)
   + the single `export const encodePoint` line.
3. **PR-C (UI query drift):** Bucket D query updates.
4. **PR-D (lint errors):** the 132 errors (unescaped entities + R3F override).

(Or land as one PR with commits per bucket — they're low-risk and test-only
except the one `export` line.)

## 8. Verification
- After each bucket: `npm run test:unit` (failure count must strictly drop; no
  new failures) and `npm run lint` (error count must drop).
- `npm run build` must stay green (it already is) — the guardrail that no
  production behavior changed.
- For Bucket C, cross-check each mocked shape against the named backend
  view/serializer before finalizing.

## 9. Risk
- Buckets A, B, D and the C mocks are **test-only** → cannot affect production.
- The single prod change (C2, `export const encodePoint`) only widens an export;
  no behavior change.
- Lint Bucket D's R3F override is config-scoped; unescaped-entity escaping is
  cosmetic JSX text. No runtime risk.
