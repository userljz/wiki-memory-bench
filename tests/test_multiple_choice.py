from datetime import datetime

from wiki_memory_bench.metrics.multiple_choice import evaluate_multiple_choice
from wiki_memory_bench.schemas import ChoiceOption, HistoryClip, PreparedExample, SystemResult, TaskType


def make_example() -> PreparedExample:
    return PreparedExample(
        example_id="example-1",
        dataset_name="synthetic-mini",
        task_type=TaskType.MULTIPLE_CHOICE,
        question="Which answer is correct?",
        history_clips=[
            HistoryClip(
                clip_id="clip-1",
                conversation_id="conv-1",
                session_id="session-1",
                speaker="user",
                timestamp=datetime.fromisoformat("2026-04-01T09:00:00"),
                text="The answer is Aurora.",
            )
        ],
        choices=[
            ChoiceOption(choice_id="choice-1", label="A", text="Aurora"),
            ChoiceOption(choice_id="choice-2", label="B", text="Seattle"),
            ChoiceOption(choice_id="choice-3", label="C", text="PostgreSQL"),
        ],
        correct_choice_index=0,
        question_type="unit",
    )


def test_multiple_choice_normalizes_label_answer() -> None:
    result = evaluate_multiple_choice(
        make_example(),
        SystemResult(example_id="example-1", system_name="unit", answer_text="A"),
    )
    assert result.is_correct is True
    assert result.selected_choice_index == 0


def test_multiple_choice_normalizes_zero_based_index() -> None:
    numeric = evaluate_multiple_choice(
        make_example(),
        SystemResult(example_id="example-1", system_name="unit", answer_text="0"),
    )
    prefixed = evaluate_multiple_choice(
        make_example(),
        SystemResult(example_id="example-1", system_name="unit", answer_text="choice 0"),
    )
    assert numeric.is_correct is True
    assert prefixed.is_correct is True
    assert prefixed.selected_choice_id == "choice-1"


def test_multiple_choice_normalizes_exact_and_partial_text() -> None:
    exact = evaluate_multiple_choice(
        make_example(),
        SystemResult(example_id="example-1", system_name="unit", answer_text="Aurora"),
    )
    partial = evaluate_multiple_choice(
        make_example(),
        SystemResult(example_id="example-1", system_name="unit", answer_text="Auror"),
    )
    assert exact.is_correct is True
    assert partial.is_correct is True
