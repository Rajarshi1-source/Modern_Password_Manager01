# Security Tooling Stack

Status as of this PR. CI already runs **Trivy, Grype, Gitleaks, CodeQL,
Bandit, Safety, pip-audit, Syft, Cosign, Codacy, Snyk, StackHawk**. This
document lists the *supplemental* tools we've added and the ones we are
deliberately *not* adding yet (with the cost and trigger).

## Now in CI

| Tool | Layer | Where |
|---|---|---|
| Semgrep (OSS rulesets) | SAST | `.github/workflows/sast-dast.yml` → `semgrep` job |
| Nuclei | DAST | `.github/workflows/sast-dast.yml` → `nuclei` job (main + nightly) |
| `eslint-plugin-security` | SAST (frontend) | `frontend/eslint.config.js` |
| Bandit | SAST (Python) | `.github/workflows/ci.yml` → `backend-test` |
| CodeQL (advanced setup) | SAST | `.github/workflows/codeql.yml` (push/PR to `main`/`develop`, weekly) |
| Playwright E2E | E2E / functional | `.github/workflows/e2e.yml` (PR on `frontend/**`, nightly) — non-blocking |
| OpenSSF Scorecard | Supply-chain posture | `.github/workflows/scorecard.yml` (push to `main`, weekly) |
| `step-security/harden-runner` (audit mode) | Runner egress visibility | First step of `codeql.yml`, `security-multi-scanner.yml`, `ci-sbom.yml`, the `nuclei` job in `sast-dast.yml`, `scorecard.yml`, `e2e.yml`, `load-test.yml` |
| k6 | Load/performance smoke | `.github/workflows/load-test.yml` (`workflow_dispatch` + weekly) — non-blocking |

Semgrep runs on every push/PR using the `p/ci`, `p/security-audit`,
`p/owasp-top-ten`, `p/django`, `p/react`, `p/typescript`, and
`p/dockerfile` community rulesets. Setting `SEMGREP_APP_TOKEN` as a repo
secret unlocks the Pro rules and the Semgrep Cloud dashboard without
further config changes.

Nuclei is gated to main-branch pushes, `workflow_dispatch`, and the
nightly cron (`03:17 UTC`) so PRs stay fast. Set the `NUCLEI_TARGET` repo
variable to point at staging once it is deployed.

### CodeQL: default setup → advanced setup (2026-09-16)

GitHub's CodeQL **default setup** had been enabled at the repo-settings
level since 2026-09-13, which conflicts with this repo's existing
**advanced** `codeql.yml` workflow — both try to upload SARIF under the
same `python` / `javascript-typescript` categories, and GitHub rejects
the advanced workflow's upload with "CodeQL analyses from advanced
configurations cannot be processed when the default setup is enabled".
That made every push to `main` show `Analyze (python)` and
`Analyze (javascript-typescript)` as failing, and had already forced
`codeql.yml`'s `pull_request` trigger to be dropped as a workaround
(default setup covered PRs on its own, at the cost of losing this repo's
custom `security-extended` query suite and the narrow `paths-ignore`
list in `.github/codeql/codeql-config.yml`).

Fix: default setup was switched off repo-wide via
`gh api -X PATCH /repos/<owner>/<repo>/code-scanning/default-setup -f state=not-configured`
(this requires repo-admin credentials — the workflow's own
`GITHUB_TOKEN` cannot call this endpoint and returns HTTP 403). With
default setup off, `codeql.yml`'s `pull_request` trigger was restored,
and an `actions` language entry (`build-mode: none`) was added to its
matrix so GitHub Actions workflow-file scanning — previously covered by
default setup — isn't lost in the switch.

Expect a one-time churn in the Security → Code scanning alert list as
default setup's alerts are reconciled against the advanced workflow's
re-upload under `/language:*` categories; no findings are lost, only
re-categorized.

### Playwright E2E (2026-09-16)

`frontend/playwright.config.js` and 19 spec files under `frontend/e2e/`
had existed with zero CI wiring since they were added — `@playwright/
test` was a `devDependency` but nothing ever invoked `playwright test`.
`e2e.yml` now runs them, **Chromium only** (`npm run test:e2e:ci` →
`playwright test --project=chromium`), not the full 5-browser matrix the
config declares — that config also sets `workers: 1` and `retries: 2` on
CI, so 19 specs × 5 projects serially would be far too slow for a PR
check. The job is `continue-on-error: true`: the specs are a mixed bag,
some mock every network call and some hit `/api/` directly against the
Django backend started by this workflow, so day-one green across all 19
is not expected. Treat this as diagnostic, not a gate, until the suite's real
pass rate is known.

### OpenSSF Scorecard (2026-09-16)

