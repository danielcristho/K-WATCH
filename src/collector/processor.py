import pandas as pd
from collections import defaultdict
from typing import List, Dict, Any, Optional
from .models import TetragonEvent, CiliumFlowEvent, FalcoEvent

class HybridFeatureProcessor:
    def __init__(self, window_seconds: int = 10):
        self.window_seconds = window_seconds
        self.event_buckets = defaultdict(lambda: {"syscalls": [], "network": [], "falco": []})
        self.feature_columns = [
            "syscall_count", "execve_count", "open_count", 
            "socket_count", "connect_count", "unique_binaries_count",
            "flow_count", "unique_destinations_count", 
            "tcp_count", "udp_count", "total_bytes", "falco_alert_count"
        ]

    def process_tetragon_event(self, event: TetragonEvent):
        container_id = self._get_container_id(event)
        self.event_buckets[container_id]["syscalls"].append(event)

    def process_cilium_event(self, event: CiliumFlowEvent):
        # Hubble events typically identify pod by name/namespace
        # We need a cross-mapping if possible, or just use pod name.
        pod_name = event.source.get("pod_name", "unknown")
        namespace = event.source.get("namespace", "default")
        container_key = f"{namespace}/{pod_name}"

        self.event_buckets[container_key]["network"].append(event)

    def process_falco_event(self, event: FalcoEvent):
        pod_name = event.output_fields.get("k8s.pod.name", "unknown")
        namespace = event.output_fields.get("k8s.ns.name", "default")
        container_key = f"{namespace}/{pod_name}"
        self.event_buckets[container_key]["falco"].append(event)

    def _get_container_id(self, event: TetragonEvent) -> str:
        if event.process_kprobe and event.process_kprobe.process.pod:
            pod = event.process_kprobe.process.pod
            return f"{pod.get('namespace')}/{pod.get('name')}"
        elif event.process_exec and event.process_exec.pod:
            pod = event.process_exec.pod
            return f"{pod.get('namespace')}/{pod.get('name')}"
        return "host"

    def aggregate_features(self, container_key: str) -> Dict[str, Any]:
        bucket = self.event_buckets[container_key]
        syscalls = bucket["syscalls"]
        flows = bucket["network"]

        if not syscalls and not flows:
            return {}

        features = {
            "container_key": container_key,
            # Syscall Features
            "syscall_count": 0,
            "execve_count": 0,
            "open_count": 0,
            "socket_count": 0,
            "connect_count": 0,
            "unique_binaries_count": 0,
            # Network Features
            "flow_count": 0,
            "unique_destinations_count": 0,
            "tcp_count": 0,
            "udp_count": 0,
            "total_bytes": 0,
        }

        # Syscall aggregation
        binaries = set()
        for ev in syscalls:
            if ev.process_kprobe:
                features["syscall_count"] += 1
                sc = ev.process_kprobe.syscall
                if "execve" in sc: features["execve_count"] += 1
                elif "open" in sc: features["open_count"] += 1
                elif "socket" in sc: features["socket_count"] += 1
                elif "connect" in sc: features["connect_count"] += 1
                binaries.add(ev.process_kprobe.process.binary)
            elif ev.process_exec:
                features["execve_count"] += 1
                binaries.add(ev.process_exec.binary)
        features["unique_binaries_count"] = len(binaries)

        # Network aggregation
        destinations = set()
        for flow in flows:
            features["flow_count"] += 1
            dest_ip = flow.IP.get("destination", "") if flow.IP else ""
            if dest_ip: destinations.add(dest_ip)

            if flow.L4:
                if flow.L4.get("TCP"): features["tcp_count"] += 1
                elif flow.L4.get("UDP"): features["udp_count"] += 1
            
            # Assuming bytes is in a standard location if enriched
            # features["total_bytes"] += flow.IP.get("length", 0) if flow.IP else 0

        features["unique_destinations_count"] = len(destinations)

        # Falco aggregation
        features["falco_alert_count"] = len(bucket["falco"])
        features["max_priority"] = max([f.priority for f in bucket["falco"]]) if bucket["falco"] else "None"

        # Reset bucket
        self.event_buckets[container_key] = {"syscalls": [], "network": [], "falco": []}

        return features
