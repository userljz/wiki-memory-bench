"""Public package entrypoints for wiki-memory-bench."""

from __future__ import annotations

__all__ = ["app", "main"]
__version__ = "0.1.0"


def main() -> None:
    """Run the Typer CLI."""

    from .cli import app

    app(prog_name="wmb")


def __getattr__(name: str):
    """Lazily expose heavy CLI entrypoints."""

    if name == "app":
        from .cli import app

        return app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
