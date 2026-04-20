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