`scorecard.yml` runs the [OSSF Scorecard](https://scorecard.dev) checks
(branch protection, token permissions, pinned actions, dependency
update tooling, etc.) on push to `main` and weekly, publishing results
(`publish_results: true`) to the public Scorecard API/badge rather than
relying on the upstream team's own periodic scan of public repos. Because
of that setting, the job running `ossf/scorecard-action` is written to
satisfy the action's strict workflow-restriction rules: no top-level
`env`/`defaults`, no workflow-level write permissions, only that job may
set `id-token: write`, and its steps are limited to the tool's approved
allow-list (`actions/checkout`, `actions/upload-artifact`,
`github/codeql-action/upload-sarif`, `ossf/scorecard-action`,
`step-security/harden-runner`).

### Harden-Runner, audit mode only (2026-09-16)

`step-security/harden-runner` was added as the first step of every
supply-chain-relevant job across `codeql.yml`, `security-multi-scanner.yml`,
`ci-sbom.yml`, the `nuclei` job in `sast-dast.yml`, `scorecard.yml`,
`e2e.yml`, and `load-test.yml`, with `egress-policy: audit`. Audit mode
only observes and logs a job's outbound network calls in its summary —
it cannot block a step or fail a build — so this is purely additive
visibility, not a new gate. It was deliberately **not** added to the
`semgrep` job in `sast-dast.yml`: that job runs inside a `container:`
(`returntocorp/semgrep`), and Harden-Runner does not work inside
containerized jobs.

### k6 load test (2026-09-16)

`load-test.yml` runs `tests/load/k6-vault-smoke.js` on `workflow_dispatch`
and weekly only — never on push or PR, since a load test has no business
gating a merge. It reuses the boot sequence already proven in
`stackhawk.yml` (Postgres 17/pgvector + Redis 7 service containers, the
disk-space cleanup the ML dependency stack needs, `manage.py migrate`,
`runserver` in the background, then a health-check poll) rather than the
`docker compose` approach the Nuclei job uses, which is already
soft-failed there and not proven reliable enough to build a new workflow
on. The script ramps to ~50 VUs against the unauthenticated `/api/health/`
and `/` endpoints — the playbook's 1,000-concurrent-user target is not
realistic on a shared GitHub-hosted runner backed by a Django dev server,
so this is a regression smoke test, not a capacity benchmark. Non-blocking
(`continue-on-error: true`); the k6 summary JSON is uploaded as an
artifact.

## Deferred — add at these triggers

| Tool | Cost | Trigger to buy |
|---|---|---|
| Burp Suite Professional | $449/user/yr | First paying customer or first external pentest |
| External pentest (Radically Open Security / Include Security) | $15–30k per engagement | Before enterprise launch |
| SonarCloud | $10–150/mo | If code-quality debt becomes a board-level metric |
| CodeRabbit | $12–24/user/mo | When PR review throughput bottlenecks the team |
| Nessus Pro | ~$4k/yr | If we self-host infrastructure beyond K8s |

## Explicitly skipped

Checkmarx, Veracode, Pentera — enterprise SKUs with contract minimums
that outweigh the marginal value over the OSS stack above for a project
of this size.

Also evaluated and skipped as part of the 2026-09-16 CI maturity pass:

- **Socket.dev, FOSSA** — require paid accounts and tokens this repo
  doesn't have; wiring them in now would only add permanently-skipped
  jobs.
- **Burp Suite, Nessus, Acunetix, Detectify, Intruder, Pentera** —
  commercial/manual tools, already listed above as deferred/skipped.
- **TruffleHog** — Gitleaks already runs as a genuinely blocking secret
  scanner; adding a second secret scanner duplicates coverage.
- **Checkov** — Trivy's `config` scanner plus `trivy-policy-data/`
  already covers IaC misconfiguration.
- **ruff** — the backend has standardized on flake8/black/isort; ruff
  would duplicate coverage and introduce conflicting lint opinions.
- **mypy --strict on the crypto module** — genuinely valuable, but needs
  its own error-cleanup pass first; not a drop-in addition.
- **Making existing non-blocking scanners blocking** — Semgrep, Bandit,
  Trivy (FS), Grype, Snyk, `npm audit`, Codacy, StackHawk, the frontend
  Vitest job, and the `backend-ci.yml` pytest job all currently run with
  `continue-on-error`/`|| true`. Only Gitleaks, `pip-audit` in
  `security-multi-scanner.yml`, the main `ci.yml` pytest job, and the
  SBOM/Cosign pipeline actually gate merges today; widening that set is
  a deliberate future decision, not bundled into this additive pass.
- **Playbook performance section** (read replicas, async views, orjson,
  index/partitioning strategy, TanStack Query migration) — architectural,
  multi-week efforts that need real profiling data first, not a CI
  workflow addition.

## AI reviewer loop

Claude Code is already in use for architecture and security-focused
review. If we need a second AI reviewer on PRs, CodeRabbit is the first
addition — it is GitHub-native and does not require changing the branch
protection rules.
