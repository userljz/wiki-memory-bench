import os
from pathlib import Path
import subprocess


def test_reproduce_script_exists_and_is_shell_valid() -> None:
    script_path = Path("scripts/reproduce_v0_1_alpha.sh")
    assert script_path.exists()
    subprocess.run(["bash", "-n", str(script_path)], check=True)


def test_reproduce_script_mentions_required_runs() -> None:
    script_text = Path("scripts/reproduce_v0_1_alpha.sh").read_text(encoding="utf-8")

    assert "synthetic-mini" in script_text
    assert "synthetic-wiki-memory" in script_text
    assert "locomo-mc10" in script_text
    assert "vector-rag" in script_text
    assert "clipwiki" in script_text
    assert "reports/v0.1-alpha-results.md" in script_text


def test_reproduce_script_smoke_executes(tmp_path: Path) -> None:
    script_path = Path("scripts/reproduce_v0_1_alpha.sh")
    report_dir = tmp_path / "reports"
    synthetic_out = tmp_path / "data" / "synthetic" / "wiki_memory_20.jsonl"
    env = {
        **os.environ,
        "WMB_HOME": str(tmp_path / "wmb-home"),
        "WMB_REPORT_DIR": str(report_dir),
        "WMB_SYNTHETIC_OUT": str(synthetic_out),
        "WMB_SMOKE_ONLY": "1",
    }

    result = subprocess.run(
        ["bash", str(script_path)],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert synthetic_out.exists()
    report_path = report_dir / "v0.1-alpha-results.md"
    assert report_path.exists()
    report_text = report_path.read_text(encoding="utf-8")
    assert "synthetic-mini" in report_text
    assert "bm25" in report_text


def test_alpha_report_includes_commit_hash_and_exact_commands() -> None:
    report_text = Path("reports/v0.1-alpha-results.md").read_text(encoding="utf-8")

    assert "git commit:" in report_text
    assert "## Exact Commands" in report_text
    assert "uv run wmb run --dataset synthetic-mini --system bm25 --limit 5" in report_text


def test_alpha_report_marks_oracle_systems_and_keeps_weak_rows_visible() -> None:
    report_text = Path("reports/v0.1-alpha-results.md").read_text(encoding="utf-8")

    assert "full-context-oracle" in report_text
    assert "## Oracle / Non-Oracle Explanation" in report_text
    assert "| locomo-mc10 | bm25 |" in report_text
    assert "| locomo-mc10 | clipwiki |" in report_text
    assert "Poor-performing rows are intentionally retained." in report_text
