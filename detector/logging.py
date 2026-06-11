from loguru import logger
from rich.console import Console
from rich.logging import RichHandler

console = Console(force_terminal=True, color_system="truecolor")

logger.remove()
logger.add(
    RichHandler(console=console, markup=True, rich_tracebacks=True, show_path=False),
    format="{message}",
    level="DEBUG",
)
