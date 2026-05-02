# In-cluster monitoring (Prometheus, Alertmanager, Grafana)

This stack scrapes the **password-manager** namespace using the same `prometheus.io/*` pod annotations that the backend Deployment already sets (`/metrics` on port 8000).

## Prerequisites

- Cluster with DNS and storage class for PVCs (Grafana).
- **Not** a replacement for managed observability (AWS Managed Prometheus, GMP, Datadog, etc.); use this for self-hosted or dev/staging.

## Apply (order)

```bash
kubectl apply -f k8s/monitoring/prometheus-rbac.yaml
kubectl apply -f k8s/monitoring/prometheus-config.yaml
kubectl apply -f k8s/monitoring/alertmanager-config.yaml
kubectl apply -f k8s/monitoring/prometheus-statefulset.yaml
kubectl apply -f k8s/monitoring/alertmanager-deployment.yaml
kubectl apply -f k8s/monitoring/grafana-deployment.yaml
```

`NetworkPolicy` may need to allow Prometheus → pods on port 8000. If you use `default-deny` policies, add an egress rule from the monitoring `component=prometheus` pods to backend pods or use a `namespaceSelector` (see comment in `network-policy-monitoring.yaml`).

## Optional: Prometheus Operator

If you use `kube-prometheus-stack`, you can instead apply `servicemonitor-backend.yaml` and skip the self-hosted Prometheus StatefulSet, pointing your Operator instance at the `password-manager` namespace.

## Components

| File | Purpose |
|------|---------|
| `prometheus-rbac.yaml` | Role + RoleBinding for in-namespace pod discovery |
| `prometheus-config.yaml` | `prometheus.yml` + recording/alerting rules (ConfigMap) |
| `prometheus-statefulset.yaml` | Prometheus 2.x StatefulSet + Service |
| `alertmanager-config.yaml` | Alertmanager routing (placeholder receiver) |
| `alertmanager-deployment.yaml` | Alertmanager + Service |
| `grafana-deployment.yaml` | Grafana + datasource provisioning + simple Django RED dashboard |
| `servicemonitor-backend.yaml` | Optional ServiceMonitor for prometheus-operator |
| `network-policy-monitoring.yaml` | Example egress from Prometheus to scrape targets |

## Secrets

Set Grafana admin password:

```bash
kubectl create secret generic grafana-admin \
  --namespace=password-manager \
  --from-literal=admin-password='YOUR_STRONG_PASSWORD'
```

(Uncomment `admin` env block in `grafana-deployment.yaml` if you wire this secret.)
