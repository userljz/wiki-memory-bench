from __future__ import annotations

import re
import subprocess
import sys
import textwrap
from pathlib import Path


def _extract_markdown_table_after_heading(text: str, heading: str) -> tuple[list[str], list[dict[str, str]]]:
    lines = text.splitlines()
    try:
        heading_index = lines.index(heading)
    except ValueError as exc:
        raise AssertionError(f"Missing heading: {heading}") from exc

    table_lines: list[str] = []
    in_table = False
    for line in lines[heading_index + 1 :]:
        if line.startswith("|"):
            table_lines.append(line)
            in_table = True
            continue
        if in_table:
            break

    assert len(table_lines) >= 3, f"Expected markdown table after {heading}"

    header_line, separator_line, *data_lines = table_lines
    assert header_line.startswith("|") and header_line.endswith("|")
    assert separator_line.startswith("|") and separator_line.endswith("|")

    header_cells = [cell.strip() for cell in header_line.strip("|").split("|")]
    separator_cells = [cell.strip() for cell in separator_line.strip("|").split("|")]
    assert len(header_cells) == len(separator_cells)
    assert all(re.fullmatch(r":?-{3,}:?", cell) for cell in separator_cells)

    rows: list[dict[str, str]] = []
    for line in data_lines:
        assert line.startswith("|") and line.endswith("|")
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        assert len(cells) == len(header_cells)
        rows.append(dict(zip(header_cells, cells)))

    return table_lines, rows


def _project_alpha_rows(rows: list[dict[str, str]], mapping: dict[str, str]) -> set[tuple[str, ...]]:
    def clean(value: str) -> str:
        value = value.strip()
        if value.startswith("`") and value.endswith("`") and len(value) >= 2:
            return value[1:-1]
        return value

    return {
        (
            clean(row[mapping["dataset"]]),
            clean(row[mapping["system"]]),
            clean(row[mapping["mode"]]),
            clean(row[mapping["status"]]),
            clean(row[mapping["uses_gold_labels"]]),
            clean(row[mapping["dependency_mode"]]),
            clean(row[mapping["accuracy"]]),
            clean(row[mapping["citation_precision"]]),
        )
        for row in rows
    }


def test_license_file_exists_and_is_mit() -> None:
    license_path = Path("LICENSE")
    assert license_path.exists()
    assert "MIT License" in license_path.read_text(encoding="utf-8")


def test_release_docs_do_not_claim_license_is_unfinalized() -> None:
    readme_text = Path("README.md").read_text(encoding="utf-8")
    readme_cn_text = Path("README-CN.md").read_text(encoding="utf-8")
    acknowledgements_text = Path("ACKNOWLEDGEMENTS.md").read_text(encoding="utf-8")

    assert "does not yet include a finalized project license file" not in readme_text.lower()
    assert "当前仓库还没有最终确定的根级 `license` 文件。" not in readme_cn_text.lower()
    assert "not finalized" not in acknowledgements_text.lower()
    assert "MIT License" in readme_text
    assert "MIT License" in readme_cn_text


def test_ci_workflow_exists() -> None:
    assert Path(".github/workflows/ci.yml").exists()


def test_readme_alpha_result_tables_use_valid_markdown_syntax() -> None:
    readme_text = Path("README.md").read_text(encoding="utf-8")
    readme_cn_text = Path("README-CN.md").read_text(encoding="utf-8")

    _extract_markdown_table_after_heading(readme_text, "## v0.1-alpha Results")
    _extract_markdown_table_after_heading(readme_cn_text, "## v0.1-alpha 结果快照")


def test_readme_links_alpha_reports_and_keeps_claims_conservative() -> None:
    report_text = Path("reports/v0.1-alpha-results.md").read_text(encoding="utf-8")
    readme_text = Path("README.md").read_text(encoding="utf-8")
    readme_cn_text = Path("README-CN.md").read_text(encoding="utf-8")

    assert "reports/v0.1-alpha-results.md" in readme_text
    assert "reports/public-benchmark-alpha.md" in readme_text
    assert "reports/llm-smoke-results.md" in readme_text
    assert "No result in this release claims" in readme_text
    assert "SOTA" in readme_text
    assert "Weak public alpha rows remain visible" in report_text or "weak alpha row" in report_text
    assert "reports/v0.1-alpha-results.md" in readme_cn_text


def test_package_and_cli_import_without_optional_dependencies() -> None:
    script = textwrap.dedent(
        """
        import builtins
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path.cwd() / "src"))

        blocked = {"litellm": 0, "sentence_transformers": 0}
        original_import = builtins.__import__

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "litellm" or name.startswith("litellm."):
                blocked["litellm"] += 1
                raise ModuleNotFoundError("blocked litellm import")
            if name == "sentence_transformers" or name.startswith("sentence_transformers."):
                blocked["sentence_transformers"] += 1
                raise ModuleNotFoundError("blocked sentence_transformers import")
            return original_import(name, globals, locals, fromlist, level)

        builtins.__import__ = guarded_import

        import wiki_memory_bench
        import wiki_memory_bench.cli

        assert wiki_memory_bench.__version__
        assert "litellm" not in sys.modules
        assert "sentence_transformers" not in sys.modules
        print(blocked)
        """
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
