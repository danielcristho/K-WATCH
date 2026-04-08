import sys
import json
import logging
import csv
import os
import argparse
import threading
import time
from datetime import datetime
from src.collector.models import TetragonEvent, CiliumFlowEvent
from src.collector.processor import HybridFeatureProcessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ids-training")

class DataCollector:
    def __init__(self, output_file: str, label: int, window_size: int = 10):
        self.processor = HybridFeatureProcessor(window_seconds=window_size)
        self.output_file = output_file
        self.label = label
        self.window_size = window_size
        self.running = True
        self._init_csv()

    def _init_csv(self):
        if not os.path.exists(self.output_file):
            fieldnames = [
                "timestamp", "container_key", "syscall_count", 
                "execve_count", "open_count", "socket_count", 
                "connect_count", "unique_binaries_count", 
                "flow_count", "unique_destinations_count", 
                "tcp_count", "udp_count", "label"
            ]
            with open(self.output_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

    def save_features(self, features):
        features["timestamp"] = datetime.now().isoformat()
        features["label"] = self.label
        
        # Map labels from processor names to CSV columns if needed
        # (processor.py uses e.g. "unique_binaries_count")
        
        with open(self.output_file, 'a', newline='') as f:
            fieldnames = [
                "timestamp", "container_key", "syscall_count", 
                "execve_count", "open_count", "socket_count", 
                "connect_count", "unique_binaries_count", 
                "flow_count", "unique_destinations_count", 
                "tcp_count", "udp_count", "label"
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writerow(features)

    def aggregation_loop(self):
        while self.running:
            time.sleep(self.window_size)
            containers = list(self.processor.event_buckets.keys())
            for container_key in containers:
                features = self.processor.aggregate_features(container_key)
                if features:
                    logger.info(f"💾 Saving features for {container_key} with label {self.label}")
                    self.save_features(features)

    def run(self):
        logger.info(f"🚀 Memulai pengumpulan data ke {self.output_file} (Label: {self.label}, Window: {self.window_size}s)")
        
        # Start aggregation thread
        threading.Thread(target=self.aggregation_loop, daemon=True).start()
        
        for line in sys.stdin:
            try:
                data = json.loads(line)
                if "process_kprobe" in data or "process_exec" in data:
                    event = TetragonEvent(**data)
                    self.processor.process_tetragon_event(event)
                elif "flow" in data:
                    event = CiliumFlowEvent(**data["flow"])
                    self.processor.process_cilium_event(event)
            except Exception:
                continue

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IDS Training Data Collector")
    parser.add_argument("--output", default="training_data.csv", help="Output CSV file")
    parser.add_argument("--label", type=int, required=True, help="Label: 0=Normal, 1=Attack")
    parser.add_argument("--window", type=int, default=10, help="Aggregation window in seconds")
    args = parser.parse_args()

    collector = DataCollector(args.output, args.label, window_size=args.window)
    collector.run()
