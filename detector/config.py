import os
import warnings
from pathlib import Path

from dotenv import load_dotenv

warnings.filterwarnings("ignore", category=UserWarning, module="sklearn")

for env_path in [Path("/opt/k-watch/.env"), Path("/app/.env"), Path(".env")]:
    if env_path.exists():
        load_dotenv(env_path)
        break

TETRAGON_LOG  = Path(os.getenv("TETRAGON_LOG", "/var/run/cilium/tetragon/tetragon.log"))
HUBBLE_LOG    = Path(os.getenv("HUBBLE_LOG", "/var/run/cilium/hubble/kwatch-workloads.log"))
MODEL_DIR     = Path(os.getenv("MODEL_DIR", "/models"))
ALERT_LOG     = Path(os.getenv("ALERT_LOG", "/var/log/k-watch/alerts.json"))
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "30")) # Interval in seconds to check for new logs
NGRAM_SIZE    = int(os.getenv("NGRAM_SIZE", "5"))
BENIGN_LABELS = set(map(int, os.getenv("BENIGN_LABELS", "5,6,7,8").split(",")))
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK", "")
MONITORED_NAMESPACES = set(os.getenv("MONITORED_NAMESPACES", "malicious,benign-workloads,default").split(","))
BENIGN_POD_PATTERNS  = set(os.getenv("BENIGN_POD_PATTERNS", "app-server").split(","))
NODE_NAME            = os.getenv("NODE_NAME", "")
