"""Deterministic multiple-choice evaluation helpers."""

from __future__ import annotations

import re

from wiki_memory_bench.schemas import ChoiceOption, EvaluatedExampleResult, PreparedExample, SystemResult
from wiki_memory_bench.utils.tokens import estimate_text_tokens, normalize_text

CHOICE_PREFIX_PATTERN = re.compile(r"^(?:choice|option)\s*([0-9]+|[a-z])$")
CHOICE_INLINE_PATTERN = re.compile(r"^([a-z]|[0-9]+)[\).\:\-\s].*$")


def normalize_choice_prediction(
    example: PreparedExample,
    prediction: SystemResult,
) -> tuple[str | None, int | None, str | None]:
    """Normalize a prediction into canonical choice id/index/text."""

    if prediction.selected_choice_id:
        for index, choice in enumerate(example.choices):
            if choice.choice_id == prediction.selected_choice_id:
                return choice.choice_id, index, choice.text

    if prediction.selected_choice_index is not None:
        if 0 <= prediction.selected_choice_index < len(example.choices):
            choice = example.choices[prediction.selected_choice_index]
            return choice.choice_id, prediction.selected_choice_index, choice.text

    candidate_texts = [
        value
        for value in [prediction.selected_choice_text, prediction.answer_text]
        if value is not None and value.strip()
    ]

    for candidate in candidate_texts:
        resolved = _resolve_from_text(example.choices, candidate)
        if resolved is not None:
            index, choice = resolved
            return choice.choice_id, index, choice.text

    return prediction.selected_choice_id, prediction.selected_choice_index, prediction.selected_choice_text


def evaluate_multiple_choice(example: PreparedExample, prediction: SystemResult) -> EvaluatedExampleResult:
    """Evaluate a multiple-choice prediction against the gold answer."""

    selected_choice_id, selected_choice_index, selected_choice_text = normalize_choice_prediction(example, prediction)
    retrieved_token_count = sum(
        item.retrieved_tokens if item.retrieved_tokens > 0 else estimate_text_tokens(item.text)
        for item in prediction.retrieved_items
    )
    normalized_answer = normalize_text(example.answer or "")
    citation_precision = prediction.citation_precision
    if citation_precision is None:
        citation_precision = 1.0 if (
            normalized_answer
            and any(normalized_answer in normalize_text(citation.quote or "") for citation in prediction.citations)
        ) else 0.0

    return EvaluatedExampleResult(
        example_id=example.example_id,
        question_id=example.question_id,
        question_type=example.question_type,
        system_name=prediction.system_name,
        selected_choice_id=selected_choice_id,
        selected_choice_index=selected_choice_index,
        selected_choice_text=selected_choice_text,
        answer_text=prediction.answer_text or selected_choice_text,
        correct_choice_id=example.correct_choice_id,
        correct_choice_index=example.correct_choice_index,
        is_correct=selected_choice_index == example.correct_choice_index,
        citations=prediction.citations,
        retrieved_items=prediction.retrieved_items,
        token_usage=prediction.token_usage,
        citation_precision=citation_precision,
        wiki_size_pages=prediction.wiki_size_pages,
        wiki_size_tokens=prediction.wiki_size_tokens,
        retrieved_token_count=retrieved_token_count,
        retrieved_chunk_count=len(prediction.retrieved_items),
        latency_ms=prediction.latency_ms,
        metadata={**example.metadata, **prediction.metadata},
    )


def summarize_accuracy(results: list[EvaluatedExampleResult]) -> tuple[int, float]:
    """Return correct count and accuracy."""

    if not results:
        return 0, 0.0
    correct_count = sum(1 for result in results if result.is_correct)
    return correct_count, correct_count / len(results)


def summarize_accuracy_by_question_type(results: list[EvaluatedExampleResult]) -> dict[str, float]:
    """Return accuracy grouped by question type."""

    grouped: dict[str, list[bool]] = {}
    for result in results:
        grouped.setdefault(result.question_type, []).append(result.is_correct)
    return {
        question_type: sum(1 for value in values if value) / len(values)
        for question_type, values in sorted(grouped.items())
    }


def _resolve_from_text(choices: list[ChoiceOption], candidate: str) -> tuple[int, ChoiceOption] | None:
    normalized_candidate = normalize_text(candidate)

    for index, choice in enumerate(choices):
        if normalized_candidate == normalize_text(choice.choice_id):
            return index, choice

    for index, choice in enumerate(choices):
        if normalized_candidate == normalize_text(choice.label):
            return index, choice

    if normalized_candidate.isdigit():
        numeric_index = int(normalized_candidate)
        if 0 <= numeric_index < len(choices):
            return numeric_index, choices[numeric_index]
        if 1 <= numeric_index <= len(choices):
            return numeric_index - 1, choices[numeric_index - 1]

    prefixed_match = CHOICE_PREFIX_PATTERN.match(normalized_candidate)
    if prefixed_match:
        return _resolve_from_text(choices, prefixed_match.group(1))

    inline_match = CHOICE_INLINE_PATTERN.match(normalized_candidate)
    if inline_match:
        inline = _resolve_from_text(choices, inline_match.group(1))
        if inline is not None:
            return inline

    exact_matches = [
        (index, choice)
        for index, choice in enumerate(choices)
        if normalize_text(choice.text) == normalized_candidate
    ]
    if len(exact_matches) == 1:
        return exact_matches[0]

    substring_matches = [
        (index, choice)
        for index, choice in enumerate(choices)
        if normalized_candidate in normalize_text(choice.text)
        or normalize_text(choice.text) in normalized_candidate
    ]
    if len(substring_matches) == 1:
        return substring_matches[0]

    candidate_tokens = set(normalized_candidate.split())
    token_subset_matches = [
        (index, choice)
        for index, choice in enumerate(choices)
        if candidate_tokens and candidate_tokens.issubset(set(normalize_text(choice.text).split()))
    ]
    if len(token_subset_matches) == 1:
        return token_subset_matches[0]

    return None
