# K-Watch

K-Watch: A Hybrid Runtime Intrusion Detection System for Kubernetes Using eBPF and Machine Learning.

It collects syscall events via Tetragon and network flow data via Hubble, processes them through trained Decision Tree models, and generates alerts when anomalies are detected.

## Project Structure

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

### Infrastructure (optional, for AWS test cluster)

- Terraform >= 1.0
- Ansible >= 2.14
- AWS CLI configured

## Quick Start

```bash
$ ./setup-all.sh
```

## Model

Two Decision Tree classifiers are used — one for syscall events and one for network flows. Each supports binary classification (benign/malicious) and multi-class scenario classification. Models are pre-trained and stored in `detector/models/`.

To retrain, use the notebook in `training/train_model.ipynb`.
