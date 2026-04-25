import json

from wiki_memory_bench.datasets import get_dataset, list_datasets, load_dataset, prepare_dataset
from wiki_memory_bench.datasets.base import _apply_sample_to_examples
from wiki_memory_bench.datasets.synthetic_wiki_memory import export_synthetic_wiki_memory


def test_synthetic_dataset_is_registered() -> None:
    names = [dataset.name for dataset in list_datasets()]
    assert "synthetic-mini" in names
    assert "locomo-mc10" in names
    assert "synthetic-wiki-memory" in names


def test_synthetic_dataset_loads_five_examples() -> None:
    dataset = get_dataset("synthetic-mini").load()
    assert dataset.name == "synthetic-mini"
    assert len(dataset.examples) == 5
    assert [example.metadata["case_type"] for example in dataset.examples] == [
        "direct_recall",
        "updated_fact",
        "temporal_question",
        "contradiction",
        "abstention",
    ]


def test_sampling_returns_deterministic_random_order_not_sorted_prefix() -> None:
    population = list(range(20))
    first = _apply_sample_to_examples(population, sample=10)
    second = _apply_sample_to_examples(population, sample=10)

    assert first == second
    assert first != sorted(first)


def test_prepared_dataset_manifest_records_request_and_source(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("WMB_HOME", str(tmp_path))
    source_path = tmp_path / "source-a.jsonl"
    export_synthetic_wiki_memory(cases=10, out_path=source_path, seed=42)
    monkeypatch.setenv("WMB_SYNTHETIC_WIKI_MEMORY_SOURCE_FILE", str(source_path))

    dataset, output_dir = prepare_dataset("synthetic-wiki-memory", limit=5, sample=5, seed=7)

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["request"] == {
        "dataset_name": "synthetic-wiki-memory",
        "adapter_name": "synthetic-wiki-memory",
        "split": None,
        "limit": 5,
        "sample": 5,
        "seed": 7,
    }
    assert manifest["source"]["path"] == str(source_path.resolve())
    assert manifest["source"]["checksum_sha256"]
    assert len(dataset.examples) == 5


def test_prepared_dataset_cache_requires_matching_request_config(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("WMB_HOME", str(tmp_path))
    source_path = tmp_path / "source-a.jsonl"
    export_synthetic_wiki_memory(cases=10, out_path=source_path, seed=42)
    monkeypatch.setenv("WMB_SYNTHETIC_WIKI_MEMORY_SOURCE_FILE", str(source_path))
    prepare_dataset("synthetic-wiki-memory", limit=5, sample=None, seed=42)

    cached = load_dataset("synthetic-wiki-memory", limit=5, sample=None, seed=42)
    mismatched = load_dataset("synthetic-wiki-memory", limit=4, sample=None, seed=42)

    assert "prepared_cache" in cached.metadata
    assert "prepared_cache" not in mismatched.metadata


def test_prepared_dataset_cache_requires_matching_source_checksum(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("WMB_HOME", str(tmp_path))
    source_a = tmp_path / "source-a.jsonl"
    source_b = tmp_path / "source-b.jsonl"
    export_synthetic_wiki_memory(cases=10, out_path=source_a, seed=42)
    export_synthetic_wiki_memory(cases=10, out_path=source_b, seed=7)
    monkeypatch.setenv("WMB_SYNTHETIC_WIKI_MEMORY_SOURCE_FILE", str(source_a))
    prepare_dataset("synthetic-wiki-memory", limit=5, sample=None, seed=42)

    monkeypatch.setenv("WMB_SYNTHETIC_WIKI_MEMORY_SOURCE_FILE", str(source_b))
    loaded = load_dataset("synthetic-wiki-memory", limit=5, sample=None, seed=42)

    assert "prepared_cache" not in loaded.metadata
    assert loaded.metadata["source_metadata"]["path"] == str(source_b.resolve())
