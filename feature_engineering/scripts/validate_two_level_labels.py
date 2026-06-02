#!/usr/bin/env python3
"""Validate K-IDS two-level labels before model training."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


DEFAULT_REQUIRED_SCENARIOS = {
    8: "Compromised-Backend",
    9: "Compromised-Cache",
    10: "Compromised-Frontend",
}


def load_label_config(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def validate_dataset(path: Path, name: str, required_scenarios: dict[int, str]) -> bool:
    print(f"\n=== {name} ===")
    print(f"Dataset: {path}")

    if not path.exists():
        print("ERROR: dataset file does not exist")
        return False

    df = pd.read_csv(path)
    ok = True

    required_columns = {"pod_name", "label", "scenario_label", "binary_label"}
    missing = sorted(required_columns - set(df.columns))
    if missing:
        print(f"ERROR: missing columns: {missing}")
        return False

    if not df["label"].equals(df["scenario_label"]):
        print("ERROR: label column is not an alias of scenario_label")
        ok = False

    scenario_counts = df["scenario_label"].value_counts().sort_index()
    binary_counts = df["binary_label"].value_counts().sort_index()

    print(f"Rows: {len(df):,}")
    print(f"Binary distribution: {binary_counts.to_dict()}")
    print(f"Scenario distribution: {scenario_counts.to_dict()}")

    for label, class_name in required_scenarios.items():
        count = int(scenario_counts.get(label, 0))
        if count == 0:
            print(f"ERROR: scenario_label {label} ({class_name}) is missing")
            ok = False
        else:
            print(f"OK: scenario_label {label} ({class_name}) has {count:,} rows")

    compromised = df[df["scenario_label"].isin(required_scenarios)]
    if not compromised.empty:
        invalid_binary = compromised[compromised["binary_label"] != 1]
        if not invalid_binary.empty:
            print("ERROR: compromised scenario rows must have binary_label = 1")
            print(invalid_binary[["pod_name", "scenario_label", "binary_label"]].head(20))
            ok = False

    return ok


def validate_config(path: Path, required_scenarios: dict[int, str]) -> bool:
    print("=== Label Config ===")
    print(f"Config: {path}")

    if not path.exists():
        print("ERROR: label config file does not exist")
        return False

    cfg = load_label_config(path)
    scenario_class_names = cfg.get("scenario_class_names", [])
    rules = cfg.get("rules", [])
    ok = True

    for label, expected_name in required_scenarios.items():
        actual_name = scenario_class_names[label] if label < len(scenario_class_names) else None
        if actual_name != expected_name:
            print(
                f"ERROR: scenario_class_names[{label}] is {actual_name!r}, "
                f"expected {expected_name!r}"
            )
            ok = False
        else:
            print(f"OK: scenario_class_names[{label}] = {expected_name}")

    expected_rules = {
        "backend-api": 8,
        "cache-worker": 9,
        "frontend": 10,
    }
    for pattern, expected_label in expected_rules.items():
        matching = [
            rule for rule in rules
            if pattern in str(rule.get("pattern", "")).lower().replace("_", "-")
        ]
        if not matching:
            print(f"ERROR: missing rule for pattern {pattern!r}")
            ok = False
            continue

        if not any(
            int(rule.get("scenario_label", rule.get("label", -1))) == expected_label
            and int(rule.get("binary_label", -1)) == 1
            for rule in matching
        ):
            print(
                f"ERROR: rule for {pattern!r} must use "
                f"scenario_label={expected_label}, binary_label=1"
            )
            ok = False
        else:
            print(f"OK: rule {pattern!r} -> scenario {expected_label}, binary 1")

    return ok


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default="config/label_mapping.json",
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
        "--allow-missing-network-compromised",
        action="store_true",
        help="Only require compromised scenario labels in the syscall dataset.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    required = DEFAULT_REQUIRED_SCENARIOS

    config_ok = validate_config(args.config, required)
    syscall_ok = validate_dataset(args.syscall, "Syscall Dataset", required)
    network_required = {} if args.allow_missing_network_compromised else required
    network_ok = validate_dataset(args.network, "Network Dataset", network_required)

    if config_ok and syscall_ok and network_ok:
        print("\nValidation passed. Dataset is ready for training.")
        return 0

    print("\nValidation failed. Fix preprocessing output before training.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
