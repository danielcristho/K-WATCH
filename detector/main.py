"""K-Watch runtime detector: wire the sources, the pipeline and the sinks together."""

import time

from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

import alerting
from alerting.console import ConsoleSink, print_cycle_summary
from alerting.discord import DiscordSink
from alerting.file import FileSink
from core import config
from core.log import console, logger
from core.modelstore import load_models, total_files
from core.pipeline import Detector
from sources.hubble import HubbleSource
from sources.tailer import LogTailer
from sources.tetragon import TetragonSource


def load_with_progress():
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(),
        TextColumn("[green]{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Loading models...", total=total_files())

        def report(filename):
            progress.update(task, description=f"Loading [cyan]{filename}[/cyan]")
            progress.advance(task)

        return load_models(on_file=report)


def build():
    """Everything that knows a concrete class lives here, and nowhere else."""
    bundles, scenario_names = load_with_progress()
    sources = [
        TetragonSource(bundles["syscall"]),
        HubbleSource(bundles["network"]),
    ]
    tailers = {
        "syscall": LogTailer(config.TETRAGON_LOG),
        "network": LogTailer(config.HUBBLE_LOG),
    }
    sinks = [
        FileSink(config.ALERT_LOG),
        DiscordSink(config.DISCORD_WEBHOOK),
        ConsoleSink(),
    ]
    return Detector(sources, scenario_names), tailers, sinks


def main():
    console.print(Panel.fit("[bold cyan]K-Watch[/bold cyan] — Detector Pipeline", border_style="cyan"))
    logger.info(f"Tetragon : [orange3]{config.TETRAGON_LOG}[/orange3]")
    logger.info(f"Hubble   : [orange3]{config.HUBBLE_LOG}[/orange3]")
    logger.info(f"Models   : [orange3]{config.MODEL_DIR}[/orange3]")
    logger.info(f"Alerts   : [orange3]{config.ALERT_LOG}[/orange3]")
    logger.info(f"Interval : [bold]{config.POLL_INTERVAL}s[/bold]")

    detector, tailers, sinks = build()
    logger.success("All models loaded successfully")
    logger.info("[bold green]Watching for new events...[/bold green]")

    while True:
        time.sleep(config.POLL_INTERVAL)
        batches = {name: tailer.read_new() for name, tailer in tailers.items()}
        if not any(batches.values()):
            logger.info("No new events in this cycle")
            continue

        logger.info(
            f"Processing [bold]{len(batches['syscall'])}[/bold] syscall events, "
            f"[bold]{len(batches['network'])}[/bold] flows"
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Analyzing pods...", total=None)
            alerts = detector.run(
                batches,
                on_pod=lambda pod: progress.update(task, description=f"Analyzing [bold]{pod}[/bold]"),
            )

        for alert in alerts:
            alerting.dispatch(alert, sinks)
        print_cycle_summary(alerts, {
            "Syscall events": len(batches["syscall"]),
            "Flow events":    len(batches["network"]),
        })


if __name__ == "__main__":
    main()
