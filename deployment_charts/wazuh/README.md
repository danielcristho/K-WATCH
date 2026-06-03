# Wazuh SIEM Deployment Guide

## Prerequisites

- Cluster running with 3 nodes (master, worker, siem)
- Node `siem` labeled and tainted:
  ```
  kubectl label node siem node-role.kubernetes.io/siem="" --overwrite
  kubectl taint node siem role=siem:NoSchedule --overwrite
  ```
- `just` task runner installed
- `KUBECONFIG` pointing to cluster (auto-set in justfile)

## Deployment Steps

### 1. Full Deploy (recommended)

```bash
just wazuh-deploy
just wazuh-init-security
```

`wazuh-deploy` runs: `wazuh-storage` → `wazuh-certs` → `wazuh-secrets` → `helm install`

`wazuh-init-security` runs: wait for indexer → `securityadmin.sh` → restart dashboard

### 2. Step-by-step

```bash
# Install local-path StorageClass
just wazuh-storage

# Generate TLS certificates
just wazuh-certs

# Create K8s namespace & secrets
just wazuh-secrets

# Helm install
export KUBECONFIG=ansible/kubeconfig
helm upgrade --install wazuh ./deployment_charts/wazuh -n wazuh

# Initialize security (run once after indexer is ready)
just wazuh-init-security
```

### 3. Upgrade after config changes

```bash
export KUBECONFIG=ansible/kubeconfig
helm upgrade --install wazuh ./deployment_charts/wazuh -n wazuh
```

## Useful Commands

```bash
# Check pod status
just wazuh-status

# View manager logs
just wazuh-logs

# Check indexer health
just wazuh-health

# Port-forward dashboard to localhost
just wazuh-dashboard

# Uninstall
just wazuh-clean
```

## Access

| Service | URL | Credentials |
|---------|-----|-------------|
| Wazuh Dashboard | `http://<SIEM_PUBLIC_IP>:30443` | admin / admin |
| Wazuh API | `https://<SIEM_PUBLIC_IP>:55000` | wazuh-wui / W4zuh.Admin!2024#Sec |

## Architecture

```
┌─────────────────────────────────────────────────┐
│ Node: siem (taint: role=siem:NoSchedule)        │
│                                                 │
│  ┌─────────────┐  ┌──────────────┐             │
│  │  Indexer    │  │   Manager    │             │
│  │  (9200)     │←─│  (1514/55000)│             │
│  └──────┬──────┘  └──────────────┘             │
│         │                                       │
│  ┌──────┴──────┐                               │
│  │  Dashboard  │ ← NodePort 30443              │
│  │  (5601)     │                               │
│  └─────────────┘                               │
└─────────────────────────────────────────────────┘

┌────────────────────┐  ┌────────────────────────┐
│ Node: k8s-master   │  │ Node: k8s-worker-1     │
│  └─ wazuh-agent    │  │  └─ wazuh-agent        │
└────────────────────┘  └────────────────────────┘
```

## Troubleshooting

### Pod stuck in Pending / FailedScheduling

**Cause:** Taint not tolerated.

```bash
kubectl describe pod -n wazuh <pod-name> | grep -A5 Events
```

**Fix:** Ensure node has correct label and chart values match:
```yaml
# values.yaml
nodeSelector:
  node-role.kubernetes.io/siem: ""
tolerations:
  - key: "role"
    operator: "Equal"
    value: "siem"
    effect: "NoSchedule"
```

### Indexer: "OpenSearch Security not initialized"

**Cause:** Security plugin needs to be initialized after first deploy.

**Fix:** Run security admin (also available as `just wazuh-init-security`):
```bash
kubectl exec -n wazuh wazuh-indexer-0 -- bash -c '
  export JAVA_HOME=/usr/share/wazuh-indexer/jdk
  /usr/share/wazuh-indexer/plugins/opensearch-security/tools/securityadmin.sh \
    -cd /usr/share/wazuh-indexer/config/opensearch-security/ \
    -cacert /usr/share/wazuh-indexer/config/certs/root-ca.pem \
    -cert /usr/share/wazuh-indexer/config/certs/admin.pem \
    -key /usr/share/wazuh-indexer/config/certs/admin-key.pem \
    -h localhost -nhnv
'
kubectl -n wazuh delete pod -l app=wazuh-dashboard
```

Then login with `admin` / `admin`.

### Manager: "Error 5007 - Insecure user password"

**Cause:** Wazuh requires strong password (uppercase, lowercase, number, special char, min 8 chars, no username substring).

**Fix:** Update `credentials.apiUser.password` in `values.yaml`, then:
```bash
kubectl -n wazuh delete statefulset wazuh-manager
kubectl -n wazuh delete pvc manager-data-wazuh-manager-0
helm upgrade --install wazuh ./deployment_charts/wazuh -n wazuh
```

### Dashboard: "server is not ready yet"

**Cause:** Dashboard can't connect to indexer (SSL mismatch or indexer not initialized).

**Fix:** Check dashboard logs:
```bash
kubectl logs -n wazuh -l app=wazuh-dashboard --tail=30
```

If `ResponseError` to indexer, ensure:
- Indexer is running & healthy
- Dashboard config uses `http://` if security is disabled
- Restart dashboard: `kubectl -n wazuh delete pod -l app=wazuh-dashboard`

### Dashboard: "ENOENT opensearch_dashboards.yml"

**Cause:** Config file not mounted.

**Fix:** Ensure `dashboard-config.yaml` configmap exists and is mounted in dashboard deployment template via `subPath`.

### local-path-provisioner stuck in Pending

**Cause:** All nodes have taints, provisioner has no tolerations.

**Fix:** Patch deployment:
```bash
kubectl -n local-path-storage patch deployment local-path-provisioner \
  --type=json -p='[{"op":"add","path":"/spec/template/spec/tolerations","value":[{"operator":"Exists"}]}]'
```

### Cannot reach Dashboard from browser

**Cause:** Security group doesn't expose NodePort.

**Fix:** Ensure SIEM security group allows port 30000-32767 (NodePort range). Apply via:
```bash
cd terraform && terraform apply -auto-approve
```

### Indexer: "access denied FilePermission certs"

**Cause:** Java SecurityManager blocks reading cert files from non-config paths.

**Fix:** Certs must be mounted inside `/usr/share/wazuh-indexer/config/certs/` and referenced with relative path `certs/` in `opensearch.yml`. Ensure secret volume has `defaultMode: 0444`.

### Nuclear Option (full reset)

```bash
just wazuh-clean
kubectl delete pvc -n wazuh --all
just wazuh-deploy
```
