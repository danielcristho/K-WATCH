"""The alert JSON is a contract with Wazuh, so its field names are pinned here.

Wazuh matches on <field name="..."> and interpolates $(...) from the same JSON, so
renaming a key in the pipeline silently stops rules 100100-100114 from firing.
"""

import re
from pathlib import Path

from core.contracts import PodTelemetry, Verdict
from core.pipeline import Detector
from sources.hubble import HubbleSource
from sources.tetragon import TetragonSource

DETECTOR = Path(__file__).resolve().parent.parent
RULES = DETECTOR.parent / "wazuh" / "rules" / "kwatch_rules.xml"

EXPECTED_FIELDS = {
    "timestamp", "source", "node", "namespace", "pod_name",
    "binary_label", "binary_result", "scenario_label", "scenario_result",
    "syscall_binary_pred", "network_binary_pred",
    "syscall_count", "flow_count", "severity",
}

SCENARIOS = ["Botnet", "Cryptominer", "Trojan-Agent", "Cloud Attack", "Brute-Force",
             "Data-Caching", "Database", "Redis", "Web-Serving"]


class _Fake:
    """Mimics a real source closely enough to produce one alert."""

    def __init__(self, name, count_field, verdict):
        self.name, self.count_field, self._verdict = name, count_field, verdict
        self.min_records = 1

    def group(self, entries):
        return {"pod-a": PodTelemetry(records=[0] * 9, namespace="malicious", node="worker-1")}

    def infer(self, records):
        return self._verdict


def one_alert():
    detector = Detector(
        [_Fake("syscall", "syscall_count", Verdict(1, 0)),
         _Fake("network", "flow_count", Verdict(1, 1))],
        SCENARIOS, node_name="worker-1", monitored={"malicious"}, excluded=set(),
    )
    alerts = detector.run({"syscall": [], "network": []})
    assert len(alerts) == 1, f"expected one alert, got {len(alerts)}"
    return alerts[0]


def test_alert_has_exactly_the_agreed_fields():
    assert set(one_alert()) == EXPECTED_FIELDS


def test_source_names_drive_the_prediction_fields():
    # TetragonSource.name == "syscall" is what produces "syscall_binary_pred"
    for source, pred, count in ((TetragonSource, "syscall_binary_pred", "syscall_count"),
                                (HubbleSource, "network_binary_pred", "flow_count")):
        assert f"{source.name}_binary_pred" == pred, f"{source.__name__}.name drifted"
        assert source.count_field == count, f"{source.__name__}.count_field drifted"


def test_every_field_wazuh_reads_is_emitted():
    text = RULES.read_text()
    used = set(re.findall(r'field name="(\w+)"', text)) | set(re.findall(r"\$\((\w+)\)", text))
    missing = used - EXPECTED_FIELDS
    assert not missing, f"Wazuh rules read fields the detector never emits: {sorted(missing)}"


def test_no_rule_interpolates_a_namespaced_field():
    # $(json.pod_name) parses but resolves to nothing, so the description renders empty
    dotted = re.findall(r"\$\([\w]+\.[\w.]+\)", RULES.read_text())
    assert not dotted, f"these resolve to an empty string at runtime: {sorted(set(dotted))}"


if __name__ == "__main__":
    test_alert_has_exactly_the_agreed_fields()
    test_source_names_drive_the_prediction_fields()
    test_every_field_wazuh_reads_is_emitted()
    test_no_rule_interpolates_a_namespaced_field()
    print(f"ok: {len(EXPECTED_FIELDS)} alert fields pinned, Wazuh rules all satisfied")
