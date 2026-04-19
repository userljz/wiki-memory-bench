from pathlib import Path

from typer.testing import CliRunner

from wiki_memory_bench.cli import app
from tests.locomo_fixture import write_locomo_fixture


def test_cli_lists_datasets() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["datasets", "list"])

    assert result.exit_code == 0
    assert "synthetic-mini" in result.output


def test_cli_lists_systems() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["systems", "list"])

    assert result.exit_code == 0
    assert "basic-memory" in result.output
    assert "full-context" in result.output
    assert "bm25" in result.output
    assert "clipwiki" in result.output
    assert "vector-rag" in result.output


def test_cli_run_and_report_smoke(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WMB_HOME": str(tmp_path)}

    full_context_run = runner.invoke(
        app,
        ["run", "--dataset", "synthetic-mini", "--system", "full-context", "--limit", "5"],
        env=env,
    )
    assert full_context_run.exit_code == 0
    assert "Run Complete" in full_context_run.output

    bm25_run = runner.invoke(
        app,
        ["run", "--dataset", "synthetic-mini", "--system", "bm25", "--limit", "5"],
        env=env,
    )
    assert bm25_run.exit_code == 0
    assert "Run Complete" in bm25_run.output

    latest_manifest = tmp_path / "runs" / "latest" / "manifest.json"
    assert latest_manifest.exists()

    report = runner.invoke(app, ["report", "runs/latest"], env=env)
    assert report.exit_code == 0
    assert "Run Overview" in report.output
    assert "synthetic-mini" in report.output


def test_cli_prepare_and_run_locomo_smoke(tmp_path: Path) -> None:
    runner = CliRunner()
    fixture_path = write_locomo_fixture(tmp_path / "locomo_mc10.json")
    env = {
        "WMB_HOME": str(tmp_path),
        "WMB_LOCOMO_MC10_SOURCE_FILE": str(fixture_path),
    }

    prepare_result = runner.invoke(app, ["datasets", "prepare", "locomo-mc10", "--limit", "5"], env=env)
    assert prepare_result.exit_code == 0
    assert "Dataset Prepared" in prepare_result.output

    run_result = runner.invoke(
        app,
        ["run", "--dataset", "locomo-mc10", "--system", "bm25", "--limit", "5"],
        env=env,
    )
    assert run_result.exit_code == 0
    assert "Run Complete" in run_result.output

    report_result = runner.invoke(app, ["report", "runs/latest"], env=env)
    assert report_result.exit_code == 0
    assert "Accuracy by Question Type" in report_result.output
    assert "Avg retrieved tokens" in report_result.output
