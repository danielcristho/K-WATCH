"""K-Watch — Kubernetes Intrusion Detection System runtime detector."""

import time
from datetime import datetime, timezone

from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

import config
from logging import console, logger
from models import load_models
from tailer import LogTailer, HubbleTailer
from alerting import write_alert, resolve_severity, print_cycle_summary
import tetragon
import hubble


def resolve_binary(sys_bin, net_bin):
    if sys_bin is not None and net_bin is not None:
        return int(sys_bin == 1 or net_bin == 1)
    return sys_bin if sys_bin is not None else net_bin


def detect(models, tetragon_events, hubble_flows):
    syscall_by_pod = tetragon.group_events(tetragon_events)
    flow_by_pod    = hubble.group_flows(hubble_flows)
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

            sys_bin, sys_scenario = tetragon.infer(models, pod_sys.get("syscalls", []))
            net_bin, net_scenario = hubble.infer(models, pod_flow.get("flows", []))

            binary_pred = resolve_binary(sys_bin, net_bin)
            progress.advance(task)

            if binary_pred is None:
                continue

            namespace = pod_sys.get("namespace") or pod_flow.get("namespace", "")
            if namespace and namespace not in config.MONITORED_NAMESPACES:
                continue

            scenario_pred = sys_scenario if sys_scenario is not None else net_scenario
            scenario_name = scenario_names[scenario_pred] if scenario_pred is not None and scenario_pred < len(scenario_names) else "unknown"
            node = pod_sys.get("node") or pod_flow.get("node", "")

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


def main():
    console.print(Panel.fit(
        "[bold cyan]K-Watch[/bold cyan] — Detector Pipeline",
        border_style="cyan",
    ))

    logger.info(f"Tetragon : [orange3]{config.TETRAGON_LOG}[/orange3]")
    logger.info(f"Hubble   : [orange3]{config.HUBBLE_LOG}[/orange3]")
    logger.info(f"Models   : [orange3]{config.MODEL_DIR}[/orange3]")
    logger.info(f"Alerts   : [orange3]{config.ALERT_LOG}[/orange3]")
    logger.info(f"Interval : [bold]{config.POLL_INTERVAL}s[/bold]")

    models = load_models()
    logger.success("All models loaded successfully")

    tetragon_tailer = LogTailer(config.TETRAGON_LOG)
    hubble_tailer   = HubbleTailer(config.HUBBLE_LOG.parent, prefix="kwatch-workloads")

    logger.info("[bold green]Watching for new events...[/bold green]")

    while True:
        time.sleep(config.POLL_INTERVAL)
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
