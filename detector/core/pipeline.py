"""Turn one cycle of raw telemetry into alerts. No files, no console, no network."""

from datetime import datetime, timezone

from core import config


class Detector:
    """Runs every source over every pod and merges their verdicts into alerts.

    Source order is precedence order: the first source that calls a pod malicious
    names the scenario.
    """

    def __init__(self, sources, scenario_names, node_name=None,
                 monitored=None, excluded=None):
        self.sources        = list(sources)
        self.scenario_names = scenario_names
        self.node_name      = config.NODE_NAME if node_name is None else node_name
        self.monitored      = config.MONITORED_NAMESPACES if monitored is None else monitored
        self.excluded       = config.EXCLUDED_NAMESPACES if excluded is None else excluded

    def run(self, batches, on_pod=None):
        """batches maps a source name to its raw entries for this cycle."""
        grouped = {s.name: s.group(batches.get(s.name, [])) for s in self.sources}
        pods    = sorted({pod for g in grouped.values() for pod in g})
        now     = datetime.now(timezone.utc).isoformat()

        alerts = []
        for pod in pods:
            if on_pod:
                on_pod(pod)
            alert = self._assess(pod, grouped, now)
            # Benign verdicts are computed but not emitted, which is why Wazuh rule
            # 100101 can never fire. Behaviour kept as-is on purpose.
            if alert and alert["binary_label"] == 1:
                alerts.append(alert)
        return alerts

    def _assess(self, pod, grouped, now):
        telemetry = {s.name: grouped[s.name].get(s.name and pod) for s in self.sources}
        verdicts  = self._collect_verdicts(telemetry)
        if not verdicts:
            return None

        namespace = self._first(telemetry, "namespace")
        if not namespace or namespace in self.excluded:
            return None
        if self.monitored and namespace not in self.monitored:
            return None

        binary  = int(any(v.binary == 1 for v in verdicts.values()))
        chosen  = self._choose(verdicts)
        counts  = {s.count_field: self._count(telemetry[s.name]) for s in self.sources}
        preds   = {f"{s.name}_binary_pred": self._binary(verdicts.get(s.name))
                   for s in self.sources}

        return {
            "timestamp":       now,
            "source":          "k-watch",
            "node":            self._first(telemetry, "node") or self.node_name,
            "namespace":       namespace,
            "pod_name":        pod,
            "binary_label":    binary,
            "binary_result":   "malicious" if binary == 1 else "benign",
            "scenario_label":  chosen.scenario,
            "scenario_result": self._scenario_name(chosen.scenario),
            **preds,
            **counts,
            "severity":        self._severity(binary, verdicts),
        }

    def _collect_verdicts(self, telemetry):
        verdicts = {}
        for source in self.sources:
            tele = telemetry[source.name]
            if tele is None or len(tele.records) < source.min_records:
                continue
            verdict = source.infer(tele.records)
            if verdict is not None:
                verdicts[source.name] = verdict
        return verdicts

    def _choose(self, verdicts):
        """The first source that cried malicious wins; otherwise the first that spoke."""
        for source in self.sources:
            verdict = verdicts.get(source.name)
            if verdict is not None and verdict.binary == 1:
                return verdict
        for source in self.sources:
            if source.name in verdicts:
                return verdicts[source.name]
        return None

    def _first(self, telemetry, attr):
        for source in self.sources:
            tele = telemetry[source.name]
            if tele is not None and getattr(tele, attr):
                return getattr(tele, attr)
        return ""

    def _scenario_name(self, label):
        if label is None or label >= len(self.scenario_names):
            return "unknown"
        return self.scenario_names[label]

    @staticmethod
    def _severity(binary, verdicts):
        if binary == 0:
            return "info"
        # Two independent sources agreeing is the strongest signal the system has
        return "critical" if sum(v.binary == 1 for v in verdicts.values()) >= 2 else "high"

    @staticmethod
    def _count(tele):
        return len(tele.records) if tele is not None else 0

    @staticmethod
    def _binary(verdict):
        return verdict.binary if verdict is not None else None


if __name__ == "__main__":
    from core.contracts import PodTelemetry, Verdict

    class _Source:
        def __init__(self, name, count_field, verdict, namespace="malicious", records=50):
            self.name, self.count_field = name, count_field
            self.min_records, self._verdict = 5, verdict
            self._ns, self._n = namespace, records

        def group(self, entries):
            return {"pod-a": PodTelemetry(records=[0] * self._n, namespace=self._ns, node="n1")}

        def infer(self, records):
            return self._verdict

    names = ["Botnet", "Cryptominer", "Trojan-Agent", "Cloud Attack", "Brute-Force",
             "Data-Caching", "Database", "Redis", "Web-Serving"]

    def detect(*sources):
        d = Detector(sources, names, node_name="fallback",
                     monitored={"malicious"}, excluded={"kube-system"})
        return d.run({s.name: [] for s in sources})

    both = detect(_Source("syscall", "syscall_count", Verdict(1, 0)),
                  _Source("network", "flow_count", Verdict(1, 1)))
    assert len(both) == 1
    assert both[0]["severity"] == "critical", "two malicious sources must escalate"
    assert both[0]["scenario_result"] == "Botnet", "the first malicious source names it"
    assert both[0]["syscall_count"] == 50 and both[0]["flow_count"] == 50

    one = detect(_Source("syscall", "syscall_count", Verdict(1, 0)),
                 _Source("network", "flow_count", None))
    assert one[0]["severity"] == "high", "a lone source is not critical"
    assert one[0]["network_binary_pred"] is None, "an abstaining source reports None"

    assert detect(_Source("syscall", "syscall_count", Verdict(0, 8))) == [], \
        "benign verdicts must not be emitted as alerts"

    quiet = detect(_Source("syscall", "syscall_count", Verdict(1, 0), records=2))
    assert quiet == [], "below min_records the source must stay silent"

    skipped = detect(_Source("syscall", "syscall_count", Verdict(1, 0), namespace="kube-system"))
    assert skipped == [], "excluded namespaces produce no alert"

    unmonitored = detect(_Source("syscall", "syscall_count", Verdict(1, 0), namespace="other"))
    assert unmonitored == [], "namespaces outside the monitored set produce no alert"

    print("ok: verdicts merge, severity escalates only on agreement, filters hold")
