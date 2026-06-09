#!/usr/bin/env python3
"""K-Watch runtime ML inference pipeline for Kubernetes intrusion detection."""

import json
import os
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import islice
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from loguru import logger
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.panel import Panel
from rich.table import Table
from rich import print as rprint

load_dotenv()

console = Console()

logger.remove()
logger.add(
    RichHandler(console=console, markup=True, rich_tracebacks=True, show_path=False),
    format="{message}",
    level="DEBUG",
)

TETRAGON_LOG  = Path(os.getenv("TETRAGON_LOG",  "/var/run/tetragon/tetragon.log"))
HUBBLE_LOG    = Path(os.getenv("HUBBLE_LOG",    "/var/run/cilium/hubble/kwatch-workloads.log"))
MODEL_DIR     = Path(os.getenv("MODEL_DIR",     "/models"))
ALERT_LOG     = Path(os.getenv("ALERT_LOG",     "/var/log/k-ids/alerts.json"))
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL",  "60"))
NGRAM_SIZE    = int(os.getenv("NGRAM_SIZE",      "5"))
BENIGN_LABELS = set(map(int, os.getenv("BENIGN_LABELS", "6,7,8,9").split(",")))

SYSCALL_MAP = {
    "__x64_sys_read": 0, "__x64_sys_write": 1, "__x64_sys_openat": 2,
    "__x64_sys_close": 3, "__x64_sys_newfstatat": 4, "__x64_sys_mmap": 9,
    "__x64_sys_mprotect": 10, "__x64_sys_brk": 12, "__x64_sys_socket": 41,
    "__x64_sys_connect": 42, "__x64_sys_accept": 43, "__x64_sys_sendto": 44,
    "__x64_sys_recvfrom": 45, "__x64_sys_clone": 56, "__x64_sys_execve": 59,
    "__x64_sys_exit_group": 231, "__x64_sys_kill": 62, "__x64_sys_nanosleep": 35,
    "__x64_sys_ioctl": 16, "__x64_sys_epoll_pwait": 281,
}

MINING_PORTS = {3333, 4444, 5555, 7777, 8888, 9999, 14444, 45700}
DB_PORTS     = {3306, 5432, 6379, 11211}
HTTP_PORTS   = {80, 443, 8080, 8443}

MODEL_FILES = {
    "syscall_scenario": "dt_syscall_scenario_model.pkl",
    "network_scenario": "dt_network_scenario_model.pkl",
    "syscall_binary":   "dt_syscall_binary_model.pkl",
    "network_binary":   "dt_network_binary_model.pkl",
    "feature_syscall":  "feature_names_syscall.pkl",
    "feature_network":  "feature_names_network.pkl",
    "scaler_syscall":   "scaler_syscall.pkl",
    "scaler_network":   "scaler_network.pkl",
    "scenario_names":   "scenario_class_names.pkl",
}


def load_models():
    models = {}
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(),
        TextColumn("[green]{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Loading models...", total=len(MODEL_FILES))
        for key, filename in MODEL_FILES.items():
            progress.update(task, description=f"Loading [cyan]{filename}[/cyan]")
            models[key] = joblib.load(MODEL_DIR / filename)
            progress.advance(task)
    return models


def ngrams(seq, n):
    it = iter(seq)
    window = list(islice(it, n))
    if len(window) == n:
        yield tuple(window)
    for item in it:
        window = window[1:] + [item]
        yield tuple(window)


def extract_syscall_features(events, feature_names):
    syscall_nums = [SYSCALL_MAP[e] for e in events if e in SYSCALL_MAP]
    if len(syscall_nums) < NGRAM_SIZE:
        return None
    gram_counts = Counter(ngrams(syscall_nums, NGRAM_SIZE))
    row = {str(k): v for k, v in gram_counts.items()}
    return pd.DataFrame([row]).reindex(columns=feature_names, fill_value=0).values


def extract_network_features(flows, feature_names):
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


class LogTailer:
    def __init__(self, path: Path):
        self.path = path
        self.offset = path.stat().st_size if path.exists() else 0

    def read_new(self):
        if not self.path.exists():
            return []
        records = []
        with open(self.path) as f:
            f.seek(self.offset)
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            self.offset = f.tell()
        return records


def write_alert(alert: dict):
    ALERT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(ALERT_LOG, "a") as f:
        f.write(json.dumps(alert) + "\n")

    severity = alert["severity"]
    color    = {"critical": "bold red", "high": "red", "info": "green"}.get(severity, "yellow")
    logger.warning(
        f"[{color}]▶ ALERT[/{color}] "
        f"pod=[bold]{alert['pod_name']}[/bold] "
        f"scenario=[cyan]{alert['scenario_result']}[/cyan] "
        f"severity=[{color}]{severity.upper()}[/{color}]"
    )


def group_tetragon_events(events):
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


def group_hubble_flows(flows):
    by_pod = defaultdict(lambda: {"flows": [], "namespace": "", "node": ""})
    for entry in flows:
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


def infer_syscall(models, syscalls):
    X = extract_syscall_features(syscalls, models["feature_syscall"])
    if X is None:
        return None, None
    X_scaled = models["scaler_syscall"].transform(X)
    return (
        int(models["syscall_binary"].predict(X_scaled).mean().round()),
        int(models["syscall_scenario"].predict(X_scaled)[0]),
    )


