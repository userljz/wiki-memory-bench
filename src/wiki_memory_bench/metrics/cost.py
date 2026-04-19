"""Token estimate aggregation helpers."""

from __future__ import annotations

from wiki_memory_bench.schemas import EvaluatedExampleResult


def summarize_token_usage(results: list[EvaluatedExampleResult]) -> tuple[float, float, float, int, float, float]:
    """Return average input/output/total tokens and average/total cost."""

    if not results:
        return 0.0, 0.0, 0.0, 0, 0.0, 0.0

    total_input = sum(result.token_usage.input_tokens for result in results)
    total_output = sum(result.token_usage.output_tokens for result in results)
    total_tokens = sum(result.token_usage.total_tokens for result in results)
    total_cost = sum(result.token_usage.estimated_cost_usd for result in results)
    result_count = len(results)

    return (
        total_input / result_count,
        total_output / result_count,
        total_tokens / result_count,
        total_tokens,
        total_cost / result_count,
        total_cost,
    )


def summarize_retrieved_tokens(results: list[EvaluatedExampleResult]) -> tuple[float, int]:
    """Return average and total retrieved tokens."""

    if not results:
        return 0.0, 0

    total_retrieved = sum(result.retrieved_token_count for result in results)
    return total_retrieved / len(results), total_retrieved


def summarize_retrieved_chunks(results: list[EvaluatedExampleResult]) -> tuple[float, int]:
    """Return average and total retrieved chunk counts."""

    if not results:
        return 0.0, 0

    total_chunks = sum(result.retrieved_chunk_count for result in results)
    return total_chunks / len(results), total_chunks


def summarize_citation_precision(results: list[EvaluatedExampleResult]) -> float | None:
    """Return average citation precision when at least one result provides it."""

    values = [result.citation_precision for result in results if result.citation_precision is not None]
    if not values:
        return None
    return sum(values) / len(values)


def summarize_wiki_sizes(results: list[EvaluatedExampleResult]) -> tuple[float, float]:
    """Return average wiki page count and token count."""

    page_values = [result.wiki_size_pages or 0 for result in results]
    token_values = [result.wiki_size_tokens or 0 for result in results]
    if not page_values:
        return 0.0, 0.0
    return sum(page_values) / len(page_values), sum(token_values) / len(token_values)
