"""The contract every telemetry source implements, and the wiring they share."""

from dataclasses import dataclass, field
from typing import Protocol

from core.config import BENIGN_LABELS


@dataclass(frozen=True)
class Verdict:
    """What one source concluded about one pod in one cycle."""

    binary: int    # 1 malicious, 0 benign
    scenario: int


@dataclass
class PodTelemetry:
    """One pod's records from one source, plus where that pod ran."""

    records: list = field(default_factory=list)
    namespace: str = ""
    node: str = ""


class TelemetrySource(Protocol):
    """A source groups raw entries per pod, then judges one pod's records."""

    name: str          # feeds the "<name>_binary_pred" alert field
    count_field: str   # alert field holding len(records); the schema is irregular by history
    min_records: int   # below this the source stays silent

    def group(self, entries) -> dict[str, PodTelemetry]: ...

    def infer(self, records) -> Verdict | None: ...


class ModelBackedSource:
    """Base for sources that ask a decision tree. Holds the one benign-label rule."""

    def __init__(self, bundle, min_records: int):
        self.bundle = bundle
        self.min_records = min_records

    def scenario_of(self, X) -> int:
        return int(self.bundle.scenario.predict(X)[0])

    def binary_of(self, scenario: int, X=None) -> int:
        """A dedicated binary model wins; otherwise the label decides."""
        if self.bundle.binary is not None and X is not None:
            return int(self.bundle.binary.predict(X)[0])
        return 0 if scenario in BENIGN_LABELS else 1
