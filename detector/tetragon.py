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


def extract_features(syscalls):
    syscall_nums = [SYSCALL_MAP[e] for e in syscalls if e in SYSCALL_MAP]
    if len(syscall_nums) < NGRAM_SIZE:
        return None
    grams = list(ngrams(syscall_nums, NGRAM_SIZE))
    return np.array(grams, dtype=np.float64)


def infer(models, syscalls):
    X = extract_features(syscalls)
    if X is None:
        return None, None
    X_scaled = models["scaler_syscall"].transform(X)
    binary_preds   = models["syscall_binary"].predict(X_scaled)
    scenario_preds = models["syscall_scenario"].predict(X_scaled)
    binary   = int(np.round(binary_preds.mean()))
    scenario = int(np.bincount(scenario_preds.astype(int)).argmax())
    return binary, scenario
