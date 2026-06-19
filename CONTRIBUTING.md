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
detector/        # Runtime detector (DaemonSet)
training/        # Model training notebook
feature_engineering/  # Data collection and preprocessing
deployment_charts/    # Kubernetes manifests and Helm charts
terraform/       # AWS infrastructure
ansible/         # Cluster configuration
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

It reads from `.env` for configuration — copy `.env.example` to `.env` and adjust paths.

After changes, rebuild and push the Docker image:

```bash
docker build -t your-registry/kwatch_detector:latest detector/
docker push your-registry/kwatch_detector:latest
```

Then update the image in `deployment_charts/k-watch/detector.yaml`.

## Models

To retrain models, run `training/train_model.ipynb`. After training, copy the updated `.pkl` files to `detector/models/`.

## Reporting Issues

Open a GitHub Issue with:

- What you were trying to do
- What happened
- Relevant logs or error messages
