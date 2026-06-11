import json
from pathlib import Path


class LogTailer:
    def __init__(self, path: Path):
        self.path = path
        self.offset = path.stat().st_size if path.exists() else 0

    def read_new(self):
        if not self.path.exists():
            return []
        records = []
        with open(self.path) as f:
            f.seek(self.offset)
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            self.offset = f.tell()
        return records


class HubbleTailer:
    """Tails the latest kwatch-workloads log file, handling rotation."""

    def __init__(self, directory: Path, prefix: str = "kwatch-workloads"):
        self.directory = directory
        self.prefix = prefix
        self.current_file = None
        self.offset = 0
        self._seek_to_end()

    def _seek_to_end(self):
        latest = self._latest_file()
        if latest:
            self.current_file = latest
            self.offset = latest.stat().st_size

    def _latest_file(self):
        files = sorted(self.directory.glob(f"{self.prefix}*.log"), key=lambda f: f.stat().st_mtime)
        return files[-1] if files else None

    def read_new(self):
        records = []
        latest = self._latest_file()
        if not latest:
            return records

        if latest != self.current_file:
            self.current_file = latest
            self.offset = 0

        with open(self.current_file) as f:
            f.seek(self.offset)
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            self.offset = f.tell()
        return records
