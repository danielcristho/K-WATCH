"""Model storage and loading."""

from dataclasses import dataclass
from typing import Any

import joblib

from core.config import BENIGN_LABELS, MODEL_DIR

BUNDLES = {
    "syscall": {
        "scenario": "dt_syscall_scenario_model.pkl",
        "features": "feature_names_syscall.pkl",
    },
    "network": {
        "scenario": "dt_network_scenario_model.pkl",
        "features": "feature_names_network.pkl",
    },
}
SCENARIO_NAMES_FILE = "scenario_class_names.pkl"


@dataclass
class ModelBundle:
    """Everything one source needs to make a prediction."""

    scenario: Any
    features: list


def _load(filename: str):
    path = MODEL_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Required model not found: {path}")
    return joblib.load(path)


def _check_benign_labels(names, labels=None):
    """BENIGN_LABELS indexes the trained class order, so a stale value must not pass."""
    labels = BENIGN_LABELS if labels is None else labels
    valid = set(range(len(names)))
    if not labels or not labels < valid:
        raise ValueError(
            f"BENIGN_LABELS={sorted(labels)} must be a non-empty proper subset "
            f"of the {len(names)} trained classes 0-{len(names) - 1}: {list(names)}"
        )


def load_models(on_file=None):
    """Load all models from disk, returning a dict of ModelBundle and the scenario names."""
    if not MODEL_DIR.exists():
        raise FileNotFoundError(f"Model directory not found: {MODEL_DIR}")
    bundles = {}
    for source, roles in BUNDLES.items():
        loaded = {}
        for role, filename in roles.items():
            if on_file:
                on_file(filename)
            loaded[role] = _load(filename)
        bundles[source] = ModelBundle(**loaded)

    if on_file:
        on_file(SCENARIO_NAMES_FILE)
    names = _load(SCENARIO_NAMES_FILE)
    _check_benign_labels(names)
    return bundles, names


def total_files() -> int:
    return sum(len(r) for r in BUNDLES.values()) + 1
