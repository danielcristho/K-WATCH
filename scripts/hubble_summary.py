#!/usr/bin/env python3
"""Summarise Hubble flows for one pod: where it connects, on which ports, and the verdict.

Reads Hubble export JSON on stdin, one flow per line. Usage:
    tail -n N kwatch-workloads.log | hubble_summary.py <pod-name-substring>
    hubble_summary.py --selftest
"""
import collections
import json
import sys


def summarise(lines, pod):
    ports = collections.Counter()
    dests = collections.Counter()
    verdicts = collections.Counter()
    dns = collections.Counter()
    fanout = collections.defaultdict(set)  # dst port -> set of dst IPs
    for line in lines:
        if pod not in line:
            continue
        try:
            flow = json.loads(line).get("flow", {})
        except ValueError:
            continue
        src = flow.get("source") or {}
        if pod not in (src.get("pod_name") or ""):
            continue
        verdicts[flow.get("verdict", "?")] += 1
        l4 = flow.get("l4") or {}
        proto = next(iter(l4), "")
        dport = (l4.get(proto) or {}).get("destination_port")
        if dport:
            ports[f"{proto}/{dport}"] += 1
        ip = (flow.get("IP") or {}).get("destination")
        dst = flow.get("destination") or {}
        name = dst.get("pod_name") or (dst.get("labels") or [""])[0] or ip or "?"
        dests[name] += 1
        if ip and dport:
            fanout[dport].add(ip)
        query = ((flow.get("l7") or {}).get("dns") or {}).get("query")
        if query:
            dns[query] += 1
    return ports, dests, verdicts, dns, fanout


def _selftest():
    sample = [
        json.dumps({"flow": {"source": {"pod_name": "mirai-x"}, "verdict": "FORWARDED",
                             "l4": {"TCP": {"destination_port": 23}}, "IP": {"destination": "10.0.0.1"},
                             "destination": {"labels": ["reserved:world"]}}}),
        json.dumps({"flow": {"source": {"pod_name": "mirai-x"}, "verdict": "DROPPED",
                             "l4": {"TCP": {"destination_port": 23}}, "IP": {"destination": "10.0.0.2"},
                             "destination": {"labels": ["reserved:world"]}}}),
        json.dumps({"flow": {"source": {"pod_name": "other"}, "verdict": "FORWARDED",
                             "l4": {"TCP": {"destination_port": 80}}}}),
    ]
    ports, dests, verdicts, _, fanout = summarise(sample, "mirai")
    assert ports["TCP/23"] == 2, ports
    assert verdicts["DROPPED"] == 1 and verdicts["FORWARDED"] == 1, verdicts
    assert len(fanout[23]) == 2, fanout  # two distinct destination IPs on port 23
    print("selftest ok")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        _selftest()
        return
    pod = sys.argv[1] if len(sys.argv) > 1 else ""
    ports, dests, verdicts, dns, fanout = summarise(sys.stdin, pod)
    total = sum(verdicts.values())
    print(f"pod match: {pod!r}   flows: {total}   verdict: {dict(verdicts)}")
    print("\ndestination ports")
    for p, n in ports.most_common(10):
        print(f"  {n:6}  {p}")
    print("\ndestinations")
    for d, n in dests.most_common(8):
        print(f"  {n:6}  {d}"[:80])
    if dns:
        print("\nDNS queries")
        for q, n in dns.most_common(6):
            print(f"  {n:5}  {q}")
    fan = sorted(((p, len(ips)) for p, ips in fanout.items()), key=lambda x: -x[1])[:5]
    if any(c > 1 for _, c in fan):
        print("\nfan-out (unique dst IPs per port, a scanning tell)")
        for p, c in fan:
            print(f"  {c:5}  port {p}")
    if not total:
        print("\n(no flows in this window: the pod bursts, raise the line count or retry)")


if __name__ == "__main__":
    main()
