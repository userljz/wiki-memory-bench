from datetime import datetime

import pytest
from pydantic import ValidationError

from wiki_memory_bench.schemas import ChoiceOption, HistoryClip, PreparedExample, TaskType, TokenUsage


def test_prepared_example_requires_matching_correct_choice() -> None:
    clip = HistoryClip(
        clip_id="clip-1",
        conversation_id="conv-1",
        session_id="session-1",
        speaker="user",
        timestamp=datetime.fromisoformat("2026-04-01T09:00:00"),
        text="A short memory clip.",
    )

    with pytest.raises(ValidationError):
        PreparedExample(
            example_id="example-1",
            dataset_name="synthetic-mini",
            task_type=TaskType.MULTIPLE_CHOICE,
            question="Which choice is correct?",
            history_clips=[clip],
            choices=[
                ChoiceOption(choice_id="choice-1", label="A", text="A"),
                ChoiceOption(choice_id="choice-2", label="B", text="B"),
            ],
            correct_choice_id="choice-missing",
        )


def test_token_usage_syncs_total_tokens() -> None:
    usage = TokenUsage(input_tokens=11, output_tokens=4)
    assert usage.total_tokens == 15


def test_prepared_example_syncs_index_and_answer() -> None:
    clip = HistoryClip(
        clip_id="clip-1",
        conversation_id="conv-1",
        session_id="session-1",
        speaker="user",
        timestamp=datetime.fromisoformat("2026-04-01T09:00:00"),
        text="A short memory clip.",
    )

    example = PreparedExample(
        example_id="example-1",
        dataset_name="synthetic-mini",
        task_type=TaskType.MULTIPLE_CHOICE,
        question="Which choice is correct?",
        history_clips=[clip],
        choices=[
            ChoiceOption(choice_id="choice-1", label="A", text="A"),
            ChoiceOption(choice_id="choice-2", label="B", text="B"),
        ],
        correct_choice_index=1,
        question_type="unit",
    )

    assert example.correct_choice_id == "choice-2"
    assert example.answer == "B"
