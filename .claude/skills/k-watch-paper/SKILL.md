---
name: k-watch-paper
description: Writing conventions for K-Watch academic and technical prose — restrained tone, evidence-proportional claims, and the correct terminology for datasets and results. Load when drafting or editing the paper, .docs/ files, README sections, analysis write-ups, or any summary of K-Watch results.
---

# K-Watch writing

Target: restrained technical prose for an academic venue.

## Tone

- Precise and evidence-based. No inflated, promotional, or exaggerated wording.
- No vague or ambiguous phrasing.
- Speculation only when explicitly framed as a limitation, assumption, or future work.
- Claims stay proportional to the evidence. Wording tied to K-Watch's actual
  implementation, dataset, and validation results — not to what the design could do.

## Claim discipline

Separate the modalities. Syscall-only, network-only, and dual-source results come
from datasets with different coverage and different sample counts, so never let a
number from one stand in for the other.

Before writing any figure, check it against `.docs/paper_draft.md`.
`.docs/research_summary.md` and `.docs/current_training_and_two_level_labeling.md`
carry outdated numbers, class names, and a superseded `binary_label` design.

Do not claim full scenario coverage for network-flow results unless
`network_events["scenario_label"].value_counts()` confirms the labels are present with
enough samples. Labels with only a few flow-window samples are **underrepresented**,
not robustly evaluated — say so.

Known weak points that must be reported rather than smoothed over:

- Botnet has very few syscall training instances; its syscall precision is low.
- Database and Data-Caching overlap in the network classifier; Database recall is
  roughly half.
- Detection latency is bounded below by the detector poll interval.

## Terminology

- `scenario_label` for the detailed class; `label` only as its backward-compat alias.
- Avoid `binary_label` unless a future experiment explicitly restores binary
  detection as a trained target.
- Raw Hubble flows (`network_events`) and model-ready rows (`network_dataset`) are
  distinct units — never report one as the other. State `NETWORK_WINDOW_SIZE`
  alongside any network sample count.
- Describe the network features as per-pod, per-session flow-window aggregation.
  `flow_window` is metadata, not a feature.

## Consistency check

`paper_draft.md` currently states two different syscall vector dimensionalities in
different sections. When editing that file, reconcile the number against
`training/models/feature_names_syscall.pkl` rather than copying either figure.
