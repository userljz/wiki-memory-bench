import os
from pathlib import Path
import subprocess
import shutil


def _clone_repo(tmp_path: Path) -> Path:
    repo_copy = tmp_path / "repo"
    shutil.copytree(Path.cwd(), repo_copy, ignore=shutil.ignore_patterns(".git", ".venv", ".pytest_cache", "__pycache__"))
    subprocess.run(["git", "init", "-q"], cwd=repo_copy, check=True)
    subprocess.run(["git", "add", "."], cwd=repo_copy, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test User",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-q",
            "-m",
            "snapshot",
        ],
        cwd=repo_copy,
        check=True,
    )
    return repo_copy


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
    repo_copy = _clone_repo(tmp_path)
    script_path = repo_copy / "scripts" / "reproduce_v0_1_alpha.sh"
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
        cwd=repo_copy,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert synthetic_out.exists()
    report_path = report_dir / "v0.1-alpha-results.md"
    assert report_path.exists()
    report_text = report_path.read_text(encoding="utf-8")
    assert "synthetic-mini" in report_text
    assert "bm25" in report_text


def test_reproduce_script_fails_on_dirty_tree_unless_override_set(tmp_path: Path) -> None:
    repo_copy = _clone_repo(tmp_path)
    script_path = repo_copy / "scripts" / "reproduce_v0_1_alpha.sh"
    dirty_file = repo_copy / "README.md"
    dirty_file.write_text(dirty_file.read_text(encoding="utf-8") + "\n<!-- dirty -->\n", encoding="utf-8")

    fail_result = subprocess.run(
        ["bash", str(script_path)],
        capture_output=True,
        text=True,
        check=False,
        cwd=repo_copy,
        env={
            **os.environ,
            "WMB_HOME": str(tmp_path / "dirty-home"),
            "WMB_REPORT_DIR": str(tmp_path / "dirty-reports"),
            "WMB_SYNTHETIC_OUT": str(tmp_path / "dirty-data" / "wiki_memory_20.jsonl"),
            "WMB_SMOKE_ONLY": "1",
        },
    )

    assert fail_result.returncode != 0
    assert "Refusing to generate public report from dirty working tree." in (fail_result.stderr or fail_result.stdout)

    pass_result = subprocess.run(
        ["bash", str(script_path)],
        capture_output=True,
        text=True,
        check=False,
        cwd=repo_copy,
        env={
            **os.environ,
            "WMB_HOME": str(tmp_path / "dirty-home-override"),
            "WMB_REPORT_DIR": str(tmp_path / "dirty-reports-override"),
            "WMB_SYNTHETIC_OUT": str(tmp_path / "dirty-data-override" / "wiki_memory_20.jsonl"),
            "WMB_SMOKE_ONLY": "1",
            "WMB_ALLOW_DIRTY_REPORT": "1",
        },
    )

    assert pass_result.returncode == 0, pass_result.stderr or pass_result.stdout
    report_text = (tmp_path / "dirty-reports-override" / "v0.1-alpha-results.md").read_text(encoding="utf-8")
    assert "Git Status Summary: dirty" in report_text
    assert "requires the same commit plus the local diff shown below" in report_text


def test_alpha_report_includes_commit_hash_and_exact_commands() -> None:
    report_text = Path("reports/v0.1-alpha-results.md").read_text(encoding="utf-8")

    assert "git commit:" in report_text
    assert "Git Status Summary: clean" in report_text
    assert "## Exact Commands" in report_text
    assert "uv run wmb run --dataset synthetic-mini --system bm25 --limit 5" in report_text


def test_smoke_generated_alpha_report_commit_hash_matches_current_head(tmp_path: Path) -> None:
    repo_copy = _clone_repo(tmp_path)
    script_path = repo_copy / "scripts" / "reproduce_v0_1_alpha.sh"
    report_dir = tmp_path / "reports-commit-check"
    synthetic_out = tmp_path / "data-commit-check" / "wiki_memory_20.jsonl"
    head_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_copy,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    result = subprocess.run(
        ["bash", str(script_path)],
        capture_output=True,
        text=True,
        check=False,
        cwd=repo_copy,
        env={
            **os.environ,
            "WMB_HOME": str(tmp_path / "wmb-home-commit-check"),
            "WMB_REPORT_DIR": str(report_dir),
            "WMB_SYNTHETIC_OUT": str(synthetic_out),
            "WMB_SMOKE_ONLY": "1",
        },
    )

    assert result.returncode == 0, result.stderr or result.stdout
    report_text = (report_dir / "v0.1-alpha-results.md").read_text(encoding="utf-8")
    assert head_sha in report_text


def test_alpha_report_marks_oracle_systems_and_keeps_weak_rows_visible() -> None:
    report_text = Path("reports/v0.1-alpha-results.md").read_text(encoding="utf-8")

    assert "full-context-oracle" in report_text
    assert "## Oracle / Non-Oracle Explanation" in report_text
    assert "| locomo-mc10 | bm25 |" in report_text
    assert "| locomo-mc10 | clipwiki |" in report_text
    assert "Poor-performing rows are intentionally retained." in report_text
