"""K-Watch runtime detector: wire the sources, the pipeline and the sinks together."""

import time

from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

import alerting
from alerting.console import INTERACTIVE, print_alert_cycle, print_banner, print_quiet_cycle
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
        disable=not INTERACTIVE,
    ) as progress:
        task = progress.add_task("Loading models...", total=total_files())

        def report(filename):
            progress.update(task, description=f"Loading [cyan]{filename}[/cyan]")
            progress.advance(task)

        return load_models(on_file=report)


def build():
    """Everything that names a concrete class lives here, and nowhere else."""
    bundles, scenario_names = load_with_progress()
    sources = [TetragonSource(bundles["syscall"]), HubbleSource(bundles["network"])]
    tailers = {
        "syscall": LogTailer(config.TETRAGON_LOG),
        "network": LogTailer(config.HUBBLE_LOG),
    }
    # The cycle panel is the console output; a per-alert line would only repeat it
    sinks = [FileSink(config.ALERT_LOG), DiscordSink(config.DISCORD_WEBHOOK)]
    return Detector(sources, scenario_names), tailers, sinks


def analyse(detector, batches):
    """Run one cycle, showing a spinner only where a spinner can be redrawn."""
    if not INTERACTIVE:
        return detector.run(batches)
    with Progress(SpinnerColumn(), TextColumn("[bold blue]{task.description}"),
                  console=console, transient=True) as progress:
        task = progress.add_task("Analyzing pods...", total=None)
        return detector.run(
            batches,
            on_pod=lambda pod: progress.update(task, description=f"Analyzing [bold]{pod}[/bold]"),
        )


def main():
    print_banner({
        "Tetragon": config.TETRAGON_LOG,
        "Hubble":   config.HUBBLE_LOG,
        "Models":   config.MODEL_DIR,
        "Alerts":   config.ALERT_LOG,
        "Interval": f"{config.POLL_INTERVAL}s",
    })

    detector, tailers, sinks = build()
    logger.info("[bold green]Watching for new events[/bold green]")

    cycle = 0
    while True:
        time.sleep(config.POLL_INTERVAL)
        cycle += 1
        batches = {name: tailer.read_new() for name, tailer in tailers.items()}
        counts = {"syscalls": len(batches["syscall"]), "flows": len(batches["network"])}

        if not any(batches.values()):
            print_quiet_cycle(cycle, counts)
            continue

        alerts = analyse(detector, batches)
        for alert in alerts:
            alerting.dispatch(alert, sinks)

        if alerts:
            print_alert_cycle(cycle, counts, alerts)
        else:
            print_quiet_cycle(cycle, counts)


if __name__ == "__main__":
    main()
