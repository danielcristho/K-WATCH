"""Tetragon syscall telemetry: grouping, feature extraction, and inference."""

import json
import re
from collections import defaultdict
from itertools import islice
from pathlib import Path

import numpy as np

from config import NGRAM_SIZE

ARCH_PREFIX = re.compile(r"^__(?:x64|arm64|ia32)_")

with open(Path(__file__).parent / "data" / "syscall_map.json") as _f:
    SYSCALL_MAP = {ARCH_PREFIX.sub("", k): v for k, v in json.load(_f).items()}


def ngrams(seq, n):
    it = iter(seq)
    window = list(islice(it, n))
    if len(window) == n:
        yield tuple(window)
    for item in it:
        window = window[1:] + [item]
        yield tuple(window)


def group_events(events):
    by_pod = defaultdict(lambda: {"syscalls": [], "namespace": "", "node": ""})
    for entry in events:
        kprobe = entry.get("process_kprobe") or entry.get("process_exec") or entry.get("process_exit")
        if not kprobe:
            continue
        pod = kprobe.get("process", {}).get("pod", {})
        pod_name = pod.get("name", "")
        if not pod_name:
            continue
        by_pod[pod_name]["syscalls"].append(kprobe.get("function_name", "sys_exit_group"))
        by_pod[pod_name]["namespace"] = pod.get("namespace", "")
        by_pod[pod_name]["node"] = entry.get("node_name", "")
    return by_pod


def extract_features(syscalls, feature_names):
    """Encode a syscall sequence as an n-gram frequency vector
    Tetragon emits arch-specific symbols (__x64_sys_read on amd64,
    __arm64_sys_read on arm64), so the prefix is stripped before lookup.
    """
    names = [ARCH_PREFIX.sub("", e) for e in syscalls]
    syscall_nums = [SYSCALL_MAP[n] for n in names if n in SYSCALL_MAP]
    if len(syscall_nums) < NGRAM_SIZE:
        return None
    grams = list(ngrams(syscall_nums, NGRAM_SIZE))

    # Build feature vector as one-hot over known ngram strings
    ngram_strs = ["_".join(str(n) for n in g) for g in grams]
    feat_index = {f: i for i, f in enumerate(feature_names)}
    vec = np.zeros(len(feature_names), dtype=np.float64)
    for s in ngram_strs:
        if s in feat_index:
            vec[feat_index[s]] += 1
    return vec.reshape(1, -1)


def decisive_features(model):
    """Indices the tree actually splits on, a fraction of the full feature set."""
    f = model.tree_.feature
    return f[f >= 0]


def infer(models, syscalls):
    feature_names = models["feature_syscall"]
    X = extract_features(syscalls, feature_names)
    if X is None:
        return None, None
    if not X[0, decisive_features(models["syscall_scenario"])].any():
        return None, None  # the tree saw no evidence, abstain rather than trust its default leaf
    scenario_preds = models["syscall_scenario"].predict(X)
    scenario = int(scenario_preds[0])
    # Derive binary from scenario: malicious if label < len(BENIGN_LABELS start)
    from config import BENIGN_LABELS
    binary = 0 if scenario in BENIGN_LABELS else 1
    if models.get("syscall_binary") is not None:
        binary = int(models["syscall_binary"].predict(X)[0])
    return binary, scenario


if __name__ == "__main__":
    # Same behaviour on amd64 and arm64 must give the same vector
    feats = ["0_1_41_42_44", "1_41_42_44_45"]
    amd64 = ["__x64_sys_read", "__x64_sys_write", "__x64_sys_socket",
             "__x64_sys_connect", "__x64_sys_sendto", "__x64_sys_recvfrom"]
    arm64 = [n.replace("__x64_", "__arm64_") for n in amd64]

    v_amd, v_arm = extract_features(amd64, feats), extract_features(arm64, feats)
    assert v_amd is not None and v_arm is not None, "arch prefix not normalised"
    assert (v_amd == v_arm).all(), f"arch mismatch: {v_amd} != {v_arm}"
    assert v_amd.sum() == 2, f"expected both ngrams matched, got {v_amd}"
    assert extract_features(["__x64_sys_read"], feats) is None, "short seq must return None"

    class _Stub:
        """A tree that splits only on feats[0]; verdict=None means predict must never run."""

        def __init__(self, verdict=None):
            self.tree_ = type("t", (), {"feature": np.array([0, -2, -2])})()
            self._verdict = verdict

        def predict(self, X):
            assert self._verdict is not None, "predict ran without evidence"
            return [self._verdict]

    def _models(verdict=None):
        return {"feature_syscall": feats, "syscall_scenario": _Stub(verdict), "syscall_binary": None}

    blind = ["__x64_sys_openat"] * 6  # real tokens, but its ngram is not in feats
    assert extract_features(blind, feats).sum() == 0, "expected an all-zero vector"
    assert infer(_models(), blind) == (None, None), "no evidence must abstain"
    assert infer(_models(verdict=0), amd64) == (1, 0), "evidence must reach the model"
    print("ok: architecture-neutral features, and no verdict without evidence")
