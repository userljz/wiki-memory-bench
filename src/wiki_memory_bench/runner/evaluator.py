"""Benchmark evaluator orchestration."""

from __future__ import annotations

import subprocess
import sys
import traceback
import platform as platform_module
from datetime import datetime, timezone
from importlib import metadata as importlib_metadata
from pathlib import Path
from time import perf_counter

import wiki_memory_bench
from wiki_memory_bench.datasets import load_dataset
from wiki_memory_bench.judges.deterministic import judge_multiple_choice
from wiki_memory_bench.judges.llm_judge import LLMJudge
from wiki_memory_bench.metrics.citations import summarize_citation_quality, update_answer_dependent_citation_flags
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
    seed: int = 42,
    run_name: str | None = None,
    continue_on_error: bool = False,
) -> tuple[RunManifest, RunSummary, list[EvaluatedExampleResult]]:
    """Execute a dataset/system pair and persist the run artifacts."""

    resolved_system_options = dict(system_options or {})
    dataset = load_dataset(dataset_name, limit=limit, sample=sample, seed=seed)
    system = get_system(system_name, **resolved_system_options)

    run_id, started_at, run_dir = create_run_dir(dataset_name=dataset.name, system_name=system.name)
    system.prepare_run(run_dir, dataset.name)
    llm_judge = LLMJudge() if judge_mode == "llm" else None
    if llm_judge is not None:
        llm_judge.set_artifact_dir(run_dir / "artifacts" / "llm" / "judge")

    results: list[EvaluatedExampleResult] = []
    for example in dataset.examples:
        example_started = perf_counter()
        try:
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

            update_answer_dependent_citation_flags(evaluated)
            results.append(evaluated)
        except Exception as error:
            if not continue_on_error:
                raise
            results.append(
                _error_result(
                    example=example,
                    system_name=system.name,
                    error=error,
                    latency_ms=(perf_counter() - example_started) * 1000.0,
                    error_dir=run_dir / "artifacts" / "errors",
                )
            )

    system.finalize_run()

    completed_at = datetime.now(timezone.utc)
    completed_results = [result for result in results if result.status == "ok"]
    completed_count = len(completed_results)
    error_count = len(results) - completed_count
    correct_count, accuracy = summarize_accuracy(completed_results)
    accuracy_by_question_type = summarize_accuracy_by_question_type(completed_results)
    avg_latency_ms, total_latency_ms = summarize_latency(completed_results)
    avg_input_tokens, avg_output_tokens, avg_total_tokens, total_tokens, avg_estimated_cost_usd, total_estimated_cost_usd = summarize_token_usage(completed_results)
    citation_precision = summarize_citation_precision(completed_results)
    citation_quality = summarize_citation_quality(completed_results)
    diagnostic_metrics = summarize_diagnostic_metrics(completed_results)
    avg_wiki_size_pages, avg_wiki_size_tokens = summarize_wiki_sizes(completed_results)
    avg_retrieved_chunk_count, total_retrieved_chunk_count = summarize_retrieved_chunks(completed_results)
    avg_retrieved_tokens, total_retrieved_tokens = summarize_retrieved_tokens(completed_results)
    retrieval_top_k = max((result.metadata.get("retrieval_top_k", 0) for result in completed_results), default=0) or None
    uses_gold_labels = any(bool(result.metadata.get("uses_gold_labels")) for result in completed_results)
    oracle_mode = any(bool(result.metadata.get("oracle_mode")) for result in completed_results)
    oracle_label = "oracle-upper-bound" if oracle_mode else "non-oracle"
    git_commit, git_dirty, git_status = _git_state()
    answerer_mode = str(resolved_system_options.get("answerer", "deterministic"))
    error_policy = "continue_on_error" if continue_on_error else "fail_fast"
    dependency_versions = _dependency_versions()

    manifest = RunManifest(
        run_id=run_id,
        dataset_name=dataset.name,
        system_name=system.name,
        started_at=started_at,
        completed_at=completed_at,
        run_dir=str(run_dir),
        example_count=len(results),
        limit=limit,
        sample=sample,
        seed=seed,
        run_name=run_name,
        system_options=resolved_system_options,
        answerer=answerer_mode,
        judge=judge_mode,
        dataset_metadata=dataset.metadata,
        package_version=wiki_memory_bench.__version__,
        python_version=sys.version.split()[0],
        cli_version=wiki_memory_bench.__version__,
        continue_on_error=continue_on_error,
        fail_fast=not continue_on_error,
        error_policy=error_policy,
        dependency_versions=dependency_versions,
        platform=_platform_metadata(),
        extras_enabled=_extras_enabled(dependency_versions),
        git_commit=git_commit,
        git_dirty=git_dirty,
        git_status=git_status,
        command=command,
    )
    summary = RunSummary(
        dataset_name=dataset.name,
        system_name=system.name,
        example_count=len(results),
        completed_count=completed_count,
        error_count=error_count,
        error_rate=error_count / len(results) if results else 0.0,
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
        citation_source_precision=citation_quality["citation_source_precision"],
        citation_source_recall=citation_quality["citation_source_recall"],
        citation_source_f1=citation_quality["citation_source_f1"],
        stale_citation_rate=float(citation_quality["stale_citation_rate"] or 0.0),
        answer_correct_but_bad_citation_rate=float(citation_quality["answer_correct_but_bad_citation_rate"] or 0.0),
        unsupported_answer_rate=float(citation_quality["unsupported_answer_rate"] or 0.0),
        diagnostic_metrics=diagnostic_metrics,
        avg_wiki_size_pages=avg_wiki_size_pages,
        avg_wiki_size_tokens=avg_wiki_size_tokens,
        retrieval_top_k=retrieval_top_k,
        avg_retrieved_chunk_count=avg_retrieved_chunk_count,
        total_retrieved_chunk_count=total_retrieved_chunk_count,
        avg_retrieved_tokens=avg_retrieved_tokens,
        total_retrieved_tokens=total_retrieved_tokens,
        oracle_label=oracle_label,
        uses_gold_labels=uses_gold_labels,
        oracle_mode=oracle_mode,
    )
    write_run_artifacts(manifest=manifest, results=results, summary=summary)
    return manifest, summary, results


