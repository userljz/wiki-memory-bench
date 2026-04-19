"""Dataset adapter interfaces and registry."""

from __future__ import annotations

import json
import random
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path

from wiki_memory_bench.schemas import PreparedDataset
from wiki_memory_bench.utils.paths import ensure_runtime_dirs, prepared_data_dir

DATASET_REGISTRY: dict[str, type["DatasetAdapter"]] = {}


class DatasetAdapter(ABC):
    """Abstract dataset adapter used by the evaluator."""

    name: str
    description: str

    @abstractmethod
    def load(self, limit: int | None = None, sample: int | None = None) -> PreparedDataset:
        """Load a prepared in-memory dataset."""

    def prepare(self, limit: int | None = None, sample: int | None = None) -> tuple[PreparedDataset, Path]:
        """Prepare the dataset and persist it under ``data/prepared``."""

        dataset = self.load(limit=None, sample=None)
        dataset.examples = _apply_sample_to_examples(dataset.examples, sample=sample)
        if limit is not None:
            dataset.examples = dataset.examples[:limit]
        dataset.metadata["example_count"] = len(dataset.examples)
        output_dir = write_prepared_dataset(dataset)
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


def write_prepared_dataset(dataset: PreparedDataset) -> Path:
    """Persist prepared dataset artifacts under ``data/prepared/<dataset>``."""

    ensure_runtime_dirs()
    output_dir = prepared_data_dir(dataset.name)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "name": dataset.name,
        "description": dataset.description,
        "example_count": len(dataset.examples),
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "metadata": dataset.metadata,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (output_dir / "examples.jsonl").write_text(
        "\n".join(example.model_dump_json() for example in dataset.examples) + "\n",
        encoding="utf-8",
    )
    return output_dir


def load_prepared_dataset(name: str, limit: int | None = None, sample: int | None = None) -> PreparedDataset | None:
    """Load a prepared dataset from disk if it exists."""

    output_dir = prepared_data_dir(name)
    manifest_path = output_dir / "manifest.json"
    examples_path = output_dir / "examples.jsonl"
    if not manifest_path.exists() or not examples_path.exists():
        return None

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    example_lines = [line for line in examples_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    example_lines = _apply_sample_to_lines(example_lines, sample=sample)
    if limit is not None:
        example_lines = example_lines[:limit]
    return PreparedDataset.model_validate(
        {
            "name": manifest["name"],
            "description": manifest["description"],
            "examples": [json.loads(line) for line in example_lines],
            "metadata": manifest.get("metadata", {}),
        }
    )


def load_dataset(name: str, limit: int | None = None, sample: int | None = None, **kwargs: object) -> PreparedDataset:
    """Load dataset from prepared cache if possible, otherwise from the adapter."""

    prepared = load_prepared_dataset(name, limit=limit, sample=sample)
    if prepared is not None:
        if limit is None or len(prepared.examples) >= limit:
            return prepared
    dataset = get_dataset(name, **kwargs).load(limit=None, sample=None)
    dataset.examples = _apply_sample_to_examples(dataset.examples, sample=sample)
    if limit is not None:
        dataset.examples = dataset.examples[:limit]
    dataset.metadata["example_count"] = len(dataset.examples)
    return dataset


def prepare_dataset(
    name: str,
    limit: int | None = None,
    sample: int | None = None,
    **kwargs: object,
) -> tuple[PreparedDataset, Path]:
    """Prepare a dataset by name and persist its artifacts."""

    adapter = get_dataset(name, **kwargs)
    return adapter.prepare(limit=limit, sample=sample)


def _apply_sample_to_lines(example_lines: list[str], sample: int | None) -> list[str]:
    if sample is None or sample >= len(example_lines):
        return example_lines
    rng = random.Random(42)
    selected_indices = sorted(rng.sample(range(len(example_lines)), sample))
    return [example_lines[index] for index in selected_indices]


def _apply_sample_to_examples(examples: list[object], sample: int | None) -> list[object]:
    if sample is None or sample >= len(examples):
        return examples
    rng = random.Random(42)
    selected_indices = sorted(rng.sample(range(len(examples)), sample))
    return [examples[index] for index in selected_indices]