def infer_network(models, flows):
    X = extract_network_features(flows, models["feature_network"])
    if X is None:
        return None, None
    X_scaled = models["scaler_network"].transform(X)
    return (
        int(models["network_binary"].predict(X_scaled)[0]),
        int(models["network_scenario"].predict(X_scaled)[0]),
    )


def resolve_binary(sys_bin, net_bin):
    if sys_bin is not None and net_bin is not None:
        return int(sys_bin == 1 or net_bin == 1)
    return sys_bin if sys_bin is not None else net_bin


def resolve_severity(binary_pred, sys_bin, net_bin):
    if binary_pred == 0:
        return "info"
    if sys_bin == 1 and net_bin == 1:
        return "critical"
    return "high"


def detect(models, tetragon_events, hubble_flows):
    syscall_by_pod = group_tetragon_events(tetragon_events)
    flow_by_pod    = group_hubble_flows(hubble_flows)
    all_pods       = set(syscall_by_pod) | set(flow_by_pod)
    ts             = datetime.now(timezone.utc).isoformat()
    scenario_names = models["scenario_names"]
    alerts         = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Analyzing pods...", total=len(all_pods))

        for pod_name in all_pods:
            progress.update(task, description=f"Analyzing [bold]{pod_name}[/bold]")
            pod_sys  = syscall_by_pod.get(pod_name, {})
            pod_flow = flow_by_pod.get(pod_name, {})

            sys_bin, sys_scenario = infer_syscall(models, pod_sys.get("syscalls", []))
            net_bin, net_scenario = infer_network(models, pod_flow.get("flows", []))

            binary_pred = resolve_binary(sys_bin, net_bin)
            progress.advance(task)

            if binary_pred is None:
                continue

            scenario_pred = sys_scenario if sys_scenario is not None else net_scenario
            scenario_name = scenario_names[scenario_pred] if scenario_pred is not None and scenario_pred < len(scenario_names) else "unknown"
            namespace     = pod_sys.get("namespace") or pod_flow.get("namespace", "")
            node          = pod_sys.get("node")      or pod_flow.get("node", "")

            alert = {
                "timestamp":           ts,
                "source":              "k-watch",
                "node":                node,
                "namespace":           namespace,
                "pod_name":            pod_name,
                "binary_label":        binary_pred,
                "binary_result":       "malicious" if binary_pred == 1 else "benign",
                "scenario_label":      scenario_pred,
                "scenario_result":     scenario_name,
                "syscall_binary_pred": sys_bin,
                "network_binary_pred": net_bin,
                "syscall_count":       len(pod_sys.get("syscalls", [])),
                "flow_count":          len(pod_flow.get("flows", [])),
                "severity":            resolve_severity(binary_pred, sys_bin, net_bin),
            }

            if binary_pred == 1:
                write_alert(alert)
                alerts.append(alert)

    return alerts


def print_cycle_summary(alerts, syscall_count, flow_count):
    table = Table(title="Cycle Summary", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("Syscall events", str(syscall_count))
    table.add_row("Flow events",    str(flow_count))
    table.add_row("Alerts",         f"[bold red]{len(alerts)}[/bold red]" if alerts else "[green]0[/green]")
    if alerts:
        for a in alerts:
            color = "bold red" if a["severity"] == "critical" else "red"
            table.add_row(
                f"  [{color}]{a['pod_name']}[/{color}]",
                f"[cyan]{a['scenario_result']}[/cyan] [{color}]{a['severity'].upper()}[/{color}]",
            )
    console.print(table)


def main():
    console.print(Panel.fit(
        "[bold cyan]K-Watch[/bold cyan] — Kubernetes Intrusion Detection System",
        border_style="cyan",
    ))

    logger.info(f"Tetragon : [dim]{TETRAGON_LOG}[/dim]")
    logger.info(f"Hubble   : [dim]{HUBBLE_LOG}[/dim]")
    logger.info(f"Models   : [dim]{MODEL_DIR}[/dim]")
    logger.info(f"Alerts   : [dim]{ALERT_LOG}[/dim]")
    logger.info(f"Interval : [bold]{POLL_INTERVAL}s[/bold]")

    models = load_models()
    logger.success("All models loaded successfully")

    tetragon_tailer = LogTailer(TETRAGON_LOG)
    hubble_tailer   = LogTailer(HUBBLE_LOG)

    logger.info("[bold green]Watching for new events...[/bold green]")

    while True:
        time.sleep(POLL_INTERVAL)
        tetragon_events = tetragon_tailer.read_new()
        hubble_flows    = hubble_tailer.read_new()

        if not tetragon_events and not hubble_flows:
            logger.debug("No new events in this cycle")
            continue

        logger.info(
            f"Processing [bold]{len(tetragon_events)}[/bold] syscall events, "
            f"[bold]{len(hubble_flows)}[/bold] flows"
        )
        alerts = detect(models, tetragon_events, hubble_flows)
        print_cycle_summary(alerts, len(tetragon_events), len(hubble_flows))


if __name__ == "__main__":
    main()
