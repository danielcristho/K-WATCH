import sys
import json
import logging
import time
import threading
from collector.models import TetragonEvent, CiliumFlowEvent
from collector.processor import HybridFeatureProcessor
from detector.model import IDSModel
from alerts.exporter import LokiAlertExporter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("project-kIDS")

class ProjectKIDS:
    def __init__(self, window_size: int = 10):
        self.processor = HybridFeatureProcessor(window_seconds=window_size)
        self.detector = IDSModel()
        self.exporter = LokiAlertExporter()
        self.window_size = window_size
        self.running = True

    def process_stdin(self):
        logger.info("project-kIDS process started, listening to eBPF streams...")
        for line in sys.stdin:
            try:
                data = json.loads(line)
                
                # Tetragon
                if "process_kprobe" in data or "process_exec" in data:
                    event = TetragonEvent(**data)
                    self.processor.process_tetragon_event(event)
                
                # Hubble
                elif "flow" in data:
                    flow_data = data["flow"]
                    event = CiliumFlowEvent(**flow_data)
                    self.processor.process_cilium_event(event)

            except Exception as e:
                # logger.error(f"Error parsing line: {e}")
                continue

    def orchestration_loop(self):
        """Periodically aggregates features and runs inference."""
        while self.running:
            time.sleep(self.window_size)
            
            # Map over all active container buckets
            containers = list(self.processor.event_buckets.keys())
            for container_key in containers:
                features = self.processor.aggregate_features(container_key)
                
                if features:
                    detection = self.detector.predict(features)
                    if detection == 1:
                        logger.warning(f"Detection event for {container_key}!")
                        self.exporter.send_alert(container_key, "MALICIOUS", features)
                    else:
                        logger.info(f"Normal activity for {container_key}")

    def run(self):
        # Run stdin processing in a separate thread so orchestration doesn't block
        threading.Thread(target=self.process_stdin, daemon=True).start()
        self.orchestration_loop()

if __name__ == "__main__":
    ids = ProjectKIDS()
    ids.run()
