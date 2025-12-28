# Compliance Mapping – SOC 2 & ISO 27001

## 🔐 Access Control
| Control | Implementation |
|------|----------------|
| SOC2 CC6.1 | Django auth, JWT rotation |
| ISO A.9 | RBAC, MFA |

## 🧾 Change Management
| Control | Implementation |
|------|----------------|
| SOC2 CC8.1 | GitHub PR reviews |
| ISO A.12.1 | Versioned builds |

## 📦 Supply Chain
| Control | Implementation |
|------|----------------|
| SOC2 CC3.2 | SBOM, pip-audit |
| ISO A.15 | Dependency policy |

## 🔍 Monitoring
| Control | Implementation |
|------|----------------|
| SOC2 CC7.2 | Sentry, pip-audit |
| ISO A.16 | Incident response |

## 🔄 Vulnerability Management
| Control | Implementation |
|------|----------------|
| SOC2 CC7.1 | safety + pip-audit |
| ISO A.12.6 | CVE triage |

## 🐳 Infrastructure
| Control | Implementation |
|------|----------------|
| SOC2 CC6.7 | Distroless Docker |
| ISO A.14 | Hardened images |

