"""Post alerts to a Discord webhook, off the detection thread."""

import json
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen

from core.log import logger

COLORS = {"critical": 0xFF0000, "high": 0xFF6600, "info": 0x00FF00}


class DiscordSink:
    def __init__(self, webhook: str, workers: int = 2):
        self.webhook = webhook
        self._pool = ThreadPoolExecutor(max_workers=workers) if webhook else None

    def emit(self, alert: dict) -> None:
        if self._pool:
            self._pool.submit(self._post, alert)

    def _post(self, alert: dict) -> None:
        severity = alert["severity"]
        payload = {"embeds": [{
            "title": f"\U0001f6a8 K-Watch Alert — {severity.upper()}",
            "color": COLORS.get(severity, 0xFFFF00),
            "fields": [
                {"name": "Pod",       "value": f"`{alert['pod_name']}`",      "inline": True},
                {"name": "Namespace", "value": f"`{alert['namespace']}`",     "inline": True},
                {"name": "Node",      "value": f"`{alert['node']}`",          "inline": True},
                {"name": "Scenario",  "value": alert["scenario_result"],      "inline": True},
                {"name": "Binary",    "value": alert["binary_result"].upper(), "inline": True},
                {"name": "Severity",  "value": severity.upper(),              "inline": True},
                {"name": "Syscalls",  "value": str(alert["syscall_count"]),   "inline": True},
                {"name": "Flows",     "value": str(alert["flow_count"]),      "inline": True},
            ],
            "timestamp": alert["timestamp"],
        }]}
        try:
            req = Request(
                self.webhook,
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json", "User-Agent": "K-Watch/1.0"},
            )
            urlopen(req, timeout=5)
        except Exception as exc:
            logger.debug(f"Discord webhook failed: {exc}")
