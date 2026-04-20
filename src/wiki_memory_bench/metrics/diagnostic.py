"""Synthetic diagnostic metric helpers."""

from __future__ import annotations

from wiki_memory_bench.schemas import EvaluatedExampleResult


def summarize_diagnostic_metrics(results: list[EvaluatedExampleResult]) -> dict[str, float]:
    """Aggregate synthetic wiki-memory metrics from operation labels."""

    if not results:
        return {}

    metrics: dict[str, float] = {
        "answer_accuracy": sum(1 for result in results if result.is_correct) / len(results),
    }
    operations_to_metric = {
        "update": "update_accuracy",
        "deprecate": "stale_claim_avoidance",
        "forget": "forgetting_compliance",
        "cite": "citation_task_accuracy",
    }

    for operation, metric_name in operations_to_metric.items():
        relevant = [
            result
            for result in results
            if operation in set(result.metadata.get("memory_operations", []))
        ]
        if relevant:
            metrics[metric_name] = sum(1 for result in relevant if result.is_correct) / len(relevant)

    patch_values = [
        float(result.metadata["patch_correctness"])
        for result in results
        if "patch_correctness" in result.metadata
    ]
    if patch_values:
        metrics["patch_correctness"] = sum(patch_values) / len(patch_values)

    source_coverage_values = []
    for result in results:
        expected_source_ids = set(str(value) for value in result.metadata.get("expected_source_ids", []))
        if not expected_source_ids:
            continue
        retrieved_source_ids = set(_extract_source_ids(result))
        source_coverage_values.append(1.0 if expected_source_ids & retrieved_source_ids else 0.0)
    if source_coverage_values:
        metrics["source_coverage"] = sum(source_coverage_values) / len(source_coverage_values)

    return metrics


def _extract_source_ids(result: EvaluatedExampleResult) -> list[str]:
    source_ids: list[str] = []
    for citation in result.citations:
        if citation.source_ref:
            source_ids.extend(value.strip() for value in citation.source_ref.split(",") if value.strip())
            continue
        source_ids.append(citation.clip_id)
    return source_ids
