"""
K-IDS Data Collection Helper
"""
import os
import subprocess
import json
import glob
from datetime import datetime


# Constants
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_LOGS_DIR = os.path.join(SCRIPT_DIR, "raw_logs")
SESSIONS_DIR = os.path.join(RAW_LOGS_DIR, "sessions")
KUBECONFIG_PATH = "/mnt/nvme0n1p11/Github/project-kIDS/ansible/kubeconfig"


def _set_kubeconfig():
    """Set KUBECONFIG environment variable."""
    os.environ['KUBECONFIG'] = KUBECONFIG_PATH


def _run_cmd(cmd, capture=True, timeout=120):
    """Run a shell command and return output."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=capture, text=True, timeout=timeout
        )
        if capture:
            return result.stdout.strip(), result.stderr.strip(), result.returncode
        return "", "", result.returncode
    except subprocess.TimeoutExpired:
        return "", "Command timed out", 1


def check_cluster():
    """Verify connection to Kubernetes cluster and print basic info."""
    _set_kubeconfig()

    print("=" * 60)
    print("  Cluster Info")
    print("=" * 60)

    # Get total nodes
    out, _, rc = _run_cmd("kubectl get nodes")
    if rc != 0:
        print("Cannot connect to cluster!")
        return False
    print(f"\nTotal Nodes:\n{out}")

    # Get benign pods
    out, _, _ = _run_cmd("kubectl -n benign-workloads get pods")
    print(f"\nBenign Pods:\n{out}")

    # Get malicious pods
    out, _, _ = _run_cmd("kubectl -n malicious get pods")
    print(f"\nMalicious Pods:\n{out}")

    # Tetragon and HUbble
    out, _, _ = _run_cmd(
        "kubectl -n kube-system get pods | grep -E 'tetragon|hubble'"
    )
    print(f"\nMonitoring:\n{out}")

    print("\n" + "=" * 60)
    return True


def pull_logs(sessions=5, interval=300, stimulate=True):
    """
    Collect logs in multiple sessions with optional workload stimulation.

    Parameters:
        sessions (int): Number of collection sessions (default: 5)
        interval (int): Delay between sessions in seconds (default: 300 = 5 minutes)
        stimulate (bool): Run workload stimulator before collection (default: True)

    Output:
        File-file di raw_logs/sessions/ dan merged di raw_logs/tetragon.json, raw_logs/hubble.json
    """
    _set_kubeconfig()

    print("=" * 60)
    print(f"  K-IDS Multi-Session Data Collection")
    print(f"  Sessions : {sessions}")
    print(f"  Interval : {interval}s ({interval // 60} min)")
    print(f"  Stimulate: {stimulate}")
    total_time = (sessions - 1) * interval
    print(f"  Est. time: ~{total_time // 60} minutes")
    print("=" * 60)
    print()

    # Build command
    script_path = os.path.join(SCRIPT_DIR, "collect_data.sh")
    cmd = f"bash {script_path} --sessions {sessions} --interval {interval}"
    if stimulate:
        cmd += " --stimulate"

    print(f"Running: {cmd}")
    print()

    # Run the collection script (not captured — stream output to user)
    rc = subprocess.call(cmd, shell=True)

    if rc != 0:
        print(f"\nCollection failed with exit code {rc}")
        return False

    print("\nCollection complete!")
    get_collection_stats()
    return True


def pull_logs_single():
    """
    Fallback: single-shot collection (mirip cara lama, tapi lebih baik).
    Berguna untuk testing cepat.
    """
    _set_kubeconfig()
    os.makedirs(RAW_LOGS_DIR, exist_ok=True)

    tetragon_file = os.path.join(RAW_LOGS_DIR, "tetragon.json")
    hubble_file = os.path.join(RAW_LOGS_DIR, "hubble.json")

    print("Pulling Hubble logs...")
    _run_cmd(
        f"kubectl -n kube-system exec ds/cilium -- "
        f"cat /var/run/cilium/hubble/events.log > {hubble_file}",
        capture=False, timeout=300
    )

    print("Pulling Tetragon logs (ALL from export-stdout, not --tail limited)...")
    # Collect dari semua tetragon pods, container export-stdout
    pods_out, _, _ = _run_cmd(
        "kubectl -n kube-system get pods -l app.kubernetes.io/name=tetragon "
        "-o jsonpath='{.items[*].metadata.name}'"
    )
    pods = pods_out.strip("'").split()

    with open(tetragon_file, 'w') as f:
        for pod in pods:
            print(f"  Collecting from {pod}...")
            out, _, _ = _run_cmd(
                f"kubectl -n kube-system logs {pod} -c export-stdout",
                timeout=300
            )
            if out:
                f.write(out + "\n")

    # Stats
    get_collection_stats()


def get_collection_stats():
    """Print statistik dari file log yang terkumpul."""
    print("\n" + "=" * 60)
    print("  Collection Statistics")
    print("=" * 60)

    # Session files
    session_files = sorted(glob.glob(os.path.join(SESSIONS_DIR, "*.json")))
    if session_files:
        print(f"\nSession files ({len(session_files)}):")
        for f in session_files:
            lines = sum(1 for _ in open(f))
            size_kb = os.path.getsize(f) / 1024
            print(f"  {os.path.basename(f)}: {lines:,} lines ({size_kb:.1f} KB)")

    # Merged files
    print(f"\nMerged files:")
    for name in ["tetragon.json", "hubble.json"]:
        path = os.path.join(RAW_LOGS_DIR, name)
        if os.path.exists(path):
            lines = sum(1 for _ in open(path))
            size_mb = os.path.getsize(path) / (1024 * 1024)
            print(f"  {name}: {lines:,} lines ({size_mb:.2f} MB)")

            # Quick content analysis
            if name == "tetragon.json":
                _analyze_tetragon_quick(path)
            elif name == "hubble.json":
                _analyze_hubble_quick(path)
        else:
            print(f"  {name}: not found")

    print()


def _analyze_tetragon_quick(filepath):
    """Quick analysis of tetragon log content."""
    event_types = {}
    namespaces = {}
    pods = set()

    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Count event types
            for key in ['process_kprobe', 'process_exec', 'process_exit']:
                if key in entry:
                    event_types[key] = event_types.get(key, 0) + 1

                    # Extract pod/namespace info
                    process = entry[key].get('process', {})
                    pod_info = process.get('pod', {})
                    ns = pod_info.get('namespace', '')
                    pod_name = pod_info.get('name', '')

                    if ns:
                        namespaces[ns] = namespaces.get(ns, 0) + 1
                    if pod_name:
                        pods.add(pod_name)
                    break

    print(f"    Event types: {event_types}")
    print(f"    Namespaces:  {namespaces}")
    print(f"    Unique pods: {len(pods)} → {list(pods)[:5]}{'...' if len(pods) > 5 else ''}")


def _analyze_hubble_quick(filepath):
    """Quick analysis of hubble log content."""
    flow_count = 0
    namespaces = {}

    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if 'flow' in entry:
                flow_count += 1
                flow = entry['flow']
                src_ns = flow.get('source', {}).get('namespace', '')
                dst_ns = flow.get('destination', {}).get('namespace', '')
                for ns in [src_ns, dst_ns]:
                    if ns:
                        namespaces[ns] = namespaces.get(ns, 0) + 1

    print(f"    Flow records: {flow_count}")
    print(f"    Namespaces:   {namespaces}")
