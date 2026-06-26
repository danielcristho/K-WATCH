# K-Watch

K-Watch is a hybrid runtime intrusion detection system for Kubernetes that uses eBPF and machine learning.

It collects syscall events via Tetragon and network flow data via Hubble, runs them through trained Decision Tree models, and generates alerts when malicious activity is detected.

This project was deployed on AWS EC2 using [kubeadm](https://kubernetes.io/docs/reference/setup-tools/kubeadm).

## Requirements

- Python >= 3.13
- [uv](https://docs.astral.sh/uv) installed
- [just](https://just.systems/man/en/installation.html) installed
- [kubectl](https://kubernetes.io/docs/tasks/tools) >= 1.32
- [Terraform](https://developer.hashicorp.com/terraform/docs) >= 1.0
- [Ansible](https://docs.ansible.com) >= 2.14
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) configured
- SSH key pair configured in `terraform/terraform.tfvars`

Sync all deps for pre-processing, training

```bash
$ uv sync
```

## Setup

<details>
<summary>Quick setup</summary>

```bash
$ ./setup-all.sh
```

</details>

<details>
<summary>Step by step setup</summary>

1. Provision infrastructure

```bash
$ cd terraform
$ terraform init
$ terraform apply
```

2. Generate Ansible inventory

```bash
$ ./generate-inventory.sh
```

Reads Terraform outputs and writes the hosts file to `ansible/hosts` automatically.

3. Configure cluster

```bash
$ just ansible
```

Installs Kubernetes, Cilium, Hubble, and Tetragon on all nodes. Also applies labels and taints.

4. Deploy workloads

```bash
$ just benign-deploy
$ just malicious-deploy
$ just wazuh-deploy
```

Or all at once:

```bash
$ just deploy-all
```

</details>

<details>
<summary>Detector</summary>

The detector runs as a DaemonSet on each worker node. It tails Tetragon and Hubble logs, extracts features per pod, and runs inference using pre-trained Decision Tree models. Alerts are written to `/var/log/kwatch/alerts.json`, forwarded to Wazuh, and sent to Discord.

```bash
$ kubectl apply -f deployment_charts/k-watch/detector.yaml
```

</details>

Configure via the `k-watch-config` ConfigMap and `k-watch-secrets` Secret in the same file.

## Pre Processing

will be fill

## Training

will be fill

## Model

will be fill

## Acknowledgement

- [Hybrid Runtime Detection of Malicious Containers Using eBPF](https://doi.org/10.32604/cmc.2025.074871)

- [Enhancing intrusion detection in containerized services: Assessing machine learning models and an advanced representation for system call data](https://doi.org/10.1016/j.cose.2025.104438)

- [Tetragon](https://tetragon.io/)

- [Cilium & Hubble](https://cilium.io/)

- [Wazuh](https://wazuh.com/)
