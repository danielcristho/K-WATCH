import json
from collections import defaultdict
from itertools import islice
from pathlib import Path

import numpy as np

from config import NGRAM_SIZE

with open(Path(__file__).parent / "data" / "syscall_map.json") as _f:
    SYSCALL_MAP = json.load(_f)


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
        by_pod[pod_name]["syscalls"].append(kprobe.get("function_name", "__x64_sys_exit_group"))
        by_pod[pod_name]["namespace"] = pod.get("namespace", "")
        by_pod[pod_name]["node"] = entry.get("node_name", "")
    return by_pod


def extract_features(syscalls, feature_names):
    syscall_nums = [SYSCALL_MAP.get(e, -1) for e in syscalls if e in SYSCALL_MAP]
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


def infer(models, syscalls):
    feature_names = models["feature_syscall"]
    X = extract_features(syscalls, feature_names)
    if X is None:
        return None, None
    scenario_preds = models["syscall_scenario"].predict(X)
    scenario = int(scenario_preds[0])
    # Derive binary from scenario: malicious if label < len(BENIGN_LABELS start)
    from config import BENIGN_LABELS
    binary = 0 if scenario in BENIGN_LABELS else 1
    if models.get("syscall_binary") is not None:
        binary = int(models["syscall_binary"].predict(X)[0])
    return binary, scenario
