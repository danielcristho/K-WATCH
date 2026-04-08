import sys
import json
import logging
from .models import TetragonEvent, CiliumFlowEvent
from .processor import HybridFeatureProcessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CollectorApp:
    def __init__(self, output_file: str = "features.csv"):
        self.processor = HybridFeatureProcessor(window_seconds=10)
        self.output_file = output_file

    def run_from_stdin(self):
        logger.info("Collector started, reading from stdin...")
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

            except Exception as e:
                # logger.error(f"Failed to parse line: {e}")
                continue

    def flush_and_save(self, container_key: str):
        features = self.processor.aggregate_features(container_key)
        if features:
            logger.info(f"Aggregated features for {container_key}: {features}")
            # Here we would save to CSV or forward to an ML model

if __name__ == "__main__":
    app = CollectorApp()
    app.run_from_stdin()
