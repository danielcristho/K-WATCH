# K-IDS (Kubernetes Intrusion Detection System)

K-IDS is a hybrid runtime detection system for Kubernetes that utilizes eBPF-based data collection and Machine Learning to detect malicious activity.

## Features
- **eBPF System Call Monitoring**: Utilizing Tetragon to capture host-level syscalls.
- **Cilium Network Flows**: Capturing network-level flow data with metadata.
- **ML Detection**: Using a Decision Tree model to classify activity on syscall and network data.
- **Real-time Alerting**: Integrated with Loki/Grafana for monitoring and incident response.

## Getting Started
See [Implementation Plan](implementation_plan.md) for architecture details.

```sh
Malicious/Benign Container
        ↓
Tetragon (syscall) + Cilium (L3/L4)
        ↓
Raw logs (JSON)
        ↓
Preprocessing & Labeling
        ↓
Dataset (CSV/Parquet)
        ↓
Train Decision Tree
        ↓
Alert → Grafana/Loki (SIEM)
```