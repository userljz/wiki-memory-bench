"""Latency aggregation helpers."""

from __future__ import annotations

from wiki_memory_bench.schemas import EvaluatedExampleResult


def summarize_latency(results: list[EvaluatedExampleResult]) -> tuple[float, float]:
    """Return average and total latency in milliseconds."""

    if not results:
        return 0.0, 0.0

    total_latency = sum(result.latency_ms for result in results)
    return total_latency / len(results), total_latency
