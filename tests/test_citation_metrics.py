from __future__ import annotations

from datetime import datetime

from wiki_memory_bench.metrics.multiple_choice import evaluate_multiple_choice
from wiki_memory_bench.schemas import Citation, ChoiceOption, HistoryClip, PreparedExample, SystemResult, TaskType


def _example(*, metadata: dict[str, object] | None = None, answer: str = "Aurora") -> PreparedExample:
    return PreparedExample(
        example_id="citation-case",
        dataset_name="unit",
        task_type=TaskType.MULTIPLE_CHOICE,
        question="Which project is active?",
        history_clips=[
            HistoryClip(
                clip_id="clip-1",
                conversation_id="conv-1",
                session_id="source-1",
                speaker="user",
                timestamp=datetime.fromisoformat("2026-01-01T00:00:00"),
                text="Project Aurora is active.",
            )
        ],
        choices=[
            ChoiceOption(choice_id="choice-1", label="A", text=answer),
            ChoiceOption(choice_id="choice-2", label="B", text="Comet"),
        ],
        correct_choice_index=0,
        correct_choice_id="choice-1",
        answer=answer,
        metadata=metadata or {},
    )


def _prediction(citations: list[Citation], *, selected_choice_index: int = 0) -> SystemResult:
    return SystemResult(
        example_id="citation-case",
        system_name="unit-system",
        selected_choice_index=selected_choice_index,
        answer_text="Aurora",
        citations=citations,
    )


def test_multi_source_expected_ids_use_recall_and_f1_not_any_overlap() -> None:
    example = _example(metadata={"expected_source_ids": ["source-1", "source-2"]})
    prediction = _prediction([Citation(clip_id="sources/source-1", quote="Project Aurora is active.")])

    result = evaluate_multiple_choice(example, prediction)

    assert result.metadata["metric_mode"] == "source"
    assert result.metadata["citation_source_precision"] == 1.0
    assert result.metadata["citation_source_recall"] == 0.5
    assert result.metadata["citation_source_f1"] == 2 / 3
    assert result.citation_precision == 1.0


def test_stale_citation_is_counted_and_can_make_correct_answer_bad_citation() -> None:
    example = _example(metadata={"expected_source_ids": ["source-1"], "stale_source_ids": ["source-old"]})
    prediction = _prediction([Citation(clip_id="evidence/source-old", quote="Project Comet used to be active.")])

    result = evaluate_multiple_choice(example, prediction)

    assert result.is_correct is True
    assert result.metadata["citation_source_precision"] == 0.0
    assert result.metadata["citation_source_recall"] == 0.0
    assert result.metadata["stale_citation_rate"] == 1.0
    assert result.metadata["unsupported_answer"] is True


def test_comma_separated_source_ref_is_parsed_as_multiple_source_ids() -> None:
    example = _example(metadata={"expected_source_ids": ["source-1", "source-2"]})
    prediction = _prediction([Citation(clip_id="page-1", source_ref="source-1, source-2", quote="Both sources support Aurora.")])

    result = evaluate_multiple_choice(example, prediction)

    assert result.metadata["cited_source_ids"] == ["source-1", "source-2"]
    assert result.metadata["citation_source_precision"] == 1.0
    assert result.metadata["citation_source_recall"] == 1.0
    assert result.metadata["citation_source_f1"] == 1.0


def test_quote_fallback_remains_when_no_expected_source_ids() -> None:
    example = _example(metadata={})
    prediction = _prediction([Citation(clip_id="unknown", quote="Project Aurora is active.")])

    result = evaluate_multiple_choice(example, prediction)

    assert result.metadata["metric_mode"] == "quote_fallback"
    assert result.metadata["citation_source_precision"] is None
    assert result.citation_precision == 1.0
    assert result.metadata["unsupported_answer"] is False
