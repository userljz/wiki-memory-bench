from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from wiki_memory_bench.cli import app
from wiki_memory_bench.datasets.synthetic_wiki_memory import convert_synthetic_case, generate_synthetic_wiki_memory_cases
from wiki_memory_bench.systems.basic_memory import BasicMemoryAdapter, basic_memory_doctor_payload, detect_basic_memory_cli


def _example():
    record = generate_synthetic_wiki_memory_cases(cases=1, seed=42)[0]
    return convert_synthetic_case(record)


def test_basic_memory_doctor_reports_missing_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("wiki_memory_bench.systems.basic_memory.shutil.which", lambda command: None)
    payload = basic_memory_doctor_payload()

    assert payload["available"] is False
    assert payload["mode"] == "file-compatible-local-fallback"


def test_basic_memory_doctor_reports_installed_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "wiki_memory_bench.systems.basic_memory.shutil.which",
        lambda command: "/usr/bin/bm" if command == "bm" else None,
    )

    def fake_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="basic-memory 0.19.0\n", stderr="")

    monkeypatch.setattr("wiki_memory_bench.systems.basic_memory.subprocess.run", fake_run)
    status = detect_basic_memory_cli()

    assert status.available is True
    assert status.command == "bm"
    assert "0.19.0" in (status.version or "")


def test_basic_memory_adapter_uses_subprocess_when_cli_available(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    commands: list[list[str]] = []

    monkeypatch.setattr(
        "wiki_memory_bench.systems.basic_memory.shutil.which",
        lambda command: "/usr/bin/bm" if command == "bm" else None,
    )

    def fake_run(command, **kwargs):  # type: ignore[no-untyped-def]
        commands.append(command)
        if command == ["bm", "--version"]:
            return subprocess.CompletedProcess(args=command, returncode=0, stdout="basic-memory 0.19.0\n", stderr="")
        if command == ["bm", "sync"]:
            return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")
        if command[:3] == ["bm", "tool", "search-notes"]:
            return subprocess.CompletedProcess(
                args=command,
                returncode=0,
                stdout=json.dumps({"query": "q", "total": 0, "page": 1, "page_size": 4, "results": []}),
                stderr="",
            )
        return subprocess.CompletedProcess(args=command, returncode=1, stdout="", stderr="unexpected")

    monkeypatch.setattr("wiki_memory_bench.systems.basic_memory.subprocess.run", fake_run)

    adapter = BasicMemoryAdapter()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    adapter.prepare_run(run_dir, "synthetic-wiki-memory")
    prediction = adapter.run(_example())

    assert prediction.retrieved_items
    assert any(command == ["bm", "sync"] for command in commands)
    assert any(command[:3] == ["bm", "tool", "search-notes"] for command in commands)


def test_basic_memory_adapter_falls_back_without_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("wiki_memory_bench.systems.basic_memory.shutil.which", lambda command: None)
    adapter = BasicMemoryAdapter()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    adapter.prepare_run(run_dir, "synthetic-wiki-memory")

    prediction = adapter.run(_example())

    assert prediction.retrieved_items
    assert prediction.metadata["basic_memory_backend"] == "local-fallback"
    assert "basic-memory" in str(run_dir / "artifacts" / "basic-memory")


def test_cli_systems_doctor_basic_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    monkeypatch.setattr("wiki_memory_bench.systems.basic_memory.shutil.which", lambda command: None)
    result = runner.invoke(app, ["systems", "doctor", "basic-memory"])

    assert result.exit_code == 0
    assert "System Doctor" in result.output
    assert "basic-memory" in result.output


def test_cli_run_basic_memory_smoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    monkeypatch.setenv("WMB_HOME", str(tmp_path))
    out_path = tmp_path / "data" / "synthetic" / "wiki_memory_20.jsonl"
    from wiki_memory_bench.datasets.synthetic_wiki_memory import export_synthetic_wiki_memory

    export_synthetic_wiki_memory(cases=20, out_path=out_path, seed=42)
    monkeypatch.setenv("WMB_SYNTHETIC_WIKI_MEMORY_SOURCE_FILE", str(out_path))
    monkeypatch.setattr("wiki_memory_bench.systems.basic_memory.shutil.which", lambda command: None)

    result = runner.invoke(app, ["run", "--dataset", "synthetic-wiki-memory", "--system", "basic-memory", "--limit", "20"])

    assert result.exit_code == 0
    assert "Run Complete" in result.output


@pytest.mark.skipif(
    os.getenv("WMB_RUN_BASIC_MEMORY_INTEGRATION") != "1",
    reason="Set WMB_RUN_BASIC_MEMORY_INTEGRATION=1 to run real Basic Memory integration tests.",
)
def test_basic_memory_integration_optional(tmp_path: Path) -> None:
    status = detect_basic_memory_cli()
    if not status.available:
        pytest.skip("Basic Memory CLI is not installed.")

    adapter = BasicMemoryAdapter()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    adapter.prepare_run(run_dir, "synthetic-wiki-memory")
    prediction = adapter.run(_example())
    assert prediction.retrieved_items
