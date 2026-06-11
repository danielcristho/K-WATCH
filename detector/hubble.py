import json
from collections import defaultdict
from pathlib import Path

import pandas as pd

from config import BENIGN_LABELS

with open(Path(__file__).parent / "data" / "ports.json") as _f:
    _ports = json.load(_f)

MINING_PORTS = set(_ports["mining"])
DB_PORTS     = set(_ports["database"])
HTTP_PORTS   = set(_ports["http"])


def group_flows(entries):
    by_pod = defaultdict(lambda: {"flows": [], "namespace": "", "node": ""})
    for entry in entries:
        flow = entry.get("flow", {})
        if not flow:
            continue
        src = flow.get("source", {})
        pod_name = src.get("pod_name", "")
        if not pod_name:
            continue
        by_pod[pod_name]["flows"].append(flow)
        by_pod[pod_name]["namespace"] = src.get("namespace", "")
        by_pod[pod_name]["node"] = entry.get("node_name", "")
    return by_pod


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


def infer(models, flows):
    X = extract_features(flows, models["feature_network"])
    if X is None:
        return None, None
    X_df = pd.DataFrame(X, columns=models["feature_network"])
    scenario = int(models["network_scenario"].predict(X_df)[0])
    binary   = 0 if scenario in BENIGN_LABELS else 1
    return binary, scenario
