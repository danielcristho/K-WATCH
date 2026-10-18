---
name: k-watch
description: Core context for the K-Watch Kubernetes runtime IDS repo — pipeline layout, label taxonomy, model artifacts, and which docs are authoritative. Load when working anywhere in this repo (detector, feature_engineering, training, ansible, terraform, deployment_charts) or when asked about K-Watch architecture, datasets, labels, or results.
---

# K-Watch

Kubernetes runtime IDS. Dual-source eBPF telemetry → Decision Tree multi-class
classifier → alerts to Wazuh and Discord.

- **Tetragon** — syscall-level telemetry (kprobes).
- **Hubble/Cilium** — network flow metadata (L3/L4).
- **Decision Tree** — one model per modality, 9-class scenario classification.

## Pipeline

```
terraform/            AWS EC2 + VPC + security groups
  ansible/            K8s + Cilium/Hubble + Tetragon (roles/, playbook.yml)
  deployment_charts/  benign-workloads, malicious, wazuh, k-watch detector DaemonSet
  feature_engineering/
    scripts/collect_data.sh   pulls Tetragon + Hubble logs off the nodes
    pre_processing.ipynb      raw logs -> dataset/*.csv
    label_mapping.json        namespace + pod-name pattern -> scenario_label
  training/train_model.ipynb  -> training/models/*.pkl
  detector/main.py            poll loop: tail logs -> infer -> alerts.json
```

Detector models are a **copy** of `training/models/` into `detector/models/`. After
retraining, copy them across or the DaemonSet keeps serving the old ones.

## Label taxonomy

Nine classes, defined in `feature_engineering/label_mapping.json`:

| Label | Binary | Class |
|---|---|---|
| 0 | malicious | Botnet |
| 1 | malicious | Cryptominer |
| 2 | malicious | Trojan-Agent |
| 3 | malicious | Cloud Attack |
| 4 | malicious | Brute-Force |
| 5 | benign | Data-Caching |
| 6 | benign | Database |
| 7 | benign | Redis |
| 8 | benign | Web-Serving |

Terminology rules:

- `scenario_label` is the real target. `label` is a backward-compat alias for it.
- Do **not** introduce or depend on `binary_label` as a trained target. The detector
  derives binary from `scenario_label in config.BENIGN_LABELS` (`{5,6,7,8}`).
  `models.py` can load optional `dt_*_binary_model.pkl` files, but they are absent
  and the two-level-labeling design in `.docs/` is superseded.
- Labeling is rule-based at preprocessing time: namespace + pod-name substring, rules
  sorted longest-pattern-first. Unmatched pods are dropped from the dataset.

## Which docs are authoritative

- `.docs/paper_draft.md` — **current** source of truth for results and dataset stats.
- `.docs/AGENTS.md` — writing and dataset conventions, still current.
- `.docs/research_summary.md` — **stale** numbers and class names (Miner,
  Media-Streaming) that no longer match `label_mapping.json`.
- `.docs/current_training_and_two_level_labeling.md` — **superseded**. Describes
  `binary_label` and Compromised-* labels 8/9/10 that do not exist.

Never quote figures from the stale two without checking `paper_draft.md` first.

## Data unit gotchas

- Raw Hubble flows (`network_events`) and model-ready rows (`network_dataset`) are
  different units. Many flows aggregate into one feature row, so the network dataset
  row count is far smaller than the raw flow count. State `NETWORK_WINDOW_SIZE`
  whenever reporting network sample counts.
- `flow_window` is metadata, never a model feature.
- Hubble endpoint labeling must consider both `source.pod_name` and
  `destination.pod_name`. Do not assume `traffic_direction` points at the workload
  that should carry the label.
- Collect Hubble exports from **every** Cilium agent pod — export files are local to
  each agent, so reading one pod misses flows from other nodes.
- Prefer group-aware splits on `session_id`. With few sessions, say so: train/test
  label balance is unstable.

See also: `k-watch-portability` for architecture and distro work, `k-watch-paper`
for writing.
