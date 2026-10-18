---
name: k-watch-portability
description: Rules for keeping K-Watch runnable on any CPU architecture (amd64, arm64/Graviton) and any Kubernetes distro (kubeadm, k3s, edge clusters). Load when touching terraform, ansible, Dockerfiles, TracingPolicy, the syscall map, or when asked about arm64, Graviton, k3s, edge deployment, or multi-arch images.
---

# K-Watch portability

Design rule: **one artifact, detected at runtime.** No arm64 branch, no k3s fork.
Anything that differs per platform becomes a variable or a runtime lookup.

## Syscall telemetry — the trap

Tetragon emits arch-specific symbols: `__x64_sys_openat` on amd64,
`__arm64_sys_openat` on arm64. Two rules follow.

**TracingPolicy uses bare names.** Tetragon prepends the arch prefix itself when
`syscall: true`:

```yaml
kprobes:
  - call: "sys_openat"   # not __x64_sys_openat
    syscall: true
```

An arch-prefixed policy attaches zero kprobes on the other architecture.

**The prefix is stripped before lookup**, in `detector/tetragon.py`:

```python
ARCH_PREFIX = re.compile(r"^__(?:x64|arm64|ia32)_")
SYSCALL_MAP = {ARCH_PREFIX.sub("", k): v for k, v in json.load(_f).items()}
```

**Never renumber `detector/data/syscall_map.json` per architecture.** Those integers
are x86-derived but they act as *token IDs* that the trained models were fitted on.
Remapping them to real arm64 syscall numbers silently invalidates every model.

Failure mode if any of this regresses: no exception, no log. `extract_features`
returns `None`, syscall detection just goes quiet.

`feature_engineering/pre_processing.ipynb` carries its own inline `SYSCALL_MAP` still
keyed on `__x64_sys_*`. It needs the same normalisation before arm64-collected data
can be preprocessed.

## Container images

Multi-arch already: `python:3.13-slim` (detector base), `cloudsuite/data-caching`,
`mariadb`, `mysql`, `postgres`, `redis`, `alpine`, `busybox`, the Wazuh stack.

**amd64-only** — verify before assuming a class is reproducible on arm64:

- `miningcontainers/xmrig` and `timonmat/xmr-stak-cpu` → the whole **Cryptominer**
  class (label 1) is unavailable on Graviton.
- `severalnines/sysbench` → a Database load generator.

Check any image before relying on it:

```bash
docker manifest inspect <image> | grep architecture
```

The detector image needs no Dockerfile change, only a multi-arch build:

```bash
docker buildx build --platform linux/amd64,linux/arm64 -t <repo>:<tag> --push .
```

## Terraform

`terraform/main.tf` resolves the AMI instead of pinning it. Switching platform is one
variable:

```hcl
architecture = "arm64"   # x86_64 | arm64
```

- `data.aws_ami.ubuntu` filters by name and `architecture`. Canonical names arm64
  images `arm64` but x86_64 images `amd64` — that's what `local.ami_arch` handles.
- `local.instance_presets` pairs the arch with its instance family (t3 / t4g) so an
  arm64 AMI can never land on an Intel instance. Override with
  `node_instance_type` / `siem_instance_type`.
- Workers are `count = var.worker_count`, named `k8s-worker-N`. Edge clusters can run
  a single one. `moved` blocks map the pre-count resources, so keep them.
- Removing the pinned AMI means `plan` will want to replace existing instances. Always
  `plan` before `apply` on a live cluster.

## Ansible

`k8s_distro` in `group_vars/all.yml` selects `kubeadm` or `k3s`.

- kubeadm-only tasks in `roles/k8s-base` are gated on it. k3s ships its own
  containerd and kubectl, so the apt/containerd block is skipped.
- `roles/k3s` installs server on `masters`, agent on everything else, and must pass
  `--flannel-backend=none --disable-network-policy --disable-kube-proxy` so Cilium can
  take over. Standard k3s needs **no** `cni.binPath`/`cni.confPath` override.
- Pod CIDR `10.42.0.0/16` is k3s's default and already matches `k8s_pod_cidr`.
- `roles/cli-tools` installs helm/cilium/hubble CLIs and derives the download arch
  from `ansible_architecture` (`aarch64` → `arm64`). Hardcoding `amd64` here breaks
  Graviton.
- Roles that install via Helm — `cilium`, `tetragon` — are already arch and distro
  neutral; their images are multi-arch.

## What is already portable — leave it alone

- Detector hostPaths `/var/run/cilium/{tetragon,hubble}` are managed by
  Cilium/Tetragon, not the distro. Identical on kubeadm, k3s, and EKS.
- The network model's features are protocol/port/TCP-flag counts — architecture has
  no bearing on them.

## Model transfer across architectures

Token IDs stay stable, but arm64 libc takes different syscall paths (`openat` instead
of `open`, `newfstatat` instead of `stat`, `clone` instead of `fork`), so n-gram
distributions shift. Treat "x86-trained model evaluated on arm64" as a measurement to
report, not an assumption. The network model should transfer directly; the syscall
model is the one to validate.
