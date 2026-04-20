import json
import csv
import sys

def flatten_flow(flow_data):
    flow = flow_data.get('flow', {})
    return {
        'time': flow_data.get('time'),
        'source_ip': flow.get('IP', {}).get('source'),
        'dest_ip': flow.get('IP', {}).get('destination'),
        'source_ns': flow.get('source', {}).get('namespace'),
        'source_pod': flow.get('source', {}).get('pod_name'),
        'dest_ns': flow.get('destination', {}).get('namespace'),
        'dest_pod': flow.get('destination', {}).get('pod_name'),
        'dest_port': flow.get('destination', {}).get('port'),
        'protocol': list(flow.get('l4', {}).keys())[0] if flow.get('l4') else 'unknown',
        'verdict': flow.get('verdict'),
        'event_type': flow_data.get('type')
    }

def convert(input_file, output_file):
    with open(input_file, 'r') as f, open(output_file, 'w', newline='') as out:
        writer = None
        for line in f:
            try:
                data = json.loads(line)
                flat = flatten_flow(data)
                if not writer:
                    writer = csv.DictWriter(out, fieldnames=flat.keys())
                    writer.writeheader()
                writer.writerow(flat)
            except Exception as e:
                continue

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 json_to_csv.py <input.json> <output.csv>")
    else:
        convert(sys.argv[1], sys.argv[2])
