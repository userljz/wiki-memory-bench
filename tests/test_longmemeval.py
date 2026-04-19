from pathlib import Path

from typer.testing import CliRunner

from tests.longmemeval_fixture import build_longmemeval_record, write_longmemeval_fixture
from wiki_memory_bench.cli import app
from wiki_memory_bench.datasets import get_dataset
from wiki_memory_bench.datasets.longmemeval import convert_longmemeval_record


def test_convert_longmemeval_record_preserves_required_fields() -> None:
    record = build_longmemeval_record(1, "single-session-user", "What degree did I graduate with?", "Business Administration")
    case = convert_longmemeval_record(record, dataset_name="longmemeval-s")

    assert case.question_id == "lm-1"
    assert case.question_type == "single-session-user"
    assert case.question == "What degree did I graduate with?"
    assert case.answer == "Business Administration"
    assert case.task_type.value == "open-qa"
    assert case.haystack_session_ids == ["session_1_1", "session_1_2"]
    assert len(case.haystack_session_datetimes) == 2
    assert len(case.haystack_sessions) == 2
    assert case.gold_evidence == ["session_1_2"]
    assert case.metadata["evidence_turn_ids"]


def test_longmemeval_loader_smoke_with_two_examples(tmp_path: Path, monkeypatch) -> None:
    fixture_path = write_longmemeval_fixture(tmp_path / "longmemeval_s_cleaned.json")
    monkeypatch.setenv("WMB_LONGMEMEVAL_S_SOURCE_FILE", str(fixture_path))

    dataset = get_dataset("longmemeval-s").load(limit=2)
    assert dataset.name == "longmemeval-s"
    assert len(dataset.examples) == 2
    assert dataset.examples[0].question_id == "lm-1"


def test_cli_longmemeval_prepare_and_run_smoke(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    fixture_path = write_longmemeval_fixture(tmp_path / "longmemeval_s_cleaned.json")
    monkeypatch.setenv("WMB_HOME", str(tmp_path))
    monkeypatch.setenv("WMB_LONGMEMEVAL_S_SOURCE_FILE", str(fixture_path))

    prepare_result = runner.invoke(app, ["datasets", "prepare", "longmemeval", "--split", "s", "--limit", "2"])
    assert prepare_result.exit_code == 0
    assert "longmemeval-s" in prepare_result.output

    bm25_result = runner.invoke(app, ["run", "--dataset", "longmemeval-s", "--system", "bm25", "--limit", "2"])
    assert bm25_result.exit_code == 0
    assert "Run Complete" in bm25_result.output

    clipwiki_result = runner.invoke(
        app,
        ["run", "--dataset", "longmemeval-s", "--system", "clipwiki", "--mode", "full-wiki", "--limit", "2"],
    )
    assert clipwiki_result.exit_code == 0
    assert "Run Complete" in clipwiki_result.output
