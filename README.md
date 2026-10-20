<div align="center">

# K-WATCH

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Detector image](https://img.shields.io/docker/image-size/danielcristh0/kwatch_detector/latest?label=detector%20image)](https://hub.docker.com/r/danielcristh0/kwatch_detector)
[![Python](https://img.shields.io/badge/python-3.13%2B-blue.svg)](pyproject.toml)
[![Kubernetes](https://img.shields.io/badge/kubernetes-1.32%2B-326ce5.svg)](https://kubernetes.io)

[Get Started](#get-started) | [Supported Clusters](#supported-clusters) | [Repository Layout](#repository-layout) | [Full Setup](#full-setup) | [Reproducing the Models](#reproducing-the-models) | [Contributing](CONTRIBUTING.md)

</div>

K-Watch is a runtime intrusion detection system for Kubernetes built on eBPF and
Decision Tree classifiers. It reads two independent streams of kernel telemetry,
syscall events from [Tetragon](https://tetragon.io) and network flows from
[Hubble](https://cilium.io), turns each into per-pod feature vectors, and raises an
alert when a pod's behaviour matches a known attack class.

The two streams are classified separately, then merged, so each alert records which
source saw what. Alerts are written to disk, forwarded to
[Wazuh](https://wazuh.com), and optionally sent to a Discord webhook. Detection
latency is bounded below by the detector's poll interval, 60 seconds by default.

## Get Started

The detector image is public. On a cluster that already runs Cilium and Tetragon, two
commands:

```bash
$ docker pull danielcristh0/kwatch_detector:latest
$ kubectl apply -f deployment_charts/k-watch/detector.yaml
```

That runs the detector as a DaemonSet on every worker node. It tails the Tetragon and
Hubble log files from the host, extracts features per pod, and runs inference with the
Decision Tree models baked into the image. Alerts land in
`/var/log/kwatch/alerts.json`.

```bash
$ kubectl -n k-watch logs -l app=k-watch-detector -f
```

Configure it through the `k-watch-config` ConfigMap and the `k-watch-secrets` Secret,
both in the same manifest.

**The published image is `linux/amd64` only.** On arm64 nodes, such as Graviton or a
Raspberry Pi, build it from `detector/Dockerfile` instead.

For a cluster from scratch, or for the benign and malicious workloads the models were
trained on, see [Full Setup](#full-setup).

## Supported Clusters

K-Watch runs on two cluster layouts, both driven by the same Ansible playbook. The
switch is `k8s_distro` in `ansible/group_vars/all.yml`.

|                | kubeadm on AWS EC2                             | k3s on libvirt VMs               |
| -------------- | ---------------------------------------------- | -------------------------------- |
| `k8s_distro`   | `kubeadm`                                      | `k3s`                            |
| Provisioning   | `terraform/`                                   | `vms/create-vms.sh`              |
| Inventory      | `terraform/generate-inventory.sh` writes it    | `ansible/hosts`, written by hand |
| Distro install | `ansible/roles/master`, `ansible/roles/worker` | `ansible/roles/k3s`              |

The syscall and network datasets were collected on the kubeadm layout. The k3s layout
exists to check that the same detector works on nodes sized for the workload
rather than for the tooling. On k3s the playbook disables flannel, kube-proxy, traefik
and servicelb, because Cilium replaces them.

## Repository Layout

Everything below the cluster is shared by both layouts.

| Path                                             | What it is                          |
| ------------------------------------------------ | ----------------------------------- |
| `detector/`                                      | The DaemonSet that does inference   |
| `feature_engineering/`                           | Data collection and preprocessing   |
| `training/`                                      | Model training notebooks            |
| `ansible/roles/cilium`, `ansible/roles/tetragon` | The two eBPF data sources           |
| `ansible/roles/config`, `ansible/roles/k8s-base` | Host prep, kernel and CRI settings  |
| `ansible/roles/cli-tools`                        | Cluster CLIs on the master          |
| `deployment_charts/`                             | Workloads, detector and Wazuh       |
| `wazuh/`                                         | Decoder and rules for the alerts    |

## Full Setup

### Requirements

- Python >= 3.13
- [uv](https://docs.astral.sh/uv) installed
- [just](https://just.systems/man/en/installation.html) installed
- [kubectl](https://kubernetes.io/docs/tasks/tools) >= 1.32
- [Ansible](https://docs.ansible.com) >= 2.14

**For the AWS EC2 layout:** [Terraform](https://developer.hashicorp.com/terraform/docs) >= 1.0, the [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) configured, and an SSH key pair in `terraform/terraform.tfvars`.

**For the k3s layout:** libvirt with `virsh` and `virt-install`, `cloud-localds` from `cloud-image-utils`, and an SSH public key at `~/.ssh/id_ed25519.pub` or `SSH_KEY` pointing at one.

Sync the dependencies for preprocessing and training:

```bash
$ uv sync
```

### Quick setup

```bash
$ ./setup-all.sh
```

### Step by step

1. Provision the infrastructure. On AWS EC2:

```bash
$ cd terraform
$ terraform init
$ terraform apply
```

Or locally, as libvirt VMs for the k3s layout:

```bash
$ ./vms/create-vms.sh
```

That creates a master, a worker and a SIEM node with pinned IPs, so the inventory
stays valid across reboots. Node sizes are the `VMS` array at the top of the script.

2. Generate the Ansible inventory. On AWS EC2, from the `terraform/` directory you are
already in:

```bash
$ ./generate-inventory.sh
```

It reads the Terraform outputs and writes `ansible/hosts`. On the k3s layout there are
no Terraform outputs to read, so copy `ansible/hosts.example` to `ansible/hosts`, fill
in the IPs that `vms/create-vms.sh` pinned, and set `k8s_distro: k3s` in
`ansible/group_vars/all.yml`.

3. Configure the cluster:

```bash
$ just ansible
```

That installs Kubernetes, Cilium, Hubble and Tetragon on all nodes, then applies the
node labels and taints.

4. Deploy the workloads:

```bash
$ just deploy-all
```

Or one at a time with `just benign-deploy`, `just malicious-deploy` and
`just wazuh-deploy`.

## Reproducing the Models

The models in the detector image come from this repository. The pipeline runs end to
end:

1. `feature_engineering/scripts/collect_data.sh` pulls the raw Tetragon and Hubble
   exports off the cluster nodes.
2. `feature_engineering/pre_processing.ipynb` turns the syscall stream into n-gram
   frequency vectors and the flow stream into per-pod flow-window aggregates. Class
   names come from `feature_engineering/label_mapping.json`.
3. `training/train_model.ipynb` fits the Decision Tree classifiers and writes the
   artifacts the detector loads. `training/read_pkl.ipynb` inspects them.

Syscall and network results come from datasets with different coverage and different
sample counts, so they are reported separately rather than as one number.

## Development and Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development setup. Issues and pull
requests are welcome.

## Acknowledgement

- [Hybrid Runtime Detection of Malicious Containers Using eBPF](https://doi.org/10.32604/cmc.2025.074871)
- [Enhancing intrusion detection in containerized services: Assessing machine learning models and an advanced representation for system call data](https://doi.org/10.1016/j.cose.2025.104438)
- [Tetragon](https://tetragon.io/)
- [Cilium & Hubble](https://cilium.io/)
- [Wazuh](https://wazuh.com/)
