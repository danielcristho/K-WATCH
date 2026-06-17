# K-Watch

K-Watch: A Hybrid Runtime Intrusion Detection System for Kubernetes Using eBPF and Machine Learning.

It collects syscall events via Tetragon and network flow data via Hubble, processes them through trained Decision Tree models, and generates alerts when anomalies are detected.

This project was deployed using [kubeadm](https://kubernetes.io/docs/reference/setup-tools/kubeadm).

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

### Infrastructure & Cluster

- [kubectl](https://kubernetes.io/docs/tasks/tools/) >= 1.32
- [Cilium](https://cilium.io/) with Hubble enabled
- [Tetragon](https://tetragon.io/) with tracing policy from `deployment_charts/tetragon/`
- [Terraform](https://developer.hashicorp.com/terraform/docs) >= 1.0
- [Ansible](https://docs.ansible.com) >= 2.14
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.htmlinst) configured

### Detector

- Python >= 3.13
- Dependencies managed with [uv](https://docs.astral.sh/uv/)

```bash
cd detector
uv sync
```


## Quick Start

```bash
$ ./setup-all.sh
```

## Model

Two Decision Tree classifiers are used — one for syscall events and one for network flows. Each supports binary classification (benign/malicious) and multi-class scenario classification. Models are pre-trained and stored in `detector/models/`.

To retrain, use the notebook in `training/train_model.ipynb`.

```
┌─────────────────┐     Deploy      ┌──────────────────────────────────────────────┐
│  Decision Tree  │ ─────────────►  │              K-Watch Detector Pipeline        │
│     Model       │                 │                                              │
└─────────────────┘                 │  ┌─────────────┐      ┌──────────────────┐  │
                                    │  │  Tetragon   │─────►│                  │  │
                                    │  │  (Syscall)  │      │  ML Inference    │  │
                                    │  └─────────────┘      │  (Binary +       │  │
                                    │                       │   Scenario)      │  │
                                    │  ┌─────────────┐      │                  │  │
                                    │  │   Hubble    │─────►│                  │  │
                                    │  │  (Network)  │      └────────┬─────────┘  │
                                    │  └─────────────┘               │            │
                                    └───────────────────────────────┼────────────┘
                                                                    │
                                              ┌─────────────────────┼──────────────────┐
                                              ▼                     ▼                  ▼
                                    ┌──────────────┐    ┌──────────────────┐   ┌──────────────┐
                                    │  alerts.json │    │     Discord      │   │    Wazuh     │
                                    │   (log file) │    │  (Push Notif)   │   │  (SIEM/Rules)│
                                    └──────────────┘    └──────────────────┘   └──────────────┘
                                                                                      │
                                                                               ┌──────▼──────┐
                                                                               │   Kibana/   │
                                                                               │  Dashboard  │
                                                                               └─────────────┘

```