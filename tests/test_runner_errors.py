from __future__ import annotations

import json
from pathlib import Path

import pytest

from wiki_memory_bench.runner.evaluator import run_benchmark
from wiki_memory_bench.schemas import Citation, PreparedExample, SystemResult, TokenUsage
from wiki_memory_bench.systems.base import SystemAdapter, choice_index, register_system
from wiki_memory_bench.utils.tokens import estimate_text_tokens


@register_system
class FailingOnSecondExampleSystem(SystemAdapter):
    name = "failing-on-second-example"
    description = "Test-only system that raises for one example."

    def run(self, example: PreparedExample) -> SystemResult:
        if example.example_id == "synthetic-mini-updated-fact":
            raise RuntimeError("intentional per-example failure")
        selected_choice = example.choices[example.correct_choice_index]
        return SystemResult(
            example_id=example.example_id,
            system_name=self.name,
            selected_choice_id=selected_choice.choice_id,
            selected_choice_index=choice_index(example, selected_choice),
            selected_choice_text=selected_choice.text,
            answer_text=selected_choice.text,
            citations=[Citation(clip_id=example.history_clips[0].clip_id, quote=example.history_clips[0].text)] if example.history_clips else [],
            token_usage=TokenUsage(
                input_tokens=estimate_text_tokens(example.question),
                output_tokens=estimate_text_tokens(selected_choice.text),
            ),
        )


def test_continue_on_error_records_failed_example_and_continues(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WMB_HOME", str(tmp_path))

    manifest, summary, results = run_benchmark(
        dataset_name="synthetic-mini",
        system_name="failing-on-second-example",
        limit=3,
        continue_on_error=True,
    )

    assert manifest.continue_on_error is True
    assert manifest.fail_fast is False
    assert manifest.error_policy == "continue_on_error"
    assert summary.example_count == 3
    assert summary.completed_count == 2
    assert summary.error_count == 1
    assert summary.error_rate == pytest.approx(1 / 3)

    error_result = next(result for result in results if result.status == "error")
    assert error_result.example_id == "synthetic-mini-updated-fact"
    assert error_result.error_type == "RuntimeError"
    assert "intentional per-example failure" in (error_result.error_message or "")
    assert error_result.traceback_path is not None
    assert Path(error_result.traceback_path).exists()

    predictions = [
        json.loads(line)
        for line in (Path(manifest.run_dir) / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [record["status"] for record in predictions].count("error") == 1
    assert (Path(manifest.run_dir) / "artifacts" / "errors").exists()


def test_fail_fast_still_raises_on_example_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WMB_HOME", str(tmp_path))

    with pytest.raises(RuntimeError, match="intentional per-example failure"):
        run_benchmark(
            dataset_name="synthetic-mini",
            system_name="failing-on-second-example",
            limit=3,
            continue_on_error=False,
        )


def test_manifest_records_reproducibility_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WMB_HOME", str(tmp_path))

    manifest, _, _ = run_benchmark(
        dataset_name="synthetic-mini",
        system_name="bm25",
        limit=3,
        continue_on_error=False,
    )

    manifest_path = Path(manifest.run_dir) / "manifest.json"
    persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert persisted["continue_on_error"] is False
    assert persisted["fail_fast"] is True
    assert persisted["error_policy"] == "fail_fast"
    assert persisted["cli_version"] == persisted["package_version"]
    assert isinstance(persisted["platform"], dict)
    assert persisted["platform"]["python_version"]
    assert isinstance(persisted["extras_enabled"], list)

    dependency_versions = persisted["dependency_versions"]
    for key in [
        "python",
        "wiki-memory-bench",
        "pydantic",
        "typer",
        "rich",
        "numpy",
        "huggingface_hub",
        "sentence_transformers",
        "litellm",
    ]:
        assert key in dependency_versions


def test_manifest_error_policy_differs_for_continue_on_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WMB_HOME", str(tmp_path))

    fail_fast_manifest, _, _ = run_benchmark(dataset_name="synthetic-mini", system_name="bm25", limit=1)
    continue_manifest, _, _ = run_benchmark(
        dataset_name="synthetic-mini",
        system_name="bm25",
        limit=1,
        continue_on_error=True,
    )

    assert fail_fast_manifest.error_policy == "fail_fast"
    assert continue_manifest.error_policy == "continue_on_error"
