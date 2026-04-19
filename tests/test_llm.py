from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from tests.locomo_fixture import write_locomo_fixture
from wiki_memory_bench.cli import app
from wiki_memory_bench.runner.evaluator import run_benchmark
from wiki_memory_bench.utils.llm import LiteLLMRuntime


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeUsage:
    def __init__(self, prompt_tokens: int = 11, completion_tokens: int = 7) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]
        self.usage = _FakeUsage()


def _fake_completion(*, messages, **kwargs):  # type: ignore[no-untyped-def]
    prompt = messages[0]["content"]
    if "score" in prompt and "Gold answer" in prompt:
        payload = {
            "score": 1,
            "reason": "Predicted answer matches the gold answer.",
            "matched_facts": ["matched"],
            "missing_facts": [],
        }
    else:
        first_chunk_line = next((line for line in prompt.splitlines() if line.startswith("Chunk ID: ")), "Chunk ID: unknown")
        chunk_id = first_chunk_line.split("Chunk ID: ", 1)[1].strip()
        payload = {
            "choice_index": 0,
            "choice_text": "Aurora",
            "rationale": "The retrieved context supports choice 0.",
            "citations": [chunk_id],
        }
    return _FakeResponse(json.dumps(payload))


def _fake_completion_cost(*args, **kwargs):  # type: ignore[no-untyped-def]
    return 0.001


def test_litellm_runtime_caches_by_prompt_hash(tmp_path: Path, monkeypatch) -> None:
    calls = {"count": 0}

    def counted_completion(*args, **kwargs):  # type: ignore[no-untyped-def]
        calls["count"] += 1
        return _fake_completion(*args, **kwargs)

    monkeypatch.setattr("wiki_memory_bench.utils.llm.completion", counted_completion)
    monkeypatch.setattr("wiki_memory_bench.utils.llm.completion_cost", _fake_completion_cost)

    runtime = LiteLLMRuntime(
        task_name="answerer",
        model="fake-model",
        api_key="fake-key",
        cache_dir=tmp_path / "cache",
        artifact_dir=tmp_path / "artifacts",
    )

    first = runtime.complete_json("test prompt")
    second = runtime.complete_json("test prompt")

    assert calls["count"] == 1
    assert first[2]["cached"] is False
    assert second[2]["cached"] is True
    assert list((tmp_path / "artifacts").glob("*.json"))


def test_run_benchmark_supports_llm_judge(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("WMB_HOME", str(tmp_path))
    monkeypatch.setenv("LLM_MODEL", "fake-model")
    monkeypatch.setenv("LLM_API_KEY", "fake-key")
    monkeypatch.setattr("wiki_memory_bench.utils.llm.completion", _fake_completion)
    monkeypatch.setattr("wiki_memory_bench.utils.llm.completion_cost", _fake_completion_cost)

    _, _, results = run_benchmark(
        dataset_name="synthetic-mini",
        system_name="full-context",
        limit=1,
        judge_mode="llm",
    )

    assert results[0].is_correct is True
    assert results[0].metadata["judge_mode"] == "llm"
    assert results[0].token_usage.estimated_cost_usd > 0


def test_cli_clipwiki_llm_and_report_show_prompts(tmp_path: Path, monkeypatch) -> None:
    fixture_path = write_locomo_fixture(tmp_path / "locomo_mc10.json")
    runner = CliRunner()

    monkeypatch.setattr("wiki_memory_bench.utils.llm.completion", _fake_completion)
    monkeypatch.setattr("wiki_memory_bench.utils.llm.completion_cost", _fake_completion_cost)

    env = {
        "WMB_HOME": str(tmp_path),
        "WMB_LOCOMO_MC10_SOURCE_FILE": str(fixture_path),
        "LLM_MODEL": "fake-model",
        "LLM_API_KEY": "fake-key",
    }

    prepare_result = runner.invoke(app, ["datasets", "prepare", "locomo-mc10", "--limit", "5"], env=env)
    assert prepare_result.exit_code == 0

    run_result = runner.invoke(
        app,
        ["run", "--dataset", "locomo-mc10", "--system", "clipwiki", "--answerer", "llm", "--limit", "5"],
        env=env,
    )
    assert run_result.exit_code == 0
    assert "Avg estimated cost" in run_result.output

    report_result = runner.invoke(app, ["report", "runs/latest", "--show-prompts"], env=env)
    assert report_result.exit_code == 0
    assert "LLM Prompts" in report_result.output
