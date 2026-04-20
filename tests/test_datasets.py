from wiki_memory_bench.datasets import get_dataset, list_datasets
from wiki_memory_bench.datasets.base import _apply_sample_to_examples


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
