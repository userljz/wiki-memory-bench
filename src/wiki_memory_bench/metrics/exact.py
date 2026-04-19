"""Exact and partial match helpers for open-QA tasks."""

from __future__ import annotations

from wiki_memory_bench.schemas import EvaluatedExampleResult, PreparedExample, SystemResult
from wiki_memory_bench.utils.tokens import estimate_text_tokens, normalize_text


def evaluate_open_qa(example: PreparedExample, prediction: SystemResult) -> EvaluatedExampleResult:
    """Evaluate a free-form answer using exact or partial matching."""

    predicted_answer = (prediction.answer_text or "").strip()
    gold_answer = (example.answer or "").strip()
    exact_match, partial_match = compute_open_qa_match(predicted_answer, gold_answer)
    retrieved_token_count = sum(
        item.retrieved_tokens if item.retrieved_tokens > 0 else estimate_text_tokens(item.text)
        for item in prediction.retrieved_items
    )
    citation_precision = prediction.citation_precision
    if citation_precision is None:
        normalized_answer = normalize_text(gold_answer)
        citation_precision = 1.0 if (
            normalized_answer
            and any(normalized_answer in normalize_text(citation.quote or "") for citation in prediction.citations)
        ) else 0.0

    return EvaluatedExampleResult(
        example_id=example.example_id,
        question_id=example.question_id,
        question_type=example.question_type,
        system_name=prediction.system_name,
        answer_text=predicted_answer,
        correct_choice_id="",
        correct_choice_index=-1,
        is_correct=exact_match or partial_match,
        citations=prediction.citations,
        retrieved_items=prediction.retrieved_items,
        token_usage=prediction.token_usage,
        citation_precision=citation_precision,
        wiki_size_pages=prediction.wiki_size_pages,
        wiki_size_tokens=prediction.wiki_size_tokens,
        retrieved_token_count=retrieved_token_count,
        retrieved_chunk_count=len(prediction.retrieved_items),
        latency_ms=prediction.latency_ms,
        metadata={
            **example.metadata,
            **prediction.metadata,
            "exact_match": exact_match,
            "partial_match": partial_match,
        },
    )


def compute_open_qa_match(predicted_answer: str, gold_answer: str) -> tuple[bool, bool]:
    """Return exact and partial match booleans for open QA."""

    normalized_pred = normalize_text(predicted_answer)
    normalized_gold = normalize_text(gold_answer)
    exact_match = normalized_pred == normalized_gold and bool(normalized_gold)
    if exact_match:
        return True, True

    if not normalized_pred or not normalized_gold:
        return False, False

    if normalized_gold in normalized_pred or normalized_pred in normalized_gold:
        return False, True

    gold_tokens = set(normalized_gold.split())
    pred_tokens = set(normalized_pred.split())
    if not gold_tokens or not pred_tokens:
        return False, False

    overlap_ratio = len(gold_tokens & pred_tokens) / len(gold_tokens)
    return False, overlap_ratio >= 0.6
