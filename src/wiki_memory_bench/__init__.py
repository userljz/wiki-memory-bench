"""Public package entrypoints for wiki-memory-bench."""

from .cli import app

__all__ = ["app", "main"]
__version__ = "0.1.0"


def main() -> None:
    """Run the Typer CLI."""
    app(prog_name="wmb")
