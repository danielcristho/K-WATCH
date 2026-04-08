import requests
import json
import logging
import time
from typing import Dict, Any

logger = logging.getLogger(__name__)

class LokiAlertExporter:
    def __init__(self, loki_url: str = "http://loki:3100/loki/api/v1/push"):
        self.loki_url = loki_url

    def send_alert(self, container_key: str, alert_type: str, features: Dict[str, Any]):
        # Loki Push API format: {"streams": [{"stream": {"label": "value"}, "values": [["timestamp_ns", "formatted_JSON"]]}]}
        timestamp_ns = str(time.time_ns())
        
        payload = {
            "streams": [
                {
                    "stream": {
                        "job": "ncc-ids-alerts",
                        "container": container_key,
                        "type": alert_type,
                        "severity": "critical" if alert_type == "MALICIOUS" else "info"
                    },
                    "values": [
                        [timestamp_ns, json.dumps({
                            "msg": f"Intrusion Detected in {container_key}!",
                            "details": features
                        })]
                    ]
                }
            ]
        }
        
        try:
            response = requests.post(self.loki_url, json=payload)
            if response.status_code != 204:
                logger.error(f"Failed to push to Loki: {response.status_code} - {response.text}")
            else:
                logger.info("Alert pushed to Loki successfully.")
        except Exception as e:
            logger.error(f"Error connecting to Loki: {e}")
