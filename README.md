# K-Watch

K-Watch is a runtime intrusion detection system for Kubernetes that combines eBPF-based observability with machine learning (Decision Tree) to classify suspicious workload behavior.

It collects syscall events via Tetragon and network flow data via Hubble, processes them through trained Decision Tree models, and generates alerts when anomalies are detected.

## Architecture Overview

```
Tetragon (syscall events)  ──┐
                              ├──► Detector (Python) ──► Alerts (Wazuh)
Hubble  (network flows)    ──┘
```

## Components

| Directory | Description |
|---|---|
| `detector/` | Python service that consumes logs and runs ML inference |
| `feature_engineering/` | Data collection scripts and preprocessing notebook |
| `training/` | Model training notebook (Decision Tree) |
| `deployment_charts/` | Helm charts and Kubernetes manifests |
| `ansible/` | Cluster provisioning playbooks |
| `terraform/` | AWS infrastructure (EC2 for test cluster) |
| `wazuh/` | Wazuh decoder and rules for K-Watch alerts |

## Requirements

### Cluster

- Kubernetes >= 1.28
- [Cilium](https://cilium.io/) with Hubble enabled
- [Tetragon](https://tetragon.io/) with tracing policy from `deployment_charts/tetragon/`

### Detector

- Python >= 3.13
- Dependencies managed with [uv](https://docs.astral.sh/uv/)

```bash
cd detector
uv sync
```

Key Python dependencies: `scikit-learn`, `pandas`, `numpy`, `loguru`, `python-dotenv`

### Infrastructure (optional, for AWS test cluster)

- Terraform >= 1.0
- Ansible >= 2.14
- AWS CLI configured

## Quick Start

```bash
# 1. Provision cluster on AWS
cd terraform && terraform apply

# 2. Install Kubernetes + Cilium + Tetragon
cd ansible && ansible-playbook playbook.yml

# 3. Deploy tracing policies and detector
kubectl apply -f deployment_charts/tetragon/
kubectl apply -f deployment_charts/k-watch/

# 4. Check alerts
kubectl logs -l app=k-watch
```

## Model

Two Decision Tree classifiers are used — one for syscall events and one for network flows. Each supports binary classification (benign/malicious) and multi-class scenario classification. Models are pre-trained and stored in `detector/models/`.

To retrain, use the notebook in `training/train_model.ipynb`.
