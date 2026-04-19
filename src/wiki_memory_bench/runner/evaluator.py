"""Benchmark evaluator orchestration."""

from __future__ import annotations

from datetime import datetime, timezone

from wiki_memory_bench.datasets import load_dataset
from wiki_memory_bench.judges.deterministic import judge_multiple_choice
from wiki_memory_bench.judges.llm_judge import LLMJudge
from wiki_memory_bench.metrics.diagnostic import summarize_diagnostic_metrics
from wiki_memory_bench.metrics.exact import evaluate_open_qa
from wiki_memory_bench.metrics.cost import (
    summarize_citation_precision,
    summarize_retrieved_chunks,
    summarize_retrieved_tokens,
    summarize_token_usage,
    summarize_wiki_sizes,
)
from wiki_memory_bench.metrics.latency import summarize_latency
from wiki_memory_bench.metrics.multiple_choice import (
    evaluate_multiple_choice,
    summarize_accuracy,
    summarize_accuracy_by_question_type,
)
from wiki_memory_bench.runner.run_store import create_run_dir, write_run_artifacts
from wiki_memory_bench.schemas import EvaluatedExampleResult, RunManifest, RunSummary, TaskType, TokenUsage
from wiki_memory_bench.systems import get_system


def run_benchmark(
    dataset_name: str,
    system_name: str,
    limit: int | None = None,
    sample: int | None = None,
    command: str | None = None,
    system_options: dict[str, object] | None = None,
    judge_mode: str = "deterministic",
) -> tuple[RunManifest, RunSummary, list[EvaluatedExampleResult]]:
    """Execute a dataset/system pair and persist the run artifacts."""

    dataset = load_dataset(dataset_name, limit=limit, sample=sample)
    system = get_system(system_name, **(system_options or {}))

    run_id, started_at, run_dir = create_run_dir(dataset_name=dataset.name, system_name=system.name)
    system.prepare_run(run_dir, dataset.name)
    llm_judge = LLMJudge() if judge_mode == "llm" else None
    if llm_judge is not None:
        llm_judge.set_artifact_dir(run_dir / "artifacts" / "llm" / "judge")

    results: list[EvaluatedExampleResult] = []
    for example in dataset.examples:
        prediction = system.run(example)
        if example.task_type == TaskType.MULTIPLE_CHOICE:
            evaluated = evaluate_multiple_choice(example, prediction)
        else:
            evaluated = evaluate_open_qa(example, prediction)

        if llm_judge is not None:
            judge_payload, judge_usage, judge_metadata = llm_judge.judge_answer(
                question=example.question,
                gold_answer=example.answer or "",
                predicted_answer=evaluated.answer_text or "",
            )
            evaluated.is_correct = int(judge_payload.get("score", 0)) == 1
            evaluated.metadata = {
                **evaluated.metadata,
                "judge_mode": "llm",
                "judge_reason": judge_payload.get("reason", ""),
                "judge_matched_facts": judge_payload.get("matched_facts", []),
                "judge_missing_facts": judge_payload.get("missing_facts", []),
                "judge_cached": judge_metadata.get("cached", False),
                "judge_artifact_path": judge_metadata.get("artifact_path"),
            }
            evaluated.token_usage = TokenUsage(
                input_tokens=evaluated.token_usage.input_tokens + judge_usage.input_tokens,
                output_tokens=evaluated.token_usage.output_tokens + judge_usage.output_tokens,
                estimated_cost_usd=evaluated.token_usage.estimated_cost_usd + judge_usage.estimated_cost_usd,
            )
        else:
            if example.task_type == TaskType.MULTIPLE_CHOICE:
                score, reason = judge_multiple_choice(evaluated.selected_choice_index, evaluated.correct_choice_index)
                evaluated.is_correct = score == 1
                evaluated.metadata = {**evaluated.metadata, "judge_mode": "deterministic", "judge_reason": reason}
            else:
                match_mode = "exact" if evaluated.metadata.get("exact_match") else "partial" if evaluated.metadata.get("partial_match") else "none"
                evaluated.metadata = {
                    **evaluated.metadata,
                    "judge_mode": "deterministic",
                    "judge_reason": f"Open QA {match_mode} match.",
                }

        results.append(evaluated)

    system.finalize_run()

    completed_at = datetime.now(timezone.utc)
    correct_count, accuracy = summarize_accuracy(results)
    accuracy_by_question_type = summarize_accuracy_by_question_type(results)
    avg_latency_ms, total_latency_ms = summarize_latency(results)
    avg_input_tokens, avg_output_tokens, avg_total_tokens, total_tokens, avg_estimated_cost_usd, total_estimated_cost_usd = summarize_token_usage(results)
    citation_precision = summarize_citation_precision(results)
    diagnostic_metrics = summarize_diagnostic_metrics(results)
    avg_wiki_size_pages, avg_wiki_size_tokens = summarize_wiki_sizes(results)
    avg_retrieved_chunk_count, total_retrieved_chunk_count = summarize_retrieved_chunks(results)
    avg_retrieved_tokens, total_retrieved_tokens = summarize_retrieved_tokens(results)
    retrieval_top_k = max((result.metadata.get("retrieval_top_k", 0) for result in results), default=0) or None

    manifest = RunManifest(
        run_id=run_id,
        dataset_name=dataset.name,
        system_name=system.name,
        started_at=started_at,
        completed_at=completed_at,
        run_dir=str(run_dir),
        example_count=len(results),
        limit=limit,
        command=command,
    )
    summary = RunSummary(
        dataset_name=dataset.name,
        system_name=system.name,
        example_count=len(results),
        correct_count=correct_count,
        accuracy=accuracy,
        accuracy_by_question_type=accuracy_by_question_type,
        avg_latency_ms=avg_latency_ms,
        total_latency_ms=total_latency_ms,
        avg_input_tokens=avg_input_tokens,
        avg_output_tokens=avg_output_tokens,
        avg_total_tokens=avg_total_tokens,
        total_tokens=total_tokens,
        avg_estimated_cost_usd=avg_estimated_cost_usd,
        total_estimated_cost_usd=total_estimated_cost_usd,
        citation_precision=citation_precision,
        diagnostic_metrics=diagnostic_metrics,
        avg_wiki_size_pages=avg_wiki_size_pages,
        avg_wiki_size_tokens=avg_wiki_size_tokens,
        retrieval_top_k=retrieval_top_k,
        avg_retrieved_chunk_count=avg_retrieved_chunk_count,
        total_retrieved_chunk_count=total_retrieved_chunk_count,
        avg_retrieved_tokens=avg_retrieved_tokens,
        total_retrieved_tokens=total_retrieved_tokens,
    )
    write_run_artifacts(manifest=manifest, results=results, summary=summary)
    return manifest, summary, results
