"""Rich report rendering helpers."""

from __future__ import annotations

import json
from pathlib import Path

from rich.table import Table

from wiki_memory_bench.runner.run_store import load_run_artifacts
from wiki_memory_bench.utils.logging import get_console


def render_report(run_path_text: str, show_prompts: bool = False) -> None:
    """Render a benchmark report for a stored run."""

    console = get_console()
    manifest, summary, results = load_run_artifacts(run_path_text)
    run_dir = Path(manifest.run_dir)

    overview = Table(title="Run Overview")
    overview.add_column("Field")
    overview.add_column("Value")
    overview.add_row("Run ID", manifest.run_id)
    overview.add_row("Dataset", summary.dataset_name)
    overview.add_row("System", summary.system_name)
    overview.add_row("Examples", str(summary.example_count))
    overview.add_row("Accuracy", f"{summary.accuracy:.2%}")
    overview.add_row(
        "Citation precision",
        f"{summary.citation_precision:.2%}" if summary.citation_precision is not None else "-",
    )
    overview.add_row("Avg wiki pages", f"{summary.avg_wiki_size_pages:.2f}")
    overview.add_row("Avg wiki tokens", f"{summary.avg_wiki_size_tokens:.2f}")
    overview.add_row("Avg latency", f"{summary.avg_latency_ms:.2f} ms")
    overview.add_row("Retrieval top-k", str(summary.retrieval_top_k) if summary.retrieval_top_k is not None else "-")
    overview.add_row("Avg retrieved chunks", f"{summary.avg_retrieved_chunk_count:.2f}")
    overview.add_row("Avg retrieved tokens", f"{summary.avg_retrieved_tokens:.2f}")
    overview.add_row("Avg input tokens", f"{summary.avg_input_tokens:.2f}")
    overview.add_row("Avg output tokens", f"{summary.avg_output_tokens:.2f}")
    overview.add_row("Avg total tokens", f"{summary.avg_total_tokens:.2f}")
    overview.add_row("Avg estimated cost", f"${summary.avg_estimated_cost_usd:.6f}")
    overview.add_row("Total estimated cost", f"${summary.total_estimated_cost_usd:.6f}")
    overview.add_row("Total tokens", str(summary.total_tokens))
    console.print(overview)

    if summary.accuracy_by_question_type:
        by_type = Table(title="Accuracy by Question Type")
        by_type.add_column("Question Type")
        by_type.add_column("Accuracy", justify="right")
        for question_type, accuracy in summary.accuracy_by_question_type.items():
            by_type.add_row(question_type, f"{accuracy:.2%}")
        console.print(by_type)

    if summary.diagnostic_metrics:
        diag = Table(title="Diagnostic Metrics")
        diag.add_column("Metric")
        diag.add_column("Value", justify="right")
        for metric_name, metric_value in summary.diagnostic_metrics.items():
            diag.add_row(metric_name, f"{metric_value:.2%}")
        console.print(diag)

    per_example = Table(title="Per-Example Results")
    per_example.add_column("Example ID")
    per_example.add_column("Question Type")
    per_example.add_column("Selected")
    per_example.add_column("Correct")
    per_example.add_column("Citation", justify="right")
    per_example.add_column("Wiki Pages", justify="right")
    per_example.add_column("Wiki Tokens", justify="right")
    per_example.add_column("Latency (ms)", justify="right")
    per_example.add_column("Chunks", justify="right")
    per_example.add_column("Retrieved Tokens", justify="right")
    per_example.add_column("Tokens", justify="right")

    for result in results:
        per_example.add_row(
            result.example_id,
            result.question_type,
            result.selected_choice_text or result.answer_text or "-",
            "yes" if result.is_correct else "no",
            "-" if result.citation_precision is None else f"{result.citation_precision:.2f}",
            str(result.wiki_size_pages or 0),
            str(result.wiki_size_tokens or 0),
            f"{result.latency_ms:.2f}",
            str(result.retrieved_chunk_count),
            str(result.retrieved_token_count),
            str(result.token_usage.total_tokens),
        )
    console.print(per_example)

    if show_prompts:
        prompt_files = sorted((run_dir / "artifacts" / "llm").rglob("*.json")) if (run_dir / "artifacts" / "llm").exists() else []
        prompts_table = Table(title="LLM Prompts")
        prompts_table.add_column("Task")
        prompts_table.add_column("Model")
        prompts_table.add_column("Cached")
        prompts_table.add_column("Prompt Preview")
        prompts_table.add_column("Response Preview")

        for path in prompt_files:
            payload = json.loads(path.read_text(encoding="utf-8"))
            prompt = str(payload.get("prompt", "")).replace("\n", " ")
            response = json.dumps(payload.get("parsed_response", payload.get("raw_response", "")))[:120]
            prompts_table.add_row(
                str(payload.get("task_name", path.stem)),
                str(payload.get("model", "")),
                str(bool(payload.get("cached", False))),
                prompt[:120],
                response,
            )

        if prompt_files:
            console.print(prompts_table)
        else:
            console.print("[bold]No saved LLM prompts found for this run.[/bold]")
