import joblib
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn

from config import MODEL_DIR
from log import console

MODEL_FILES = {
    "syscall_scenario": "dt_syscall_scenario_model.pkl",
    "network_scenario": "dt_network_scenario_model.pkl",
    "syscall_binary":   "dt_syscall_binary_model.pkl",
    "network_binary":   "dt_network_binary_model.pkl",
    "feature_syscall":  "feature_names_syscall.pkl",
    "feature_network":  "feature_names_network.pkl",
    "scaler_syscall":   "scaler_syscall.pkl",
    "scaler_network":   "scaler_network.pkl",
    "scenario_names":   "scenario_class_names.pkl",
}


def load_models():
    models = {}
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(),
        TextColumn("[green]{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Loading models...", total=len(MODEL_FILES))
        for key, filename in MODEL_FILES.items():
            progress.update(task, description=f"Loading [cyan]{filename}[/cyan]")
            models[key] = joblib.load(MODEL_DIR / filename)
            progress.advance(task)
    return models
