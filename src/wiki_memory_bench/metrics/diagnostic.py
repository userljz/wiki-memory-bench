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

    return metrics
