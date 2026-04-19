from pathlib import Path

from typer.testing import CliRunner

from wiki_memory_bench.cli import app
from wiki_memory_bench.datasets import get_dataset
from wiki_memory_bench.datasets.synthetic_wiki_memory import (
    default_synthetic_wiki_memory_path,
    export_synthetic_wiki_memory,
    generate_synthetic_wiki_memory_cases,
)


def test_synthetic_wiki_memory_generation_is_deterministic() -> None:
    first = generate_synthetic_wiki_memory_cases(cases=10, seed=7)
    second = generate_synthetic_wiki_memory_cases(cases=10, seed=7)
    assert first == second


def test_synthetic_wiki_memory_cases_have_valid_answers_and_unique_ids() -> None:
    cases = generate_synthetic_wiki_memory_cases(cases=100, seed=42)
    ids = [case["case_id"] for case in cases]

    assert len(ids) == len(set(ids))
    for case in cases:
        assert case["expected_answer"]
        assert isinstance(case["expected_source_ids"], list)
        assert isinstance(case["memory_operation_labels"], list)


def test_synthetic_generate_cli_and_dataset_load(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.setenv("WMB_HOME", str(tmp_path))

    result = runner.invoke(
        app,
        ["synthetic", "generate", "--cases", "12", "--out", "data/synthetic/wiki_memory_12.jsonl", "--seed", "99"],
    )
    assert result.exit_code == 0
    assert "Synthetic Dataset Generated" in result.output

    monkeypatch.setenv("WMB_SYNTHETIC_WIKI_MEMORY_SOURCE_FILE", str(tmp_path / "data" / "synthetic" / "wiki_memory_12.jsonl"))
    dataset = get_dataset("synthetic-wiki-memory").load(limit=5)
    assert dataset.name == "synthetic-wiki-memory"
    assert len(dataset.examples) == 5


def test_synthetic_wiki_memory_default_file_is_exportable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("WMB_HOME", str(tmp_path))
    out_path = default_synthetic_wiki_memory_path()
    export_synthetic_wiki_memory(cases=5, out_path=out_path, seed=42)
    assert out_path.exists()


def test_cli_run_synthetic_wiki_memory_clipwiki(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.setenv("WMB_HOME", str(tmp_path))
    out_path = tmp_path / "data" / "synthetic" / "wiki_memory_20.jsonl"
    export_synthetic_wiki_memory(cases=20, out_path=out_path, seed=42)
    monkeypatch.setenv("WMB_SYNTHETIC_WIKI_MEMORY_SOURCE_FILE", str(out_path))

    result = runner.invoke(
        app,
        ["run", "--dataset", "synthetic-wiki-memory", "--system", "clipwiki", "--limit", "10"],
    )
    assert result.exit_code == 0
    assert "Run Complete" in result.output
