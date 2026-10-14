"""Alert sinks. Adding a destination means adding a file here, not editing the pipeline."""

from typing import Protocol

from core.log import logger


class AlertSink(Protocol):
    def emit(self, alert: dict) -> None: ...


def dispatch(alert: dict, sinks) -> None:
    """One failing sink must not silence the others, nor stop the detection loop."""
    for sink in sinks:
        try:
            sink.emit(alert)
        except Exception as exc:
            logger.error(f"{type(sink).__name__} failed: {exc}")
