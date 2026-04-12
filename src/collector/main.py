import sys
import json
import logging
from .models import TetragonEvent, CiliumFlowEvent, FalcoEvent
from .processor import HybridFeatureProcessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CollectorApp:
    def __init__(self, output_file: str = "training_data.csv"):
        self.processor = HybridFeatureProcessor(window_seconds=10)
        self.output_file = output_file
        self._init_csv()

    def _init_csv(self):
        # Create CSV header if file doesn't exist
        import os
        if not os.path.exists(self.output_file):
            cols = self.processor.feature_columns + ["label", "container_key"]
            with open(self.output_file, 'w') as f:
                f.write(",".join(cols) + "\n")

    def get_label(self, container_key: str) -> int:
        if "malicious" in container_key.lower():
            return 1
        return 0

    def run_from_stdin(self):
        logger.info("Collector started, reading from stdin...")
        import time
        last_flush = time.time()
        
        for line in sys.stdin:
            try:
                data = json.loads(line)
                
                # Check for Tetragon vs Cilium
                # Simple check: Tetragon often has 'process_kprobe' or 'process_exec'
                if "process_kprobe" in data or "process_exec" in data:
                    event = TetragonEvent(**data)
                    self.processor.process_tetragon_event(event)
                
                # Cilium Hubble often has 'flow' or 'source'/'destination'
                elif "flow" in data:
                    event = CiliumFlowEvent(**data["flow"])
                    self.processor.process_cilium_event(event)
                
                # Falco Alert
                elif "rule" in data and "output" in data:
                    event = FalcoEvent(**data)
                    self.processor.process_falco_event(event)

                # Periodic flush
                if time.time() - last_flush > 5:
                    for key in list(self.processor.event_buckets.keys()):
                        self.flush_and_save(key)
                    last_flush = time.time()

            except Exception as e:
                # logger.error(f"Failed to parse line: {e}")
                continue

    def flush_and_save(self, container_key: str):
        features = self.processor.aggregate_features(container_key)
        if features:
            label = self.get_label(container_key)
            features["label"] = label
            
            logger.info(f"Saving features for {container_key} (Label: {label})")
            
            # Append to CSV
            cols = self.processor.feature_columns + ["label", "container_key"]
            row = [str(features.get(c, 0)) for c in cols]
            with open(self.output_file, 'a') as f:
                f.write(",".join(row) + "\n")

if __name__ == "__main__":
    app = CollectorApp()
    app.run_from_stdin()
