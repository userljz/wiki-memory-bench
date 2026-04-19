from wiki_memory_bench.datasets import get_dataset
from wiki_memory_bench.systems import get_system


def test_full_context_baseline_answers_all_synthetic_cases() -> None:
    dataset = get_dataset("synthetic-mini").load()
    system = get_system("full-context")

    predictions = [system.run(example) for example in dataset.examples]

    assert [prediction.selected_choice_id for prediction in predictions] == [
        example.correct_choice_id for example in dataset.examples
    ]
