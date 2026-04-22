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

Semgrep runs on every push/PR using the `p/ci`, `p/security-audit`,
`p/owasp-top-ten`, `p/django`, `p/react`, `p/typescript`, and
`p/dockerfile` community rulesets. Setting `SEMGREP_APP_TOKEN` as a repo
secret unlocks the Pro rules and the Semgrep Cloud dashboard without
further config changes.

Nuclei is gated to main-branch pushes, `workflow_dispatch`, and the
nightly cron (`03:17 UTC`) so PRs stay fast. Set the `NUCLEI_TARGET` repo
variable to point at staging once it is deployed.

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

## AI reviewer loop

Claude Code is already in use for architecture and security-focused
review. If we need a second AI reviewer on PRs, CodeRabbit is the first
addition — it is GitHub-native and does not require changing the branch
protection rules.
