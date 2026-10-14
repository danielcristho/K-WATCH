"""Show alerts to whoever is watching the pod logs."""

from rich.table import Table

from core.log import console, logger

STYLES = {"critical": "bold red", "high": "red", "info": "green"}


class ConsoleSink:
    def emit(self, alert: dict) -> None:
        severity = alert["severity"]
        color = STYLES.get(severity, "yellow")
        logger.warning(
            f"[{color}]▶ ALERT[/{color}] "
            f"pod=[bold]{alert['pod_name']}[/bold] "
            f"scenario=[cyan]{alert['scenario_result']}[/cyan] "
            f"severity=[{color}]{severity.upper()}[/{color}]"
        )


def print_cycle_summary(alerts, counts: dict) -> None:
    table = Table(title="Cycle Summary", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")
    for label, value in counts.items():
        table.add_row(label, str(value))
    table.add_row("Alerts", f"[bold red]{len(alerts)}[/bold red]" if alerts else "[green]0[/green]")
    for alert in alerts:
        color = STYLES.get(alert["severity"], "red")
        table.add_row(
            f"  [{color}]{alert['pod_name']}[/{color}]",
            f"[cyan]{alert['scenario_result']}[/cyan] [{color}]{alert['severity'].upper()}[/{color}]",
        )
    console.print(table)
