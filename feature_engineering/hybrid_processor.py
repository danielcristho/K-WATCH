import json
import pandas as pd
import numpy as np
from datetime import datetime
import os

def load_tetragon(filepath):
    """Load and parse Tetragon JSON logs."""
    records = []
    if not os.path.exists(filepath):
        print(f"Warning: {filepath} not found.")
        return pd.DataFrame()
    with open(filepath) as f:
        for line in f:
            try:
                data = json.loads(line)
                kprobe = data.get("process_kprobe", {})
                process = kprobe.get("process", {})
                pod = process.get("pod", {})
                
                if not pod: continue
                
                records.append({
                    "time": pd.to_datetime(data.get("time")),
                    "pod_name": pod.get("name"),
                    "namespace": pod.get("namespace"),
                    "syscall": kprobe.get("function_name"),
                    "binary": process.get("binary")
                })
            except: continue
    return pd.DataFrame(records)

def load_hubble(filepath):
    """Load and parse Hubble JSON logs."""
    records = []
    if not os.path.exists(filepath):
        print(f"Warning: {filepath} not found.")
        return pd.DataFrame()
    with open(filepath) as f:
        for line in f:
            try:
                data = json.loads(line)
                flow = data.get("flow", {})
                source = flow.get("source", {})
                
                if not source.get("pod_name"): continue
                
                records.append({
                    "time": pd.to_datetime(flow.get("time")),
                    "pod_name": source.get("pod_name"),
                    "namespace": source.get("namespace"),
                    "dest_port": flow.get("destination", {}).get("port"),
                    "protocol": "TCP" if flow.get("l4", {}).get("TCP") else "UDP" if flow.get("l4", {}).get("UDP") else "ICMP",
                    "verdict": flow.get("verdict")
                })
            except: continue
    return pd.DataFrame(records)

def extract_ngrams(sequence, n=5):
    """Convert syscall list to n-gram strings."""
    if not sequence or len(sequence) == 0: return ""
    if len(sequence) < n: return "|".join(sequence)
    ngrams = ["|".join(sequence[i:i+n]) for i in range(len(sequence)-n+1)]
    return " ".join(ngrams)

def process_hybrid(sys_file, net_file, window="10s", output="training/hybrid_dataset.csv"):
    print(f"Loading logs ({sys_file}, {net_file})...")
    df_sys = load_tetragon(sys_file)
    df_net = load_hubble(net_file)
    
    if df_sys.empty and df_net.empty:
        print("Error: No data found to process.")
        return

    """
    AGGREGATE SYSCALLS (5-GRAM)
    """
    print("Processing Syscalls into 5-grams...")
    if not df_sys.empty:
        sys_agg = df_sys.groupby(['pod_name', 'namespace', pd.Grouper(key='time', freq=window)])['syscall'].apply(list).reset_index()
        sys_agg['syscall_ngrams'] = sys_agg['syscall'].apply(lambda x: extract_ngrams(x, 5))
        sys_agg['syscall_count'] = sys_agg['syscall'].apply(len)
        sys_agg = sys_agg.drop(columns=['syscall'])
    else:
        sys_agg = pd.DataFrame(columns=['pod_name', 'namespace', 'time', 'syscall_ngrams', 'syscall_count'])

    """
    AGGREGATE NETWORK (STATS)
    """
    print("Processing Network flows...")
    if not df_net.empty:
        net_agg = df_net.groupby(['pod_name', 'namespace', pd.Grouper(key='time', freq=window)]).agg(
            flow_count=('verdict', 'count'),
            tcp_count=('protocol', lambda x: (x == 'TCP').sum()),
            udp_count=('protocol', lambda x: (x == 'UDP').sum()),
            dropped_count=('verdict', lambda x: (x == 'DROPPED').sum())
        ).reset_index()
    else:
        net_agg = pd.DataFrame(columns=['pod_name', 'namespace', 'time', 'flow_count', 'tcp_count', 'udp_count', 'dropped_count'])

    # Merge datas
    print("Merging Hubble & Tetragon data...")
    hybrid_df = pd.merge(sys_agg, net_agg, on=['pod_name', 'namespace', 'time'], how='outer').fillna(0)

    # Labeling
    print("Labeling (Namespace: malicious -> 1, others -> 0)...")
    hybrid_df['label'] = hybrid_df['namespace'].apply(lambda x: 1 if x == 'malicious' else 0)

    # Create training dir if not exists
    os.makedirs(os.path.dirname(output), exist_ok=True)
    hybrid_df.to_csv(output, index=False)
    print(f"Hybrid dataset saved to: {output}")
    print(f"Summary: {len(hybrid_df)} samples (Attack: {sum(hybrid_df['label'] == 1)}, Normal: {sum(hybrid_df['label'] == 0)})")

if __name__ == "__main__":
    process_hybrid("tetragon.json", "hubble.json")
