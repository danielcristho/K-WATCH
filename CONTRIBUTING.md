# Contributing

Contributions are always welcome.

## Getting Started

Fork and clone the repository:

```bash
git clone https://github.com/YOUR_USERNAME/k-watch && cd k-watch
uv sync
```

## Project Structure

```
detector/              # Runtime detector (DaemonSet), with its own pyproject
feature_engineering/   # Data collection and preprocessing notebooks
training/              # Model training notebooks
deployment_charts/     # Kubernetes manifests and Helm charts
wazuh/                 # Decoder and rules for the alerts
ansible/               # Cluster configuration, both distros
terraform/             # AWS EC2 provisioning, the kubeadm layout
vms/                   # libvirt provisioning, the k3s layout
```

## Making Changes

1. Fork the repo and create a branch from `main`
2. Make your changes
3. Test locally where possible
4. Open a pull request with a clear description of what changed and why

## Detector

The detector is a Python application in `detector/`. To run locally:

```bash
cd detector
uv run main.py
```

Configuration comes from `.env`. Copy `.env.example` to `.env` and adjust the paths.
The defaults in `.env.example` assume you run from `detector/`, so `MODEL_DIR=models`
resolves to the tracked `detector/models/`. The container sets `MODEL_DIR=/app/models`
instead, so the two do not collide.

After changes, rebuild and push the Docker image:

```bash
docker build -t your-registry/kwatch_detector:latest detector/
docker push your-registry/kwatch_detector:latest
```

Then update the image in `deployment_charts/k-watch/detector.yaml`.

## Models

To retrain, run `feature_engineering/pre_processing.ipynb` and then
`training/train_model.ipynb`. The notebook writes to `training/models/`, which is
gitignored, so copy the updated `.pkl` files to `detector/models/`. That directory is
tracked and gets baked into the image at build time.

Syscall and network models are separate bundles. `training/read_pkl.ipynb` inspects
what a bundle contains.

## Reporting Issues

Open a GitHub Issue with:

- What you were trying to do
- What happened
- Relevant logs or error messages
