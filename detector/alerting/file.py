"""Append alerts as JSON lines. This file is what Wazuh tails."""

import json
from pathlib import Path


class FileSink:
    def __init__(self, path: Path):
        self.path = path

    def emit(self, alert: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a") as f:
            f.write(json.dumps(alert) + "\n")
