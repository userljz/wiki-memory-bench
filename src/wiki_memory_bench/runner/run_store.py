"""Local run storage helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from wiki_memory_bench.schemas import EvaluatedExampleResult, RunManifest, RunSummary
from wiki_memory_bench.utils.paths import ensure_runtime_dirs, resolve_user_path, runs_dir


def create_run_dir(dataset_name: str, system_name: str) -> tuple[str, datetime, Path]:
    """Create a run directory and return its identifier, start time, and path."""

    ensure_runtime_dirs()
    started_at = datetime.now(timezone.utc)
    run_id = f"{started_at.strftime('%Y%m%dT%H%M%SZ')}-{dataset_name}-{system_name}"
    run_dir = runs_dir() / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    return run_id, started_at, run_dir


def write_run_artifacts(
    manifest: RunManifest,
    results: list[EvaluatedExampleResult],
    summary: RunSummary,
) -> None:
    """Persist manifest, predictions, and summary files for a completed run."""

    run_dir = Path(manifest.run_dir)
    _write_json(run_dir / "manifest.json", manifest.model_dump(mode="json"))
    _write_json(run_dir / "summary.json", summary.model_dump(mode="json"))
    _write_jsonl(run_dir / "predictions.jsonl", [result.model_dump(mode="json") for result in results])
    (run_dir / "summary.md").write_text(_build_summary_markdown(manifest, summary), encoding="utf-8")
    _update_latest_symlink(run_dir)


def load_run_artifacts(run_path_text: str) -> tuple[RunManifest, RunSummary, list[EvaluatedExampleResult]]:
    """Load manifest, summary, and per-example results from a run directory."""

    run_dir = resolve_user_path(run_path_text)
    manifest = RunManifest.model_validate_json((run_dir / "manifest.json").read_text(encoding="utf-8"))
    summary = RunSummary.model_validate_json((run_dir / "summary.json").read_text(encoding="utf-8"))
    results = [
        EvaluatedExampleResult.model_validate_json(line)
        for line in (run_dir / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return manifest, summary, results


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, payloads: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(payload) for payload in payloads) + "\n", encoding="utf-8")


def _update_latest_symlink(run_dir: Path) -> None:
    latest_link = runs_dir() / "latest"
    if latest_link.exists() or latest_link.is_symlink():
        latest_link.unlink()
    latest_link.symlink_to(run_dir.name, target_is_directory=True)


def _build_summary_markdown(manifest: RunManifest, summary: RunSummary) -> str:
    return "\n".join(
        [
            f"# Run Summary: {manifest.run_id}",
            "",
            f"- Dataset: `{summary.dataset_name}`",
            f"- System: `{summary.system_name}`",
            f"- Examples: `{summary.example_count}`",
            f"- Accuracy: `{summary.accuracy:.2%}`",
            f"- Citation precision: `{summary.citation_precision if summary.citation_precision is not None else '-'}`",
            f"- Avg wiki pages: `{summary.avg_wiki_size_pages:.2f}`",
            f"- Avg wiki tokens: `{summary.avg_wiki_size_tokens:.2f}`",
            f"- Avg latency: `{summary.avg_latency_ms:.2f} ms`",
            f"- Retrieval top-k: `{summary.retrieval_top_k}`",
            f"- Avg retrieved chunks: `{summary.avg_retrieved_chunk_count:.2f}`",
            f"- Avg retrieved tokens: `{summary.avg_retrieved_tokens:.2f}`",
            f"- Avg estimated cost: `${summary.avg_estimated_cost_usd:.6f}`",
            f"- Avg tokens: `{summary.avg_total_tokens:.2f}`",
            "",
        ]
    )
