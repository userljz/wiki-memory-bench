from pathlib import Path

from typer.testing import CliRunner

from tests.locomo_fixture import build_locomo_record, write_locomo_fixture
from wiki_memory_bench.datasets import get_dataset
from wiki_memory_bench.datasets.synthetic_wiki_memory import convert_synthetic_case, generate_synthetic_wiki_memory_cases
from wiki_memory_bench.cli import app
from wiki_memory_bench.clipwiki.compiler import compile_clipwiki, extract_speaker_names, retrieve_wiki_pages
from wiki_memory_bench.datasets.locomo_mc10 import convert_locomo_record
from wiki_memory_bench.runner.evaluator import run_benchmark
from wiki_memory_bench.schemas import RetrievedItem
from wiki_memory_bench.systems.answering import DeterministicOpenQAAnswerer
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


def test_concept_pages_do_not_include_raw_question(tmp_path: Path) -> None:
    case = generate_synthetic_wiki_memory_cases(cases=1, seed=42)[0]
    example = convert_synthetic_case(case)
    compiled = compile_clipwiki(example, tmp_path, mode="full-wiki")

    concept_pages = [page for page in compiled.pages if page.page_id.startswith("concepts/")]
    assert concept_pages
    for page in concept_pages:
        assert example.question not in page.content


def test_answerer_ignores_question_metadata_lines() -> None:
    case = generate_synthetic_wiki_memory_cases(cases=1, seed=42)[0]
    example = convert_synthetic_case(case)
    answerer = DeterministicOpenQAAnswerer()
    retrieved_items = [
        RetrievedItem(
            clip_id="sources/source-001-session-1",
            rank=1,
            score=8.0,
            text="\n".join(
                [
                    "# Source source-001-session-1",
                    "",
                    "Question: Which database should the wiki remember as Morgan's default analytics database?",
                    "Tags: source, evidence",
                    "Concept: direct_recall",
                    "Why saved: for debugging",
                    "Summary: Morgan mentioned several tools.",
                    "Source: session-1",
                    "Evidence: metadata field, not an answer snippet.",
                    "",
                    "## Evidence snippets",
                    "- Morgan: My preferred database for analytics is PostgreSQL.",
                    "- Avery: I will remember that PostgreSQL is the default.",
                ]
            ),
        )
    ]

    selection = answerer.answer_question(example, retrieved_items)

    assert selection.answer_text
    assert "postgresql" in selection.answer_text.lower()
    assert not selection.answer_text.startswith(
        ("Question:", "Tags:", "Concept:", "Why saved:", "Summary:", "Source:", "Evidence:")
    )


def test_clipwiki_retrieval_prefers_source_pages(tmp_path: Path) -> None:
    case = generate_synthetic_wiki_memory_cases(cases=1, seed=42)[0]
    example = convert_synthetic_case(case)
    compiled = compile_clipwiki(example, tmp_path, mode="full-wiki")

    retrieved_pages = retrieve_wiki_pages(example.question, compiled, top_k=4)

    assert retrieved_pages
    assert retrieved_pages[0].page_type in {"source", "evidence", "preference"}
    assert any(page.page_type in {"source", "evidence"} for page in retrieved_pages)
    assert all(page.page_type != "concept" for page in retrieved_pages[:1])


def test_clipwiki_direct_recall_retrieval_returns_source_or_evidence_page(tmp_path: Path) -> None:
    case = next(case for case in generate_synthetic_wiki_memory_cases(cases=10, seed=42) if case["task_type"] == "direct_recall")
    example = convert_synthetic_case(case)
    compiled = compile_clipwiki(example, tmp_path, mode="full-wiki")

    retrieved_pages = retrieve_wiki_pages(example.question, compiled, top_k=4)

    assert retrieved_pages
    assert any(page.page_type in {"source", "evidence"} for page in retrieved_pages)


def test_speaker_extraction_supports_bold_markdown_names() -> None:
    assert "Morgan" in extract_speaker_names("**Morgan**: I prefer PostgreSQL for analytics.")
    assert "Morgan" in extract_speaker_names("Morgan: Please remember the office moved to Seattle.")
    assert "Morgan" in extract_speaker_names("[MORGAN] The design review is on 2026-01-13.")


def test_clipwiki_answerable_page_types_are_separated_from_navigation_pages(tmp_path: Path) -> None:
    case = generate_synthetic_wiki_memory_cases(cases=1, seed=42)[0]
    example = convert_synthetic_case(case)
    compiled = compile_clipwiki(example, tmp_path, mode="full-wiki")

    page_by_type = {page.page_type: page for page in compiled.pages}

    assert page_by_type["source"].is_answerable is True
    assert page_by_type["evidence"].is_answerable is True
    assert page_by_type["preference"].is_answerable is True
    assert page_by_type["concept"].is_answerable is False
    assert page_by_type["index"].is_answerable is False
    assert page_by_type["log"].is_answerable is False


def test_clipwiki_synthetic_threshold_20_cases(tmp_path: Path, monkeypatch) -> None:
    out_path = tmp_path / "data" / "synthetic" / "wiki_memory_20.jsonl"
    from wiki_memory_bench.datasets.synthetic_wiki_memory import export_synthetic_wiki_memory

    monkeypatch.setenv("WMB_HOME", str(tmp_path))
    export_synthetic_wiki_memory(cases=20, out_path=out_path, seed=42)
    monkeypatch.setenv("WMB_SYNTHETIC_WIKI_MEMORY_SOURCE_FILE", str(out_path))

    _manifest, summary, results = run_benchmark(
        dataset_name="synthetic-wiki-memory",
        system_name="clipwiki",
        limit=20,
        system_options={"mode": "full-wiki", "answerer": "deterministic"},
    )

    assert summary.accuracy >= 0.4
    assert (summary.citation_precision or 0.0) >= 0.4

    direct_recall_results = [result for result in results if result.question_type == "direct_recall"]
    assert direct_recall_results
    for result in direct_recall_results:
        assert any(item.clip_id.startswith(("sources/", "evidence/")) for item in result.retrieved_items)


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
