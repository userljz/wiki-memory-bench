from pathlib import Path

from typer.testing import CliRunner

from tests.locomo_fixture import build_locomo_record, write_locomo_fixture
from wiki_memory_bench.datasets import get_dataset
from wiki_memory_bench.datasets.synthetic_wiki_memory import convert_synthetic_case, generate_synthetic_wiki_memory_cases
from wiki_memory_bench.cli import app
from wiki_memory_bench.clipwiki.compiler import compile_clipwiki
from wiki_memory_bench.datasets.locomo_mc10 import convert_locomo_record
from wiki_memory_bench.systems.clipwiki import ClipWikiBaseline


def test_compile_clipwiki_writes_index_log_and_sources(tmp_path: Path) -> None:
    example = convert_locomo_record(build_locomo_record(1, "single_hop", "Which project codename is active?", "Aurora"))
    compiled = compile_clipwiki(example, tmp_path, mode="full-wiki")

    assert compiled.wiki_size_pages >= 4
    assert (tmp_path / "index.md").exists()
    assert (tmp_path / "log.md").exists()
    assert (tmp_path / "sources" / "session_1.md").exists()


def test_clipwiki_baseline_returns_citations_and_wiki_metrics(tmp_path: Path) -> None:
    example = convert_locomo_record(build_locomo_record(2, "multi_hop", "Which city is the current office in?", "Seattle"))
    system = ClipWikiBaseline(mode="full-wiki")
    run_dir = tmp_path / "run-dir"
    run_dir.mkdir(parents=True, exist_ok=True)
    system.prepare_run(run_dir, "locomo-mc10")

    prediction = system.run(example)

    assert prediction.citations
    assert prediction.wiki_size_pages is not None and prediction.wiki_size_pages > 0
    assert prediction.wiki_size_tokens is not None and prediction.wiki_size_tokens > 0
    assert prediction.retrieved_items
    assert "artifacts/wiki" in prediction.metadata["wiki_dir"]


def test_clipwiki_oracle_curated_uses_session_level_gold_evidence_for_synthetic_mini(tmp_path: Path) -> None:
    example = get_dataset("synthetic-mini").load().examples[1]
    compiled = compile_clipwiki(example, tmp_path, mode="oracle-curated")

    assert compiled.selected_session_ids == ["session-2"]


def test_clipwiki_curated_mode_uses_curated_clips_metadata(tmp_path: Path) -> None:
    case = generate_synthetic_wiki_memory_cases(cases=1, seed=42)[0]
    example = convert_synthetic_case(case)
    compiled = compile_clipwiki(example, tmp_path, mode="curated")

    expected_sessions = {
        session["session_id"]
        for session in case["sessions"]
        if any(message["message_id"] in set(case["curated_clips"]) for message in session["messages"])
    }
    assert set(compiled.selected_session_ids) == expected_sessions


def test_cli_clipwiki_smoke(tmp_path: Path) -> None:
    runner = CliRunner()
    fixture_path = write_locomo_fixture(tmp_path / "locomo_mc10.json")
    env = {
        "WMB_HOME": str(tmp_path),
        "WMB_LOCOMO_MC10_SOURCE_FILE": str(fixture_path),
    }

    prepare_result = runner.invoke(app, ["datasets", "prepare", "locomo-mc10", "--limit", "5"], env=env)
    assert prepare_result.exit_code == 0

    run_result = runner.invoke(
        app,
        ["run", "--dataset", "locomo-mc10", "--system", "clipwiki", "--mode", "full-wiki", "--limit", "5"],
        env=env,
    )
    assert run_result.exit_code == 0
    assert "Run Complete" in run_result.output
    assert "Citation precision" in run_result.output

    wiki_root = tmp_path / "runs" / "latest" / "artifacts" / "wiki"
    assert wiki_root.exists()
    example_dirs = [path for path in wiki_root.iterdir() if path.is_dir()]
    assert example_dirs
    assert (example_dirs[0] / "index.md").exists()
    assert (example_dirs[0] / "log.md").exists()
