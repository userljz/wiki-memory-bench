"""Dataset adapter interfaces and registry."""

from __future__ import annotations

import hashlib
import json
import random
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from wiki_memory_bench.schemas import PreparedDataset
from wiki_memory_bench.utils.paths import ensure_runtime_dirs, prepared_data_dir

DATASET_REGISTRY: dict[str, type["DatasetAdapter"]] = {}
DEFAULT_SAMPLE_SEED = 42


class DatasetAdapter(ABC):
    """Abstract dataset adapter used by the evaluator."""

    name: str
    description: str

    @abstractmethod
    def load(self, limit: int | None = None, sample: int | None = None) -> PreparedDataset:
        """Load a prepared in-memory dataset."""

    def prepare(self, limit: int | None = None, sample: int | None = None, seed: int = DEFAULT_SAMPLE_SEED) -> tuple[PreparedDataset, Path]:
        """Prepare the dataset and persist it under ``data/prepared``."""

        dataset = self.load(limit=None, sample=None)
        dataset.examples = _apply_sample_to_examples(dataset.examples, sample=sample, seed=seed)
        if limit is not None:
            dataset.examples = dataset.examples[:limit]
        dataset.metadata["example_count"] = len(dataset.examples)
        request = _prepared_request(
            dataset_name=dataset.name,
            adapter=self,
            limit=limit,
            sample=sample,
            seed=seed,
        )
        source = _source_metadata(self, dataset.metadata)
        dataset.metadata["requested_config"] = request
        dataset.metadata["source_metadata"] = source
        output_dir = write_prepared_dataset(dataset, request=request, source=source)
        return dataset, output_dir


def register_dataset(adapter_class: type[DatasetAdapter]) -> type[DatasetAdapter]:
    """Register a dataset adapter class by its public name."""

    DATASET_REGISTRY[adapter_class.name] = adapter_class
    return adapter_class


def get_dataset(name: str, **kwargs: object) -> DatasetAdapter:
    """Instantiate a dataset adapter by name."""

    try:
        adapter_class = DATASET_REGISTRY[name]
    except KeyError as error:
        available = ", ".join(sorted(DATASET_REGISTRY))
        raise KeyError(f"Unknown dataset '{name}'. Available datasets: {available}") from error
    filtered_kwargs = {key: value for key, value in kwargs.items() if value is not None}
    if filtered_kwargs:
        return adapter_class(**filtered_kwargs)
    return adapter_class()


def list_datasets() -> list[DatasetAdapter]:
    """Return dataset adapters sorted by name."""

    return [DATASET_REGISTRY[name]() for name in sorted(DATASET_REGISTRY)]


def write_prepared_dataset(
    dataset: PreparedDataset,
    *,
    request: dict[str, Any] | None = None,
    source: dict[str, Any] | None = None,
) -> Path:
    """Persist prepared dataset artifacts under ``data/prepared/<dataset>``."""

    ensure_runtime_dirs()
    output_dir = prepared_data_dir(dataset.name)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "name": dataset.name,
        "description": dataset.description,
        "example_count": len(dataset.examples),
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "request": request or {},
        "source": source or _source_from_dataset_metadata(dataset.metadata),
        "metadata": dataset.metadata,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (output_dir / "examples.jsonl").write_text(
        "\n".join(example.model_dump_json() for example in dataset.examples) + "\n",
        encoding="utf-8",
    )
    return output_dir


