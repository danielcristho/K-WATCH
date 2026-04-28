# Malicious Containers Simulation Chart

This Helm chart deploys simulated "malicious" containers for testing Intrusion Detection Systems (IDS) like Tetragon, Falco, or Cilium.

## Supported Simulations

### 1. Mirai
Simulates a botnet that:
- Scans the local network for open ports (SSH, Telnet).
- Attempts connection to external IPs.

### 2. Kinsing
Simulates cryptojacking behavior:
- Downloads a shell script.
- Downloads and executes a "kinsing" binary.
- Runs a "kdevtmpfsi" miner (simulated).

### 3. TeamTNT
Simulates a more complex threat actor targeting cloud environments:
- Searches for AWS/SSH credentials in the filesystem.
- Checks for the presence of a writable Docker socket.
- Attempts to access the Cloud Metadata Service (169.254.169.254).
- Tries to establish persistence via crontab.
- Runs a simulated `xmrig` miner.

## Installation

```bash
helm install my-test-attack ./deploy/malicious-containers
```

## Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `mirai.enabled` | Enable Mirai simulation | `true` |
| `kinsing.enabled` | Enable Kinsing simulation | `true` |
| `teamtnt.enabled` | Enable TeamTNT simulation | `true` |
| `teamtnt.simulateHostMount` | Mount host /var/run/docker.sock (Dangerous!) | `false` |