def _error_result(
    *,
    example: object,
    system_name: str,
    error: Exception,
    latency_ms: float,
    error_dir: Path,
) -> EvaluatedExampleResult:
    error_dir.mkdir(parents=True, exist_ok=True)
    example_id = str(getattr(example, "example_id", "unknown"))
    traceback_path = error_dir / f"{_safe_filename(example_id)}.txt"
    traceback_text = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    traceback_path.write_text(traceback_text, encoding="utf-8")
    return EvaluatedExampleResult(
        example_id=example_id,
        question_id=str(getattr(example, "question_id", example_id)),
        question_type=str(getattr(example, "question_type", "unknown")),
        system_name=system_name,
        status="error",
        error_type=type(error).__name__,
        error_message=str(error),
        traceback_path=str(traceback_path),
        correct_choice_id=str(getattr(example, "correct_choice_id", "") or ""),
        correct_choice_index=int(getattr(example, "correct_choice_index", -1) if getattr(example, "correct_choice_index", -1) is not None else -1),
        is_correct=False,
        latency_ms=latency_ms,
        metadata={"error": True},
    )


def _safe_filename(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in value) or "example"


def _git_state() -> tuple[str | None, bool | None, str | None]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except Exception:
        return None, None, None
    return commit, bool(status), status or "clean"


def _dependency_versions() -> dict[str, str | None]:
    package_names = {
        "python": None,
        "wiki-memory-bench": "wiki-memory-bench",
        "pydantic": "pydantic",
        "typer": "typer",
        "rich": "rich",
        "numpy": "numpy",
        "huggingface_hub": "huggingface-hub",
        "sentence_transformers": "sentence-transformers",
        "litellm": "litellm",
    }
    versions: dict[str, str | None] = {"python": sys.version.split()[0]}
    for key, package_name in package_names.items():
        if package_name is None:
            continue
        try:
            versions[key] = importlib_metadata.version(package_name)
        except importlib_metadata.PackageNotFoundError:
            versions[key] = None
    versions["wiki-memory-bench"] = wiki_memory_bench.__version__
    return versions


def _platform_metadata() -> dict[str, str]:
    return {
        "system": platform_module.system(),
        "release": platform_module.release(),
        "machine": platform_module.machine(),
        "python_implementation": platform_module.python_implementation(),
        "python_version": platform_module.python_version(),
    }


def _extras_enabled(dependency_versions: dict[str, str | None]) -> list[str]:
    extras: list[str] = []
    if dependency_versions.get("sentence_transformers"):
        extras.append("vector")
    if dependency_versions.get("litellm"):
        extras.append("llm")
    return extras
