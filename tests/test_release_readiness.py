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


def test_readme_alpha_rows_and_vector_rag_status_match_alpha_report() -> None:
    report_text = Path("reports/v0.1-alpha-results.md").read_text(encoding="utf-8")
    readme_text = Path("README.md").read_text(encoding="utf-8")
    readme_cn_text = Path("README-CN.md").read_text(encoding="utf-8")

    _, report_rows = _extract_markdown_table_after_heading(report_text, "## Result Table")
    _, readme_rows = _extract_markdown_table_after_heading(readme_text, "## v0.1-alpha Results")
    _, readme_cn_rows = _extract_markdown_table_after_heading(readme_cn_text, "## v0.1-alpha 结果快照")

    report_projection = _project_alpha_rows(
        report_rows,
        {
            "dataset": "Dataset",
            "system": "System",
            "mode": "Mode",
            "status": "Status",
            "uses_gold_labels": "Uses Gold Labels",
            "dependency_mode": "Dependency Mode",
            "accuracy": "Accuracy",
            "citation_precision": "Citation Precision",
        },
    )
    readme_projection = _project_alpha_rows(
        readme_rows,
        {
            "dataset": "Dataset",
            "system": "System",
            "mode": "Mode",
            "status": "Status",
            "uses_gold_labels": "Uses Gold Labels",
            "dependency_mode": "Dependency Mode",
            "accuracy": "Accuracy",
            "citation_precision": "Citation Precision",
        },
    )
    readme_cn_projection = _project_alpha_rows(
        readme_cn_rows,
        {
            "dataset": "数据集",
            "system": "系统",
            "mode": "Mode",
            "status": "Status",
            "uses_gold_labels": "Uses Gold Labels",
            "dependency_mode": "Dependency Mode",
            "accuracy": "Accuracy",
            "citation_precision": "Citation Precision",
        },
    )

    assert readme_projection == report_projection
    assert readme_cn_projection == report_projection


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
