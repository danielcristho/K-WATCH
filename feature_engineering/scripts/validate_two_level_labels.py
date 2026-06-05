#!/usr/bin/env python3
"""Validate K-IDS multi-class scenario labels before model training."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def load_label_config(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def parse_required_labels(value: str) -> set[int]:
    if not value.strip():
        return set()
    return {int(part.strip()) for part in value.split(",") if part.strip()}


def validate_dataset(path: Path, name: str, class_names: list[str], required_labels: set[int]) -> bool:
    print(f"\n=== {name} ===")
    print(f"Dataset: {path}")

    if not path.exists():
        print("ERROR: dataset file does not exist")
        return False

    df = pd.read_csv(path)
    ok = True

    required_columns = {"pod_name", "label", "scenario_label"}
    missing = sorted(required_columns - set(df.columns))
    if missing:
        print(f"ERROR: missing columns: {missing}")
        return False

    if "binary_label" in df.columns:
        print("ERROR: binary_label is not expected in multi-class-only datasets")
        ok = False

    if not df["label"].equals(df["scenario_label"]):
        print("ERROR: label column is not an alias of scenario_label")
        ok = False

    scenario_counts = df["scenario_label"].value_counts().sort_index()
    print(f"Rows: {len(df):,}")
    print(f"Scenario distribution: {scenario_counts.to_dict()}")

    valid_labels = set(range(len(class_names)))
    observed_labels = set(scenario_counts.index.astype(int))
    invalid_labels = sorted(observed_labels - valid_labels)
    if invalid_labels:
        print(f"ERROR: labels outside configured scenario_class_names range: {invalid_labels}")
        ok = False

    for label in sorted(required_labels):
        class_name = class_names[label] if 0 <= label < len(class_names) else str(label)
        count = int(scenario_counts.get(label, 0))
        if count == 0:
            print(f"ERROR: scenario_label {label} ({class_name}) is missing")
            ok = False
        else:
            print(f"OK: scenario_label {label} ({class_name}) has {count:,} rows")

    return ok


def validate_config(path: Path) -> tuple[bool, list[str]]:
    print("=== Label Config ===")
    print(f"Config: {path}")

    if not path.exists():
        print("ERROR: label config file does not exist")
        return False, []

    cfg = load_label_config(path)
    class_names = cfg.get("scenario_class_names", cfg.get("class_names", []))
    rules = cfg.get("rules", [])
    ok = True

    if not class_names:
        print("ERROR: scenario_class_names is empty or missing")
        ok = False
    else:
        print(f"Scenario classes ({len(class_names)}): {class_names}")

    if "binary_class_names" in cfg:
        print("ERROR: binary_class_names is not expected in multi-class-only label config")
        ok = False

    for idx, rule in enumerate(rules):
        if "binary_label" in rule:
            print(f"ERROR: rule {idx} ({rule.get('pattern')}) still contains binary_label")
            ok = False
        label = int(rule.get("scenario_label", rule.get("label", -1)))
        if label < 0 or label >= len(class_names):
            print(f"ERROR: rule {idx} ({rule.get('pattern')}) uses invalid scenario_label={label}")
            ok = False

    return ok, class_names


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default="feature_engineering/label_mapping.json",
        type=Path,
        help="Path to label_mapping.json",
    )
    parser.add_argument(
        "--syscall",
        default="feature_engineering/dataset/syscall_dataset.csv",
        type=Path,
        help="Path to syscall dataset CSV",
    )
    parser.add_argument(
        "--network",
        default="feature_engineering/dataset/network_flow_dataset.csv",
        type=Path,
        help="Path to network dataset CSV",
    )
    parser.add_argument(
        "--required-syscall-labels",
        default="",
        help="Comma-separated scenario labels required in the syscall dataset.",
    )
    parser.add_argument(
        "--required-network-labels",
        default="",
        help="Comma-separated scenario labels required in the network dataset.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_ok, class_names = validate_config(args.config)
    if not class_names:
        print("\nValidation failed. Fix label config before checking datasets.")
        return 1

    syscall_ok = validate_dataset(
        args.syscall,
        "Syscall Dataset",
        class_names,
        parse_required_labels(args.required_syscall_labels),
    )
    network_ok = validate_dataset(
        args.network,
        "Network Dataset",
        class_names,
        parse_required_labels(args.required_network_labels),
    )

    if config_ok and syscall_ok and network_ok:
        print("\nValidation passed. Dataset is ready for multi-class training.")
        return 0

    print("\nValidation failed. Fix preprocessing output before training.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
