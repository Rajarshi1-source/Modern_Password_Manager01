# SOC-2 & ISO-27001 Control Mapping

## SOC-2 CC8 – Change Management
Evidence:
- CI pipeline with signed builds
- SLSA provenance attestation
- Immutable SBOM (CycloneDX + SPDX)

## ISO-27001 A.8.28 – Secure Development
Evidence:
- Dependency audits (Trivy, Grype, Anchore)
- Supply-chain signing (Cosign, Rekor)
- Enforced cryptographic standards (FIPS-ready)

## ISO-27001 A.8.9 – Configuration Management
Evidence:
- Docker distroless images
- IaC-managed CI/CD
- Reproducible builds
