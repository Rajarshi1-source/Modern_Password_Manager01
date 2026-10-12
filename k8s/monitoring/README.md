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
kubectl apply -f k8s/monitoring/alertmanager-deployment.yaml   # needs the alertmanager-receiver Secret, see below
kubectl apply -f k8s/monitoring/network-policy-monitoring.yaml
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
| `alertmanager-config.yaml` | Alertmanager routing; receiver URL read from the `alertmanager-receiver` Secret |
| `alertmanager-deployment.yaml` | Alertmanager + Service |
| `grafana-deployment.yaml` | Grafana + datasource provisioning + simple Django RED dashboard |
| `servicemonitor-backend.yaml` | Optional ServiceMonitor for prometheus-operator |
| `network-policy-monitoring.yaml` | Egress from Prometheus to scrape targets; Prometheus → Alertmanager and Alertmanager → receiver (HTTPS) |

## Secrets

Set Grafana admin password:

```bash
kubectl create secret generic grafana-admin \
  --namespace=password-manager \
  --from-literal=admin-password='YOUR_STRONG_PASSWORD'
```

(Uncomment `admin` env block in `grafana-deployment.yaml` if you wire this secret.)

## Alert delivery

Alertmanager sends every alert to one receiver, `default`, whose endpoint is
read from a Secret at send time (`url_file`), so no credential is in git:

```bash
kubectl create secret generic alertmanager-receiver \
  --namespace=password-manager \
  --from-literal=webhook-url='https://hooks.example.com/your/endpoint'
```

The receiver is a generic webhook (Alertmanager's JSON payload). For Slack or
PagerDuty, swap `webhook_configs` in `alertmanager-config.yaml` for the
commented `slack_configs` (`api_url_file`) or `pagerduty_configs`
(`routing_key_file`) block and store that key in the same Secret.

The Secret volume is **not optional**: until it exists the Alertmanager pod
stays in `ContainerCreating`. That is deliberate, because a receiver with no
integration delivers alerts nowhere. `network-policy-monitoring.yaml` must be
applied too: under `default-deny-all` Alertmanager otherwise cannot receive
alerts from Prometheus or reach the receiver.

Test delivery once after configuring:

```bash
kubectl -n password-manager port-forward svc/alertmanager 9093 &
curl -XPOST localhost:9093/api/v2/alerts -H 'Content-Type: application/json' \
  -d '[{"labels":{"alertname":"DeliveryTest","severity":"info"}}]'
```

For delivery that is itself monitored, add an always-firing "watchdog" rule
routed to an external dead-man's-switch service. Nothing in-cluster can tell
you that Alertmanager itself is down.

## Backups

The `db-backup` CronJob (`k8s/cronjobs.yaml`) writes age-encrypted dumps to the
`db-backups` PVC (`k8s/backup-pvc.yaml`). The backend exports
`vault_backup_last_success_timestamp_seconds{backup="db-backup"}`, which is
stamped only after a file is complete and renamed into place, never on failure.
It is 0 if no backup has ever succeeded. Rules in `prometheus-config.yaml`:

- `VaultBackupStale`: no successful backup for more than 26 hours (critical);
- `VaultBackupMetricMissing`: the gauge is not being scraped, so staleness is
  not being watched.

Before the first run, put the age public key in `app-config`
(`BACKUP_AGE_RECIPIENT`); generate the pair off-cluster with `age-keygen`, and
keep the private key offline. Verify a backup end to end with
`k8s/restore-drill-job.yaml`.
