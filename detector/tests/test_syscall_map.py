"""Every syscall the TracingPolicy monitors must tokenize to something the model knows."""

import json
import re
from pathlib import Path

import joblib

DETECTOR = Path(__file__).resolve().parent.parent
POLICY = DETECTOR.parent / "deployment_charts" / "tetragon" / "tracing-policy-ids.yaml"
ARCH_PREFIX = re.compile(r"^__(?:x64|arm64|ia32)_")


def monitored_syscalls():
    return set(re.findall(r'- call:\s*"(sys_\w+)"', POLICY.read_text()))


def token_map():
    raw = json.loads((DETECTOR / "sources" / "data" / "syscall_map.json").read_text())
    return {ARCH_PREFIX.sub("", k): v for k, v in raw.items()}


def model_tokens():
    names = joblib.load(DETECTOR / "models" / "feature_names_syscall.pkl")
    return {int(t) for f in names for t in re.findall(r"\d+", str(f))}


def test_policy_syscalls_are_mapped():
    missing = monitored_syscalls() - token_map().keys()
    assert not missing, f"monitored but unmapped: {sorted(missing)}"


def test_tokens_exist_in_the_trained_model():
    tmap, known = token_map(), model_tokens()
    # A token the model never saw makes its n-grams silently drop out of the feature vector
    strays = {s: tmap[s] for s in monitored_syscalls() if tmap[s] not in known}
    assert not strays, f"tokens absent from feature_names_syscall.pkl: {strays}"


if __name__ == "__main__":
    test_policy_syscalls_are_mapped()
    test_tokens_exist_in_the_trained_model()
    print(f"ok: {len(monitored_syscalls())} monitored syscalls, all tokens known to the model")
