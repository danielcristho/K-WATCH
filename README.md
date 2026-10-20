# K-WATCH

K-Watch is a hybrid runtime intrusion detection system for Kubernetes that uses eBPF and machine learning.

It collects syscall events via Tetragon and network flow data via Hubble, runs them through trained Decision Tree models, and generates alerts when malicious activity is detected.

It runs on two cluster layouts. The evaluation reported in the paper was collected on
AWS EC2 with [kubeadm](https://kubernetes.io/docs/reference/setup-tools/kubeadm). The
edge layout runs [k3s](https://docs.k3s.io) on local libvirt VMs, to check that the
same detector works on nodes sized for the workload rather than for the tooling.

Both are driven by the same Ansible playbook. The switch is `k8s_distro` in
`ansible/group_vars/all.yml`, set to either `kubeadm` or `k3s`. On k3s the playbook
disables flannel, kube-proxy, traefik and servicelb, because Cilium replaces them.

Which directory serves which layout:

|                   | kubeadm on AWS EC2                               | k3s on libvirt VMs                   |
| ----------------- | ------------------------------------------------ | ------------------------------------ |
| Provisioning      | `terraform/`                                     | `vms/create-vms.sh`                  |
| Inventory         | `terraform/generate-inventory.sh` writes it       | `ansible/hosts`, written by hand      |
| Distro install    | `ansible/roles/master`, `ansible/roles/worker`   | `ansible/roles/k3s`                  |
| `k8s_distro`      | `kubeadm`                                        | `k3s`                                |

Everything below the cluster is shared by both:

| Path                                                       | What it is                          |
| ---------------------------------------------------------- | ----------------------------------- |
| `ansible/roles/config`, `ansible/roles/k8s-base`           | Host prep, kernel and CRI settings  |
| `ansible/roles/cilium`, `ansible/roles/tetragon`           | eBPF data sources                   |
| `ansible/roles/cli-tools`                                  | Cluster CLIs on the master          |
| `deployment_charts/`                                       | Workloads, detector, Wazuh charts   |
| `detector/`                                                | The DaemonSet that does inference   |
| `wazuh/`                                                   | Decoder and rules for the alerts    |

## Requirements

- Python >= 3.13
- [uv](https://docs.astral.sh/uv) installed
- [just](https://just.systems/man/en/installation.html) installed
- [kubectl](https://kubernetes.io/docs/tasks/tools) >= 1.32
- [Ansible](https://docs.ansible.com) >= 2.14

For the AWS EC2 layout:

- [Terraform](https://developer.hashicorp.com/terraform/docs) >= 1.0
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) configured
- SSH key pair configured in `terraform/terraform.tfvars`

For the k3s layout:

- libvirt with `virsh` and `virt-install`
- `cloud-localds` from `cloud-image-utils`
- An SSH public key at `~/.ssh/id_ed25519.pub`, or `SSH_KEY` pointing at one

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

On AWS EC2:

```bash
$ cd terraform
$ terraform init
$ terraform apply
```

Or locally, as libvirt VMs for the k3s layout:

```bash
$ ./vms/create-vms.sh
```

Creates a master, a worker and a SIEM node with pinned IPs, so the inventory stays
valid across reboots. Node sizes are the `VMS` array at the top of the script.

2. Generate Ansible inventory

On AWS EC2, from the `terraform/` directory you are already in:

```bash
$ ./generate-inventory.sh
```

Reads Terraform outputs and writes `ansible/hosts` automatically.

On the k3s layout there are no Terraform outputs to read, so copy
`ansible/hosts.example` to `ansible/hosts` and fill in the IPs that
`vms/create-vms.sh` pinned, then set `k8s_distro: k3s` in
`ansible/group_vars/all.yml`.

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

TBD

## Acknowledgement

- [Hybrid Runtime Detection of Malicious Containers Using eBPF](https://doi.org/10.32604/cmc.2025.074871)
- [Enhancing intrusion detection in containerized services: Assessing machine learning models and an advanced representation for system call data](https://doi.org/10.1016/j.cose.2025.104438)
- [Tetragon](https://tetragon.io/)
- [Cilium & Hubble](https://cilium.io/)
- [Wazuh](https://wazuh.com/)
