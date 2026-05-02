# Enterprise architecture — operations map

This document ties **load balancing**, **probes**, **scaling**, **bulkheads**, and **consistency** to concrete artifacts in this repository.

## Traffic path: reverse proxy vs load balancer

- **Edge (HTTP/S):** [k8s/ingress.yaml](../k8s/ingress.yaml) configures the **nginx Ingress controller** as an **Layer 7 reverse proxy**: TLS termination, host/path routing (`yourapp.com` → frontend, `api.yourapp.com` → API paths), rate limits, WebSocket upgrades, and security headers. In cloud deployments, a **cloud load balancer** typically sits in front of the cluster and forwards to the Ingress controller Service.
- **In-cluster (TCP):** Kubernetes **ClusterIP Services** ([k8s/deployment.yaml](../k8s/deployment.yaml)) provide **Layer 4–style** endpoint distribution (kube-proxy) to pod backends on each Service port.
- **Algorithms:** Default **round-robin** across ready endpoints. WebSockets use **hash-by client IP** (`nginx.ingress.kubernetes.io/upstream-hash-by`) for stickiness.
- **Horizontal scaling:** [k8s/hpa.yaml](../k8s/hpa.yaml) scales Deployments by CPU/memory; backend uses multiple replicas with **RollingUpdate** (`maxUnavailable: 0`).

## Health, readiness, and metrics

| Concern | Path | Use |
|--------|------|-----|
| **Liveness** (process up) | `/live/` or `/api/live/` | Cheap; no DB. Kubernetes **livenessProbe** uses `/live/`. |
| **Readiness** (accept traffic) | `/ready/` or `/api/ready/` | Single `SELECT 1` to PostgreSQL. **readinessProbe** uses `/ready/`. |
| **Deep health** | `/health/`, `/api/health/`, `/ht/` | DB + cache + django-health-check; use for monitoring dashboards, not high-frequency probes. |
| **Prometheus** | `/metrics` | `django_prometheus` + middleware in Django settings; backend pods annotated for scrape in-cluster ([k8s/deployment.yaml](../k8s/deployment.yaml), [k8s/monitoring/](../k8s/monitoring/)). |

## Bulkhead (failure isolation)

- **Deployments:** Separate **backend**, **websocket**, **celery-worker**, **frontend** ([k8s/deployment.yaml](../k8s/deployment.yaml)).
- **Celery queues:** Task routes isolate workloads by queue ([password_manager/password_manager/celery.py](../password_manager/password_manager/celery.py)) — e.g. `blockchain`, `ml`, `analytics`.
- **Scheduler:** **Celery beat** runs **one replica** (single scheduler); [k8s/cronjobs.yaml](../k8s/cronjobs.yaml) for time-based jobs.

## Consistency model

| Store | Typical consistency | Notes |
|-------|---------------------|--------|
| **PostgreSQL** | **Strong** (per transaction) | Authoritative vault metadata and backup rows. |
| **Redis** (cache, broker) | **Eventual** | Cache may lag; do not rely on Redis alone for security decisions. |
| **Celery / async tasks** | **Eventual** | Work completes after the API response. |
| **Client sync** | Configurable | See `conflictResolution: 'server-wins'` in shared frontend config. |

## Observability stack (optional self-hosted)

See [k8s/monitoring/README.md](../k8s/monitoring/README.md) for Prometheus, Alertmanager, and Grafana manifests aligned with existing `/metrics` scraping.

## Related docs

- [VALET_KEY_CLOUD_BACKUP.md](VALET_KEY_CLOUD_BACKUP.md) — presigned URL flow for large backups.
