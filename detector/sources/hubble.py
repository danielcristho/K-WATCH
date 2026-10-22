"""Hubble network telemetry: flow-window aggregates over Cilium flow records."""

import json
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from core.config import MIN_FLOW_THRESHOLD
from core.contracts import ModelBackedSource, PodTelemetry, Verdict

with open(Path(__file__).parent / "data" / "ports.json") as _f:
    _ports = json.load(_f)

MINING_PORTS = set(_ports["mining"])
DB_PORTS     = set(_ports["database"])
HTTP_PORTS   = set(_ports["http"])
NETWORK_WINDOW_SIZE = 100


def extract_features(flows, feature_names):
    if not flows:
        return None

    agg = defaultdict(int)
    agg["flow_count"] = len(flows)
    src_ports, dst_ports = set(), set()

    for f in flows:
        l4    = f.get("l4", {})
        tcp   = l4.get("TCP", {})
        udp   = l4.get("UDP", {})
        flags = tcp.get("flags", {})
        dst   = int(tcp.get("destination_port", udp.get("destination_port", 0)) or 0)
        src   = int(tcp.get("source_port",      udp.get("source_port",      0)) or 0)
        src_ports.add(src)
        dst_ports.add(dst)

        agg["proto_TCP_count"]         += int(bool(tcp))
        agg["proto_UDP_count"]         += int(bool(udp))
        agg["proto_OTHER_count"]       += int(not tcp and not udp)
        agg["dir_EGRESS_count"]        += int(f.get("traffic_direction") == "EGRESS")
        agg["dir_INGRESS_count"]       += int(f.get("traffic_direction") == "INGRESS")
        agg["verdict_FORWARDED_count"] += int(f.get("verdict") == "FORWARDED")
        agg["verdict_DROPPED_count"]   += int(f.get("verdict") == "DROPPED")
        agg["verdict_TRACED_count"]    += int(f.get("verdict") == "TRACED")
        agg["flag_SYN_count"]          += int(flags.get("SYN", False))
        agg["flag_ACK_count"]          += int(flags.get("ACK", False))
        agg["flag_FIN_count"]          += int(flags.get("FIN", False))
        agg["flag_RST_count"]          += int(flags.get("RST", False))
        agg["flag_PSH_count"]          += int(flags.get("PSH", False))
        agg["is_well_known_port_count"]+= int(0 < dst < 1024)
        agg["is_high_port_count"]      += int(dst > 49152)
        agg["is_dns_port_count"]       += int(dst == 53)
        agg["is_http_port_count"]      += int(dst in HTTP_PORTS)
        agg["is_db_port_count"]        += int(dst in DB_PORTS)
        agg["is_mining_port_count"]    += int(dst in MINING_PORTS)

    agg["unique_src_ports"] = len(src_ports)
    agg["unique_dst_ports"] = len(dst_ports)

    return pd.DataFrame([agg]).reindex(columns=feature_names, fill_value=0).values


class HubbleSource(ModelBackedSource):
    """Flows answer where a pod went."""

    name = "network"
    count_field = "flow_count"

    def __init__(self, bundle, min_records: int = MIN_FLOW_THRESHOLD):
        super().__init__(bundle, min_records)

    def group(self, entries):
        by_pod = defaultdict(PodTelemetry)
        for entry in entries:
            flow = entry.get("flow", {})
            if not flow:
                continue
            src = flow.get("source", {})
            pod_name = src.get("pod_name", "")
            if not pod_name:
                continue
            tele = by_pod[pod_name]
            tele.records.append(flow)
            tele.namespace = src.get("namespace", "")
            tele.node = entry.get("node_name", "")
        return by_pod

    def infer(self, records):
        names = self.bundle.features
        votes = []
        for i in range(0, len(records), NETWORK_WINDOW_SIZE):
            X = extract_features(records[i:i + NETWORK_WINDOW_SIZE], names)
            if X is None:
                continue
            votes.append(self.scenario_of(pd.DataFrame(X, columns=names)))
        if not votes:
            return None
        scenario = Counter(votes).most_common(1)[0][0]
        return Verdict(self.binary_of(scenario), scenario)


if __name__ == "__main__":
    from core.modelstore import ModelBundle

    names = ["proto_TCP_count", "unique_dst_ports"]

    class _Tally:
        """Stands in for the tree and counts how many windows infer() asked about."""

        def __init__(self):
            self.windows = 0

        def predict(self, X):
            self.windows += 1
            return [6]  # Database, a benign label

    tally = _Tally()
    source = HubbleSource(ModelBundle(scenario=tally, binary=None, features=names))
    flows = [{"l4": {"TCP": {"destination_port": 80, "source_port": 1234}}}] * 250

    assert source.infer(flows) == Verdict(binary=0, scenario=6)
    assert tally.windows == 3, f"250 flows are 3 windows of <={NETWORK_WINDOW_SIZE}, got {tally.windows}"
    assert source.infer([]) is None, "no flows must abstain"

    grouped = source.group([
        {"flow": {"source": {"pod_name": "p", "namespace": "ns"}}, "node_name": "n1"},
    ])
    assert len(grouped["p"].records) == 1, "grouping must keep the flow"
    assert grouped["p"].namespace == "ns" and grouped["p"].node == "n1", "pod metadata lost"

    print(f"ok: flows are windowed at {NETWORK_WINDOW_SIZE}, matching training")
