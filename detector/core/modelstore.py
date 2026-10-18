"""Model storage and loading."""

from dataclasses import dataclass
from typing import Any

import joblib

from core.config import MODEL_DIR

BUNDLES = {
    "syscall": {
        "scenario": "dt_syscall_scenario_model.pkl",
        "binary":   "dt_syscall_binary_model.pkl",
        "features": "feature_names_syscall.pkl",
    },
    "network": {
        "scenario": "dt_network_scenario_model.pkl",
        "binary":   "dt_network_binary_model.pkl",
        "features": "feature_names_network.pkl",
    },
}
SCENARIO_NAMES_FILE = "scenario_class_names.pkl"
OPTIONAL_ROLES = {"binary"}


@dataclass
class ModelBundle:
    """Everything one source needs to make a prediction."""

    scenario: Any
    binary: Any | None
    features: list


def _load(filename: str, required: bool):
    path = MODEL_DIR / filename
    if path.exists():
        return joblib.load(path)
    if required:
        raise FileNotFoundError(f"Required model not found: {path}")
    return None


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
            loaded[role] = _load(filename, required=role not in OPTIONAL_ROLES)
        bundles[source] = ModelBundle(**loaded)

    if on_file:
        on_file(SCENARIO_NAMES_FILE)
    return bundles, _load(SCENARIO_NAMES_FILE, required=True)


def total_files() -> int:
    return sum(len(r) for r in BUNDLES.values()) + 1
