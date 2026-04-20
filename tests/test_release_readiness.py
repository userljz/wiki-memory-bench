from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path


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
