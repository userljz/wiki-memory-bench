"""Logging and console helpers."""

from __future__ import annotations

from rich.console import Console

_CONSOLE = Console()


def get_console() -> Console:
    """Return the shared Rich console instance."""

    return _CONSOLE