def load_prepared_dataset(
    name: str,
    limit: int | None = None,
    sample: int | None = None,
    seed: int = DEFAULT_SAMPLE_SEED,
    *,
    request: dict[str, Any] | None = None,
    source: dict[str, Any] | None = None,
) -> PreparedDataset | None:
    """Load a prepared dataset from disk if it exists."""

    output_dir = prepared_data_dir(name)
    manifest_path = output_dir / "manifest.json"
    examples_path = output_dir / "examples.jsonl"
    if not manifest_path.exists() or not examples_path.exists():
        return None

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not _prepared_manifest_matches(manifest, request=request, source=source):
        return None
    example_lines = [line for line in examples_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    example_lines = _apply_sample_to_lines(example_lines, sample=sample, seed=seed)
    if limit is not None:
        example_lines = example_lines[:limit]
    metadata = {
        **manifest.get("metadata", {}),
        "prepared_cache": {
            "manifest_path": str(manifest_path),
            "request": manifest.get("request", {}),
            "source": manifest.get("source", {}),
            "prepared_at": manifest.get("prepared_at"),
        },
    }
    return PreparedDataset.model_validate(
        {
            "name": manifest["name"],
            "description": manifest["description"],
            "examples": [json.loads(line) for line in example_lines],
            "metadata": metadata,
        }
    )


def load_dataset(name: str, limit: int | None = None, sample: int | None = None, seed: int = DEFAULT_SAMPLE_SEED, **kwargs: object) -> PreparedDataset:
    """Load dataset from prepared cache if possible, otherwise from the adapter."""

    adapter = get_dataset(name, **kwargs)
    request = _prepared_request(
        dataset_name=getattr(adapter, "dataset_name", name),
        adapter=adapter,
        limit=limit,
        sample=sample,
        seed=seed,
    )
    source = _source_metadata(adapter)
    prepared = load_prepared_dataset(name, limit=limit, sample=sample, seed=seed, request=request, source=source)
    if prepared is not None:
        if limit is None or len(prepared.examples) >= limit:
            return prepared
    dataset = adapter.load(limit=None, sample=None)
    dataset.examples = _apply_sample_to_examples(dataset.examples, sample=sample, seed=seed)
    if limit is not None:
        dataset.examples = dataset.examples[:limit]
    dataset.metadata["example_count"] = len(dataset.examples)
    dataset.metadata["requested_config"] = request
    dataset.metadata["source_metadata"] = _source_metadata(adapter, dataset.metadata)
    return dataset


def prepare_dataset(
    name: str,
    limit: int | None = None,
    sample: int | None = None,
    seed: int = DEFAULT_SAMPLE_SEED,
    **kwargs: object,
) -> tuple[PreparedDataset, Path]:
    """Prepare a dataset by name and persist its artifacts."""

    adapter = get_dataset(name, **kwargs)
    return adapter.prepare(limit=limit, sample=sample, seed=seed)


def _apply_sample_to_lines(example_lines: list[str], sample: int | None, seed: int = DEFAULT_SAMPLE_SEED) -> list[str]:
    if sample is None or sample >= len(example_lines):
        return example_lines
    rng = random.Random(seed)
    return rng.sample(example_lines, sample)


def _apply_sample_to_examples(examples: list[object], sample: int | None, seed: int = DEFAULT_SAMPLE_SEED) -> list[object]:
    if sample is None or sample >= len(examples):
        return examples
    rng = random.Random(seed)
    return rng.sample(examples, sample)


def _prepared_request(
    *,
    dataset_name: str,
    adapter: DatasetAdapter,
    limit: int | None,
    sample: int | None,
    seed: int,
) -> dict[str, Any]:
    return {
        "dataset_name": dataset_name,
        "adapter_name": str(getattr(adapter, "dataset_name", adapter.name)),
        "split": getattr(adapter, "split_key", None),
        "limit": limit,
        "sample": sample,
        "seed": seed,
    }


def _source_metadata(adapter: DatasetAdapter, dataset_metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    source_path = _resolved_source_path(adapter)
    metadata_source = (dataset_metadata or {}).get("source")
    if source_path is None:
        return _source_from_dataset_metadata({"source": metadata_source or f"built-in:{adapter.name}"})

    return {
        "identifier": str(metadata_source or source_path),
        "path": str(source_path),
        "checksum_sha256": _sha256_file(source_path),
    }


def _source_from_dataset_metadata(dataset_metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "identifier": str(dataset_metadata.get("source", "unknown")),
        "path": None,
        "checksum_sha256": None,
    }


def _resolved_source_path(adapter: DatasetAdapter) -> Path | None:
    resolver = getattr(adapter, "resolve_source_path", None)
    if resolver is None:
        return None
    try:
        path = resolver()
    except Exception:
        return None
    if path is None:
        return None
    return Path(path).expanduser().resolve()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _prepared_manifest_matches(
    manifest: dict[str, Any],
    *,
    request: dict[str, Any] | None,
    source: dict[str, Any] | None,
) -> bool:
    if request is not None and manifest.get("request") != request:
        return False
    if source is not None and manifest.get("source") != source:
        return False
    return True
