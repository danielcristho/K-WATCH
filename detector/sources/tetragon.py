"""Tetragon syscall telemetry: 5-gram frequency vectors over kprobe events."""

import json
import re
from collections import defaultdict
from itertools import islice
from pathlib import Path

import numpy as np

from core.config import MIN_SYSCALL_THRESHOLD, NGRAM_SIZE
from core.contracts import ModelBackedSource, PodTelemetry, Verdict

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


def extract_features(syscalls, feature_names):
    """Encode a syscall sequence as an n-gram frequency vector.

    Tetragon emits arch-specific symbols (__x64_sys_read on amd64,
    __arm64_sys_read on arm64), so the prefix is stripped before lookup.
    """
    names = [ARCH_PREFIX.sub("", e) for e in syscalls]
    syscall_nums = [SYSCALL_MAP[n] for n in names if n in SYSCALL_MAP]
    if len(syscall_nums) < NGRAM_SIZE:
        return None

    feat_index = {f: i for i, f in enumerate(feature_names)}
    vec = np.zeros(len(feature_names), dtype=np.float64)
    for gram in ngrams(syscall_nums, NGRAM_SIZE):
        key = "_".join(str(n) for n in gram)
        if key in feat_index:
            vec[feat_index[key]] += 1
    return vec.reshape(1, -1)


def decisive_features(model):
    """Indices the tree actually splits on, a fraction of the full feature set."""
    f = model.tree_.feature
    return f[f >= 0]


class TetragonSource(ModelBackedSource):
    """Syscalls answer what a pod did."""

    name = "syscall"
    count_field = "syscall_count"

    def __init__(self, bundle, min_records: int = MIN_SYSCALL_THRESHOLD):
        super().__init__(bundle, min_records)

    def group(self, entries):
        by_pod = defaultdict(PodTelemetry)
        for entry in entries:
            kprobe = (entry.get("process_kprobe")
                      or entry.get("process_exec")
                      or entry.get("process_exit"))
            if not kprobe:
                continue
            pod = kprobe.get("process", {}).get("pod", {})
            pod_name = pod.get("name", "")
            if not pod_name:
                continue
            tele = by_pod[pod_name]
            tele.records.append(kprobe.get("function_name", "sys_exit_group"))
            tele.namespace = pod.get("namespace", "")
            tele.node = entry.get("node_name", "")
        return by_pod

    def infer(self, records):
        X = extract_features(records, self.bundle.features)
        if X is None:
            return None
        if not X[0, decisive_features(self.bundle.scenario)].any():
            return None
        scenario = self.scenario_of(X)
        return Verdict(self.binary_of(scenario, X), scenario)


if __name__ == "__main__":
    from core.modelstore import ModelBundle

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

    def _source(verdict=None):
        return TetragonSource(ModelBundle(scenario=_Stub(verdict), binary=None, features=feats))

    blind = ["__x64_sys_openat"] * 6  # real tokens, but its ngram is not in feats
    assert extract_features(blind, feats).sum() == 0, "expected an all-zero vector"
    assert _source().infer(blind) is None, "no evidence must abstain"
    assert _source(verdict=0).infer(amd64) == Verdict(binary=1, scenario=0), "evidence must reach the model"

    grouped = _source().group([
        {"process_kprobe": {"function_name": "__x64_sys_read",
                            "process": {"pod": {"name": "p", "namespace": "ns"}}},
         "node_name": "n1"},
    ])
    assert grouped["p"].records == ["__x64_sys_read"], "grouping must keep the call"
    assert grouped["p"].namespace == "ns" and grouped["p"].node == "n1", "pod metadata lost"

    print("ok: architecture-neutral features, no verdict without evidence, grouping intact")
