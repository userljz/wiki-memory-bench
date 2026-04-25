from pathlib import Path
import json

from typer.testing import CliRunner

from wiki_memory_bench.cli import app
from wiki_memory_bench.datasets import get_dataset
from wiki_memory_bench.datasets.synthetic_wiki_memory import (
    TASK_TYPES,
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
        assert isinstance(case["stale_source_ids"], list)
        assert isinstance(case["memory_operations"], list)
        assert isinstance(case["memory_operation_labels"], list)
        assert case["memory_operations"] == case["memory_operation_labels"]
        assert case["question_type"] == case["task_type"]
        assert case["generation_template_id"] == f"{case['task_type']}:v2"


def test_all_expected_source_ids_exist_and_stale_sources_do_not_overlap() -> None:
    cases = generate_synthetic_wiki_memory_cases(cases=100, seed=42)
    for case in cases:
        session_ids = {session["session_id"] for session in case["sessions"]}
        assert set(case["expected_source_ids"]).issubset(session_ids)
        assert set(case["stale_source_ids"]).issubset(session_ids)
        assert not (set(case["expected_source_ids"]) & set(case["stale_source_ids"]))


def test_expected_source_ids_are_covered_by_curated_clip_sessions_when_present() -> None:
    cases = generate_synthetic_wiki_memory_cases(cases=100, seed=42)
    for case in cases:
        message_to_session = {
            message["message_id"]: session["session_id"]
            for session in case["sessions"]
            for message in session["messages"]
        }
        curated_session_ids = {
            message_to_session[clip_id]
            for clip_id in case["curated_clips"]
            if clip_id in message_to_session
        }
        expected_source_ids = set(case["expected_source_ids"])

        if not expected_source_ids:
            continue
        assert expected_source_ids.issubset(curated_session_ids), case["case_id"]


def test_curated_clips_are_present_for_non_abstention_tasks() -> None:
    cases = generate_synthetic_wiki_memory_cases(cases=100, seed=42)
    for case in cases:
        if case["task_type"] == "abstention_when_not_in_memory":
            continue
        assert case["curated_clips"], case["case_id"]


def test_every_task_type_appears_in_100_case_generation() -> None:
    cases = generate_synthetic_wiki_memory_cases(cases=100, seed=42)
    task_types = {case["task_type"] for case in cases}

    assert task_types == {
        "direct_recall",
        "update_latest_fact",
        "stale_claim_avoidance",
        "explicit_forgetting",
        "conflicting_sources",
        "multi_source_aggregation",
        "temporal_question",
        "citation_required",
        "abstention_when_not_in_memory",
        "paraphrased_question",
    }


def test_first_ten_cases_are_regression_fixtures_for_each_task_type() -> None:
    cases = generate_synthetic_wiki_memory_cases(cases=10, seed=42)

    assert [case["task_type"] for case in cases] == [
        "direct_recall",
        "update_latest_fact",
        "stale_claim_avoidance",
        "explicit_forgetting",
        "conflicting_sources",
        "multi_source_aggregation",
        "temporal_question",
        "citation_required",
        "abstention_when_not_in_memory",
        "paraphrased_question",
    ]
    assert [case["generation_template_id"] for case in cases] == [f"{case['task_type']}:v2" for case in cases]


def test_some_questions_are_paraphrased_without_answer_keywords() -> None:
    cases = generate_synthetic_wiki_memory_cases(cases=100, seed=42)
    paraphrased_cases = [case for case in cases if case["task_type"] in {"paraphrased_question", "temporal_question"}]

    assert paraphrased_cases
    assert any(str(case["expected_answer"]).lower() not in str(case["question"]).lower() for case in paraphrased_cases)


def test_same_seed_exports_identical_jsonl_and_different_seed_changes_valid_data(tmp_path: Path) -> None:
    first_path = tmp_path / "first.jsonl"
    second_path = tmp_path / "second.jsonl"
    other_path = tmp_path / "other.jsonl"

    export_synthetic_wiki_memory(cases=100, out_path=first_path, seed=42)
    export_synthetic_wiki_memory(cases=100, out_path=second_path, seed=42)
    export_synthetic_wiki_memory(cases=100, out_path=other_path, seed=7)

    first_text = first_path.read_text(encoding="utf-8")
    second_text = second_path.read_text(encoding="utf-8")
    other_text = other_path.read_text(encoding="utf-8")
    assert first_text == second_text
    assert first_text != other_text

    for line in other_text.splitlines():
        case = json.loads(line)
        assert case["task_type"] in set(TASK_TYPES)
        assert case["expected_answer"]
        assert isinstance(case["expected_source_ids"], list)
        assert isinstance(case["memory_operations"], list)


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
