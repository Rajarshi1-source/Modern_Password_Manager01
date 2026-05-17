# Kyverno policies (optional cluster governance)

These policies complement [k8s/network-policy.yaml](../../network-policy.yaml) by validating **workload manifests** at admission time. They require **[Kyverno](https://kyverno.io/)** installed on the cluster.

## Apply

```bash
kubectl apply -f k8s/policy/kyverno/
```

Policies use `validationFailureAction: audit` first so violations are logged without blocking rollouts. Switch to `enforce` when ready.

## Included rules

| File | Intent |
|------|--------|
| `disallow-privileged-containers.yaml` | Pods in `password-manager` must not set `privileged: true`. |
| `require-non-root-containers.yaml` | Containers should declare `runAsNonRoot` / non-zero UID (aligned with existing deployments). |

Adjust `match` blocks if you add init containers that require exceptions.
