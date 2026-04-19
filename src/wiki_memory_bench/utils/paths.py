"""Filesystem path helpers for local benchmark artifacts."""

from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    """Return the benchmark home directory.

    The default is the repository root. Tests can override it with ``WMB_HOME``.
    """

    configured_root = os.getenv("WMB_HOME")
    if configured_root:
        return Path(configured_root).expanduser().resolve()
    return Path(__file__).resolve().parents[3]


def data_dir() -> Path:
    """Return the local data directory."""

    return project_root() / "data"


def prepared_data_dir(dataset_name: str) -> Path:
    """Return the prepared dataset directory for a given dataset name."""

    return data_dir() / "prepared" / dataset_name


def synthetic_data_dir() -> Path:
    """Return the directory for raw synthetic datasets."""

    return data_dir() / "synthetic"


def llm_cache_dir() -> Path:
    """Return the shared on-disk LLM cache directory."""

    return data_dir() / "cache" / "llm"


def runs_dir() -> Path:
    """Return the local runs directory."""

    return project_root() / "runs"


def ensure_runtime_dirs() -> None:
    """Create required runtime directories if they do not exist."""

    data_dir().mkdir(parents=True, exist_ok=True)
    (data_dir() / "prepared").mkdir(parents=True, exist_ok=True)
    synthetic_data_dir().mkdir(parents=True, exist_ok=True)
    llm_cache_dir().mkdir(parents=True, exist_ok=True)
    runs_dir().mkdir(parents=True, exist_ok=True)


def resolve_user_path(path_text: str) -> Path:
    """Resolve a user-facing CLI path relative to the benchmark home."""

    path = Path(path_text)
    if path.is_absolute():
        return path
    return project_root() / path
