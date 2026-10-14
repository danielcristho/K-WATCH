import json
from pathlib import Path


class LogTailer:
    def __init__(self, path: Path):
        self.path = path
        self._inode = None
        self.offset = 0
        if path.exists():
            stat = path.stat()
            self._inode = stat.st_ino
            self.offset = stat.st_size

    def read_new(self):
        if not self.path.exists():
            return []
        stat = self.path.stat()
        # Detect log rotation: inode changed or file shrunk
        if stat.st_ino != self._inode or stat.st_size < self.offset:
            self._inode = stat.st_ino
            self.offset = 0
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


if __name__ == "__main__":
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "flows.log"
        p.write_text('{"a": 1}\n')
        tail = LogTailer(p)
        assert tail.read_new() == [], "a fresh tailer starts at the end"

        with p.open("a") as f:
            f.write('{"a": 2}\n')
        assert tail.read_new() == [{"a": 2}], "appended lines must be read"

        # Hubble rotates by renaming, so the live path stays and the new file is smaller
        os.rename(p, Path(d) / "flows-rotated.log")
        p.write_text('{"a": 3}\n')
        assert tail.read_new() == [{"a": 3}], "rotation by rename must reset the offset"

    print("ok: tailer survives rename-based rotation")
