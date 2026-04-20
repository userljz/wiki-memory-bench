"""Typer CLI for wiki-memory-bench."""

from __future__ import annotations

import typer
from rich.table import Table

from wiki_memory_bench.datasets import list_datasets, prepare_dataset
from wiki_memory_bench.datasets.synthetic_wiki_memory import export_synthetic_wiki_memory
from wiki_memory_bench.runner.evaluator import run_benchmark
from wiki_memory_bench.runner.report import render_report
from wiki_memory_bench.systems import list_systems
from wiki_memory_bench.systems.basic_memory import basic_memory_doctor_payload
from wiki_memory_bench.utils.logging import get_console
from wiki_memory_bench.utils.paths import resolve_user_path

app = typer.Typer(help="Benchmark and evaluation harness for Markdown/Wiki memory systems.")
datasets_app = typer.Typer(help="Inspect available benchmark datasets.")
systems_app = typer.Typer(help="Inspect available benchmark systems.")
synthetic_app = typer.Typer(help="Generate deterministic synthetic benchmark datasets.")

app.add_typer(datasets_app, name="datasets")
app.add_typer(systems_app, name="systems")
app.add_typer(synthetic_app, name="synthetic")


@datasets_app.command("list")
def list_datasets_command() -> None:
    """List registered datasets."""

    console = get_console()
    table = Table(title="Datasets")
    table.add_column("Name")
    table.add_column("Description")

    for dataset in list_datasets():
        table.add_row(dataset.name, dataset.description)

    console.print(table)


@datasets_app.command("prepare")
def prepare_datasets_command(
    dataset_name: str = typer.Argument(..., help="Dataset name, for example locomo-mc10."),
    split: str | None = typer.Option(None, help="Optional dataset split, for example s, m, or oracle."),
    limit: int | None = typer.Option(None, min=1, help="Maximum number of examples to prepare."),
    sample: int | None = typer.Option(None, min=1, help="Random sample size for quick tests."),
) -> None:
    """Prepare a dataset and persist normalized examples under data/prepared."""

    console = get_console()
    dataset, output_dir = prepare_dataset(dataset_name, limit=limit, sample=sample, split=split)

    table = Table(title="Dataset Prepared")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Dataset", dataset.name)
    table.add_row("Prepared dir", str(output_dir))
    table.add_row("Examples", str(len(dataset.examples)))
    console.print(table)


@systems_app.command("list")
def list_systems_command() -> None:
    """List registered systems."""

    console = get_console()
    table = Table(title="Systems")
    table.add_column("Name")
    table.add_column("Description")

    for system in list_systems():
        table.add_row(system.name, system.description)

    console.print(table)


@systems_app.command("doctor")
def systems_doctor_command(
    system_name: str = typer.Argument(..., help="System name to inspect, for example basic-memory."),
) -> None:
    """Show setup and availability diagnostics for an optional system adapter."""

    console = get_console()
    if system_name != "basic-memory":
        raise typer.BadParameter("Only 'basic-memory' is currently supported by systems doctor.")

    payload = basic_memory_doctor_payload()
    table = Table(title="System Doctor")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("System", str(payload["adapter"]))
    table.add_row("Available", str(payload["available"]))
    table.add_row("Command", str(payload["command"]))
    table.add_row("Version", str(payload["version"]))
    table.add_row("Tested version", str(payload["tested_version"]))
    table.add_row("Adapter mode", str(payload["mode"]))
    table.add_row("Backend mode", str(payload["backend_mode"]))
    table.add_row("Install command", str(payload["install_command"]))
    table.add_row("Docs", str(payload["docs"]))
    console.print(table)

    limitations = payload.get("limitations", [])
    if limitations:
        limit_table = Table(title="Limitations")
        limit_table.add_column("Item")
        for item in limitations:
            limit_table.add_row(str(item))
        console.print(limit_table)


@synthetic_app.command("generate")
def synthetic_generate_command(
    cases: int = typer.Option(100, min=1, help="Number of deterministic cases to generate."),
    out: str = typer.Option(
        "data/synthetic/wiki_memory_100.jsonl",
        help="Output JSONL path.",
    ),
    seed: int = typer.Option(42, help="Seed for deterministic generation."),
) -> None:
    """Generate the wiki-style synthetic diagnostic dataset."""

    console = get_console()
    out_path = resolve_user_path(out)
    export_synthetic_wiki_memory(cases=cases, out_path=out_path, seed=seed)

    table = Table(title="Synthetic Dataset Generated")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Cases", str(cases))
    table.add_row("Seed", str(seed))
    table.add_row("Output", str(out_path))
    console.print(table)


@app.command("run")
def run_command(
    dataset: str = typer.Option(..., help="Dataset name, for example synthetic-mini."),
    system: str = typer.Option(..., help="System name, for example full-context or bm25."),
    mode: str | None = typer.Option(None, help="Optional system mode, for example clipwiki modes."),
    answerer: str = typer.Option("deterministic", help="Answerer mode: deterministic or llm."),
    judge: str = typer.Option("deterministic", help="Judge mode: deterministic or llm."),
    limit: int | None = typer.Option(None, min=1, help="Maximum number of examples to run."),
    sample: int | None = typer.Option(None, min=1, help="Random sample size for quick tests."),
) -> None:
    """Execute a benchmark run and persist the artifacts under runs/."""

    console = get_console()
    manifest, summary, _ = run_benchmark(
        dataset_name=dataset,
        system_name=system,
        limit=limit,
        command=(
            f"wmb run --dataset {dataset} --system {system}"
            + (f" --mode {mode}" if mode is not None else "")
            + (f" --answerer {answerer}" if answerer != "deterministic" else "")
            + (f" --judge {judge}" if judge != "deterministic" else "")
            + (f" --sample {sample}" if sample is not None else "")
            + (f" --limit {limit}" if limit is not None else "")
        ),
        system_options={
            **({"mode": mode} if mode is not None else {}),
            **({"answerer": answerer} if answerer is not None else {}),
        },
        judge_mode=judge,
        sample=sample,
    )

    table = Table(title="Run Complete")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Run ID", manifest.run_id)
    table.add_row("Run dir", manifest.run_dir)
    table.add_row("Accuracy", f"{summary.accuracy:.2%}")
    table.add_row(
        "Citation precision",
        f"{summary.citation_precision:.2%}" if summary.citation_precision is not None else "-",
    )
    table.add_row("Avg wiki pages", f"{summary.avg_wiki_size_pages:.2f}")
    table.add_row("Avg wiki tokens", f"{summary.avg_wiki_size_tokens:.2f}")
    table.add_row("Avg latency", f"{summary.avg_latency_ms:.2f} ms")
    table.add_row("Retrieval top-k", str(summary.retrieval_top_k) if summary.retrieval_top_k is not None else "-")
    table.add_row("Avg retrieved chunks", f"{summary.avg_retrieved_chunk_count:.2f}")
    table.add_row("Avg retrieved tokens", f"{summary.avg_retrieved_tokens:.2f}")
    table.add_row("Avg estimated cost", f"${summary.avg_estimated_cost_usd:.6f}")
    table.add_row("Avg total tokens", f"{summary.avg_total_tokens:.2f}")
    console.print(table)


@app.command("report")
def report_command(
    run_path: str = typer.Argument(..., help="Run directory path, for example runs/latest."),
    show_prompts: bool = typer.Option(False, help="Show saved LLM prompts and responses when available."),
) -> None:
    """Render a Rich report for a saved run."""

    render_report(run_path, show_prompts=show_prompts)
