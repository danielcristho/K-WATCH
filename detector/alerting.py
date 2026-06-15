import json
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen

from rich.table import Table

from config import ALERT_LOG, DISCORD_WEBHOOK
from log import console, logger

_discord_pool = ThreadPoolExecutor(max_workers=2)


def resolve_severity(binary_pred, sys_bin, net_bin):
    if binary_pred == 0:
        return "info"
    if sys_bin == 1 and net_bin == 1:
        return "critical"
    return "high"


def _send_discord_sync(alert: dict):
    severity = alert["severity"]
    color = {"critical": 0xFF0000, "high": 0xFF6600, "info": 0x00FF00}.get(severity, 0xFFFF00)
    embed = {
        "embeds": [{
            "title": f"\ud83d\udea8 K-Watch Alert \u2014 {severity.upper()}",
            "color": color,
            "fields": [
                {"name": "Pod",       "value": f"`{alert['pod_name']}`",       "inline": True},
                {"name": "Namespace", "value": f"`{alert['namespace']}`",      "inline": True},
                {"name": "Node",      "value": f"`{alert['node']}`",           "inline": True},
                {"name": "Scenario",  "value": alert["scenario_result"],        "inline": True},
                {"name": "Binary",    "value": alert["binary_result"].upper(),  "inline": True},
                {"name": "Severity",  "value": severity.upper(),               "inline": True},
                {"name": "Syscalls",  "value": str(alert["syscall_count"]),     "inline": True},
                {"name": "Flows",     "value": str(alert["flow_count"]),        "inline": True},
            ],
            "timestamp": alert["timestamp"],
        }]
    }
    try:
        req = Request(DISCORD_WEBHOOK, data=json.dumps(embed).encode(), headers={"Content-Type": "application/json", "User-Agent": "K-Watch/1.0"})
        urlopen(req, timeout=5)
    except Exception as e:
        logger.debug(f"Discord webhook failed: {e}")


def send_discord(alert: dict):
    if not DISCORD_WEBHOOK:
        return
    _discord_pool.submit(_send_discord_sync, alert)


def write_alert(alert: dict):
    ALERT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(ALERT_LOG, "a") as f:
        f.write(json.dumps(alert) + "\n")

    send_discord(alert)

    severity = alert["severity"]
    color = {"critical": "bold red", "high": "red", "info": "green"}.get(severity, "yellow")
    logger.warning(
        f"[{color}]\u25b6 ALERT[/{color}] "
        f"pod=[bold]{alert['pod_name']}[/bold] "
        f"scenario=[cyan]{alert['scenario_result']}[/cyan] "
        f"severity=[{color}]{severity.upper()}[/{color}]"
    )


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
