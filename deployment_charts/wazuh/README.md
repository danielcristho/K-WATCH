# Wazuh SIEM Deployment for K-IDS

Simplified Wazuh deployment for the K-IDS research project.
All Wazuh server components run on a dedicated Kubernetes node.

## Architecture

```
K8s Cluster
├── Node 1 (master)  — control plane + workloads
├── Node 2 (worker)  — workloads (benign + malicious pods)
└── Node 3 (wazuh)   — dedicated (tainted), Wazuh components only
    ├── Wazuh Indexer (1 replica)
    ├── Wazuh Manager (1 replica)
    └── Wazuh Dashboard (1 replica)

+ Wazuh Agent DaemonSet on Node 1 & 2
```

## Prerequisites

- Kubernetes 1.25+
- Helm 3.x
- A dedicated node labeled `role=wazuh` with taint `dedicated=wazuh:NoSchedule`
- `local-path` StorageClass (or equivalent)

## Deployment Steps

### 1. Prepare the dedicated node

```bash
# Join the new t3 node to the cluster, then:
kubectl taint nodes <wazuh-node-name> dedicated=wazuh:NoSchedule
kubectl label nodes <wazuh-node-name> role=wazuh
```

### 2. Install local-path provisioner (if not already installed)

```bash
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/v0.0.26/deploy/local-path-storage.yaml
```

### 3. Generate certificates

```bash
cd certs/
./generate_certs.sh
```

### 4. Create namespace and secrets

```bash
kubectl create namespace wazuh

cd certs/

kubectl -n wazuh create secret generic indexer-certs \
  --from-file=root-ca.pem --from-file=node.pem \
  --from-file=node-key.pem --from-file=admin.pem \
  --from-file=admin-key.pem

kubectl -n wazuh create secret generic manager-certs \
  --from-file=root-ca.pem --from-file=manager.pem \
  --from-file=manager-key.pem

kubectl -n wazuh create secret generic dashboard-certs \
  --from-file=root-ca.pem --from-file=dashboard.pem \
  --from-file=dashboard-key.pem
```

### 5. Deploy with Helm

```bash
cd ..
helm install wazuh . -n wazuh
```

### 6. Verify deployment

```bash
kubectl -n wazuh get all
```

All pods should be in `Running` state.

### 7. Access Dashboard

The dashboard is exposed via NodePort on port `30443`:

```
https://<wazuh-node-ip>:30443
Username: admin
Password: SecretPassword
```

## Integration with K-IDS ML Model

The ML model sends alerts to Wazuh via the Wazuh API:

```python
import requests

WAZUH_API = "https://<wazuh-manager-ip>:55000"
AUTH = ("wazuh-wui", "MyS3cr3tP4ssw0rd")

def send_alert(alert_data):
    requests.post(
        f"{WAZUH_API}/active-response",
        json=alert_data,
        auth=AUTH,
        verify=False
    )
```

Or via custom log files monitored by the Wazuh Agent on K8s nodes.

## Troubleshooting

### Indexer CrashLoopBackOff
Ensure `vm.max_map_count=262144` on the wazuh node:
```bash
sudo sysctl -w vm.max_map_count=262144
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf
```

### PVC stuck in Pending
Verify local-path provisioner is running:
```bash
kubectl get pods -n local-path-storage
```
