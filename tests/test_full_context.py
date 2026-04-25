from datetime import datetime

from wiki_memory_bench.datasets import get_dataset
from wiki_memory_bench.systems import get_system
from wiki_memory_bench.schemas import ChoiceOption, HistoryClip, PreparedExample, TaskType


def test_full_context_baseline_answers_all_synthetic_cases() -> None:
    dataset = get_dataset("synthetic-mini").load()
    system = get_system("full-context")

    predictions = [system.run(example) for example in dataset.examples]

    assert [prediction.selected_choice_id for prediction in predictions] == [
        example.correct_choice_id for example in dataset.examples
    ]
    assert all(prediction.metadata["baseline_type"] == "oracle_upper_bound" for prediction in predictions)
    assert all(prediction.metadata["uses_gold_labels"] is True for prediction in predictions)
    assert all(prediction.metadata["oracle_mode"] is True for prediction in predictions)
    assert all(prediction.metadata["oracle_label"] == "oracle-upper-bound" for prediction in predictions)
    assert all("correct_choice_index" in prediction.metadata["gold_label_fields_used"] for prediction in predictions)


def test_full_context_heuristic_does_not_use_gold_labels() -> None:
    example = PreparedExample(
        example_id="heuristic-check",
        dataset_name="unit",
        task_type=TaskType.MULTIPLE_CHOICE,
        question="Which database should the memory keep as current?",
        history_clips=[
            HistoryClip(
                clip_id="clip-1",
                conversation_id="conv-1",
                session_id="session-1",
                speaker="user",
                timestamp=datetime.fromisoformat("2026-04-01T09:00:00"),
                text="The current database is PostgreSQL.",
            )
        ],
        choices=[
            ChoiceOption(choice_id="choice-1", label="A", text="Redis"),
            ChoiceOption(choice_id="choice-2", label="B", text="PostgreSQL"),
        ],
        correct_choice_index=0,
        question_id="heuristic-check",
        question_type="unit",
        answer="Redis",
    )
    system = get_system("full-context-heuristic")
    prediction = system.run(example)

    assert prediction.selected_choice_id == "choice-2"
    assert prediction.metadata["baseline_type"] == "heuristic_reference"
    assert prediction.metadata["selection_mode"] == "heuristic"
    assert prediction.metadata["uses_gold_labels"] is False
    assert prediction.metadata["oracle_mode"] is False
    assert prediction.metadata["oracle_label"] == "non-oracle"
    assert prediction.metadata["gold_label_fields_used"] == []
