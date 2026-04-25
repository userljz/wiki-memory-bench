"""Evidence-aware citation evaluation."""

from __future__ import annotations

import re
from dataclasses import dataclass

from wiki_memory_bench.schemas import Citation, EvaluatedExampleResult, PreparedExample, SystemResult
from wiki_memory_bench.utils.tokens import normalize_text


SOURCE_PAGE_PREFIXES = ("sources/", "evidence/", "preferences/", "events/")


@dataclass(frozen=True)
class CitationEvaluation:
    citation_precision: float
    citation_source_precision: float | None
    citation_source_recall: float | None
    citation_source_f1: float | None
    stale_citation_rate: float
    unsupported_answer: bool
    metric_mode: str
    cited_source_ids: list[str]
    expected_source_ids: list[str]
    stale_source_ids: list[str]


def evaluate_citations(
    example: PreparedExample,
    prediction: SystemResult,
) -> CitationEvaluation:
    """Evaluate citations against source ids when available, else quote fallback."""

    expected_source_ids = _source_ids_from_metadata(example.metadata, "expected_source_ids")
    stale_source_ids = _source_ids_from_metadata(example.metadata, "stale_source_ids")
    cited_source_ids = _cited_source_ids(prediction.citations)

    if expected_source_ids:
        cited_set = set(cited_source_ids)
        expected_set = set(expected_source_ids)
        stale_set = set(stale_source_ids)
        matching = cited_set & expected_set

        precision = len(matching) / len(cited_set) if cited_set else 0.0
        recall = len(matching) / len(expected_set)
        f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
        stale_rate = len(cited_set & stale_set) / len(cited_set) if cited_set else 0.0
        unsupported = not cited_set or not matching
        return CitationEvaluation(
            citation_precision=precision,
            citation_source_precision=precision,
            citation_source_recall=recall,
            citation_source_f1=f1,
            stale_citation_rate=stale_rate,
            unsupported_answer=unsupported,
            metric_mode="source",
            cited_source_ids=sorted(cited_set),
            expected_source_ids=sorted(expected_set),
            stale_source_ids=sorted(stale_set),
        )

    quote_precision = prediction.citation_precision
    if quote_precision is None:
        normalized_answer = normalize_text(example.answer or "")
        quote_precision = (
            1.0
            if normalized_answer
            and any(normalized_answer in normalize_text(citation.quote or "") for citation in prediction.citations)
            else 0.0
        )

    return CitationEvaluation(
        citation_precision=quote_precision,
        citation_source_precision=None,
        citation_source_recall=None,
        citation_source_f1=None,
        stale_citation_rate=0.0,
        unsupported_answer=(not prediction.citations or quote_precision <= 0.0),
        metric_mode="quote_fallback",
        cited_source_ids=sorted(set(cited_source_ids)),
        expected_source_ids=[],
        stale_source_ids=[],
    )


def update_answer_dependent_citation_flags(result: EvaluatedExampleResult) -> None:
    bad_citation = bool(result.metadata.get("unsupported_answer")) or float(result.metadata.get("stale_citation_rate", 0.0) or 0.0) > 0.0
    result.metadata["answer_correct_but_bad_citation"] = bool(result.is_correct and bad_citation)


def summarize_citation_quality(results: list[EvaluatedExampleResult]) -> dict[str, float | None]:
    """Aggregate evidence-aware citation metrics over evaluated examples."""

    def avg(values: list[float]) -> float | None:
        return sum(values) / len(values) if values else None

    source_precision = [float(value) for result in results if (value := result.metadata.get("citation_source_precision")) is not None]
    source_recall = [float(value) for result in results if (value := result.metadata.get("citation_source_recall")) is not None]
    source_f1 = [float(value) for result in results if (value := result.metadata.get("citation_source_f1")) is not None]
    stale_rates = [float(result.metadata.get("stale_citation_rate", 0.0) or 0.0) for result in results]
    unsupported_count = sum(1 for result in results if result.metadata.get("unsupported_answer"))
    correct_results = [result for result in results if result.is_correct]
    correct_bad_count = sum(1 for result in correct_results if result.metadata.get("answer_correct_but_bad_citation"))

    return {
        "citation_source_precision": avg(source_precision),
        "citation_source_recall": avg(source_recall),
        "citation_source_f1": avg(source_f1),
        "stale_citation_rate": avg(stale_rates) or 0.0,
        "unsupported_answer_rate": unsupported_count / len(results) if results else 0.0,
        "answer_correct_but_bad_citation_rate": correct_bad_count / len(correct_results) if correct_results else 0.0,
    }


def _source_ids_from_metadata(metadata: dict[str, object], field: str) -> list[str]:
    values = metadata.get(field, [])
    if not isinstance(values, list):
        return []
    return sorted({str(value) for value in values if str(value).strip()})


def _cited_source_ids(citations: list[Citation]) -> list[str]:
    source_ids: set[str] = set()
    for citation in citations:
        if citation.source_ref:
            for value in citation.source_ref.split(","):
                cleaned = value.strip()
                if cleaned:
                    source_ids.add(cleaned)
            continue
        source_ids.update(_source_ids_from_clip_id(citation.clip_id))
    return sorted(source_ids)


def _source_ids_from_clip_id(clip_id: str) -> set[str]:
    for prefix in SOURCE_PAGE_PREFIXES:
        if clip_id.startswith(prefix):
            return {clip_id.removeprefix(prefix)}
    match = re.search(r":([^:]+):turn-\d+$", clip_id)
    if match:
        return {match.group(1)}
    return {clip_id}
