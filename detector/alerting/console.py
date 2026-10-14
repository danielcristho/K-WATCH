"""Show alerts to whoever is watching, on a terminal or through kubectl logs.

Quiet cycles collapse to one dim line and alert cycles open a framed block, so a
viewer across a room sees the moment something fires without reading anything.
"""

import sys

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from core.log import console, logger

BANNER = r"""
 ██╗  ██╗      ██╗    ██╗ █████╗ ████████╗ ██████╗██╗  ██╗
 ██║ ██╔╝      ██║    ██║██╔══██╗╚══██╔══╝██╔════╝██║  ██║
 █████╔╝ █████╗██║ █╗ ██║███████║   ██║   ██║     ███████║
 ██╔═██╗ ╚════╝██║███╗██║██╔══██║   ██║   ██║     ██╔══██║
 ██║  ██╗      ╚███╔███╔╝██║  ██║   ██║   ╚██████╗██║  ██║
 ╚═╝  ╚═╝       ╚══╝╚══╝ ╚═╝  ╚═╝   ╚═╝    ╚═════╝╚═╝  ╚═╝
"""

STYLES = {"critical": "bold white on red", "high": "bold red", "info": "green"}
BORDERS = {"critical": "red", "high": "dark_orange", "info": "green"}

#: A spinner redrawn over itself is noise once it lands in a log file
INTERACTIVE = sys.stdout.isatty()


def print_banner(settings: dict) -> None:
    console.print(Text(BANNER.strip("\n"), style="bold cyan"))
    console.print(Text("  eBPF runtime intrusion detection for Kubernetes\n", style="dim"))
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="dim")
    grid.add_column(style="cyan")
    for key, value in settings.items():
        grid.add_row(key, str(value))
    console.print(grid)
    console.print()


def print_quiet_cycle(cycle: int, counts: dict) -> None:
    """One dim line, so the eye has nothing to catch until something fires."""
    seen = "  ".join(f"{label} {value}" for label, value in counts.items())
    console.print(f"[dim]{cycle:>4}  {seen}  quiet[/dim]")


def print_alert_cycle(cycle: int, counts: dict, alerts) -> None:
    worst = "critical" if any(a["severity"] == "critical" for a in alerts) else "high"

    rows = Table.grid(padding=(0, 2))
    rows.add_column(justify="right")
    rows.add_column()
    rows.add_column()
    rows.add_column()
    for alert in alerts:
        severity = alert["severity"]
        rows.add_row(
            Text(severity.upper(), style=STYLES.get(severity, "yellow")),
            Text(short_name(alert["pod_name"]), style="bold"),
            Text(alert["scenario_result"], style="cyan"),
            Text(sources(alert), style="dim"),
        )

    seen = "  ".join(f"{label} {value}" for label, value in counts.items())
    console.print(Panel(
        rows,
        title=f"[bold]{len(alerts)} ALERT{'S' if len(alerts) > 1 else ''}[/bold]",
        subtitle=f"[dim]{cycle}  {seen}[/dim]",
        border_style=BORDERS[worst],
        padding=(0, 1),
        expand=False,
    ))


def short_name(pod: str) -> str:
    """Drop the replicaset hash; it is noise on a projector and the JSON keeps it."""
    parts = pod.rsplit("-", 2)
    return parts[0] if len(parts) == 3 and len(parts[-1]) == 5 else pod


def sources(alert: dict) -> str:
    """Which eBPF sources agreed, the detail the whole talk is about."""
    agreed = [label for label, key in (("sys", "syscall_binary_pred"),
                                       ("net", "network_binary_pred"))
              if alert[key] == 1]
    return "+".join(agreed) if agreed else "none"


class ConsoleSink:
    """Per-alert line, for anyone grepping the stream rather than watching it."""

    def emit(self, alert: dict) -> None:
        severity = alert["severity"]
        logger.warning(
            f"[{BORDERS.get(severity, 'yellow')}]ALERT[/] "
            f"pod=[bold]{alert['pod_name']}[/bold] "
            f"scenario=[cyan]{alert['scenario_result']}[/cyan] "
            f"severity=[bold]{severity.upper()}[/bold]"
        )


if __name__ == "__main__":
    for line in BANNER.strip("\n").splitlines():
        assert len(line) == 58, f"banner is ragged at {len(line)}: {line!r}"

    assert short_name("malicious-agent-57d54dd5dc-gwhzh") == "malicious-agent"
    assert short_name("coredns") == "coredns", "a bare name must survive"
    assert sources({"syscall_binary_pred": 1, "network_binary_pred": 1}) == "sys+net"
    assert sources({"syscall_binary_pred": 1, "network_binary_pred": None}) == "sys"
    assert sources({"syscall_binary_pred": 0, "network_binary_pred": 0}) == "none"

    print_banner({"Tetragon": "/var/run/cilium/tetragon/tetragon.log", "Interval": "30s"})
    print_quiet_cycle(41, {"syscalls": 309, "flows": 314})
    print_alert_cycle(42, {"syscalls": 246, "flows": 312}, [
        {"severity": "critical", "pod_name": "malicious-agent-57d54dd5dc-gwhzh",
         "scenario_result": "Brute-Force", "syscall_binary_pred": 1, "network_binary_pred": 1},
        {"severity": "high", "pod_name": "trojan-agent-5b9c6969f7-8dz7c",
         "scenario_result": "Botnet", "syscall_binary_pred": 1, "network_binary_pred": None},
    ])
    print_quiet_cycle(43, {"syscalls": 288, "flows": 301})
    print("\nok: banner aligned, names shortened, quiet cycles stay out of the way")
