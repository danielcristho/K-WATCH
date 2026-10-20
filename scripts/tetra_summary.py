#!/usr/bin/env python3
"""Summarise Tetragon JSON events for one pod: what it exec'd and which syscalls it hit.

Reads Tetragon export JSON on stdin, one event per line. Usage:
    tail -n N tetragon.log | tetra_summary.py <pod-name-substring>
    tetra_summary.py --selftest
"""
import collections
import json
import sys

KINDS = ("process_exec", "process_kprobe", "process_exit", "process_tracepoint")


def summarise(lines, pod):
    execs = collections.Counter()
    kprobes = collections.Counter()
    last = None
    for line in lines:
        if pod not in line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        kind = next((k for k in KINDS if k in event), None)  # top level also has time, node_name
        if kind is None:
            continue
        body = event[kind]
        proc = body.get("process") or {}
        if pod not in (proc.get("pod") or {}).get("name", ""):
            continue
        last = event.get("time")
        if kind == "process_exec":
            execs[(proc.get("binary", ""), (proc.get("arguments") or "")[:70])] += 1
        elif kind == "process_kprobe":
            kprobes[body.get("function_name", "?")] += 1
    return execs, kprobes, last


def _selftest():
    sample = [
        json.dumps({"time": "t1", "process_exec": {"process": {"pod": {"name": "mirai-x"}, "binary": "/usr/bin/nmap", "arguments": "-sS"}}}),
        json.dumps({"time": "t2", "process_kprobe": {"process": {"pod": {"name": "mirai-x"}}, "function_name": "__x64_sys_connect"}}),
        json.dumps({"time": "t3", "process_kprobe": {"process": {"pod": {"name": "other"}}, "function_name": "__x64_sys_mmap"}}),
    ]
    execs, kprobes, _ = summarise(sample, "mirai")
    assert sum(execs.values()) == 1, execs
    assert sum(kprobes.values()) == 1, kprobes  # the "other" pod is excluded
    print("selftest ok")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        _selftest()
        return
    pod = sys.argv[1] if len(sys.argv) > 1 else ""
    execs, kprobes, last = summarise(sys.stdin, pod)
    print(f"pod match: {pod!r}   last event: {last}")
    print(f"\nexec ({sum(execs.values())} total)")
    for (binary, args), n in execs.most_common(15):
        print(f"  {n:4}  {binary} {args}".rstrip()[:96])
    print(f"\nsyscalls ({sum(kprobes.values())} total)")
    for fn, n in kprobes.most_common(20):
        print(f"  {n:5}  {fn}")
    if not execs and not kprobes:
        print("\n(no traced events: the pod may be compute-bound, invisible to the syscall source)")


if __name__ == "__main__":
    main()
