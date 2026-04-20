from __future__ import annotations

import os
from pathlib import Path
import subprocess
import textwrap

from tests.locomo_fixture import write_locomo_fixture


def _script_path() -> Path:
    return Path("scripts/reproduce_llm_smoke.sh")


def _base_env(tmp_path: Path) -> dict[str, str]:
    report_dir = tmp_path / "reports"
    wmb_home = tmp_path / "wmb-home"
    locomo_fixture = write_locomo_fixture(tmp_path / "locomo_mc10.json")
    return {
        **os.environ,
        "WMB_HOME": str(wmb_home),
        "WMB_REPORT_DIR": str(report_dir),
        "WMB_LLM_REPORT_FILE": str(report_dir / "llm-smoke-results.md"),
        "WMB_LLM_RESULTS_JSONL": str(report_dir / ".llm_smoke_results.jsonl"),
        "WMB_LLM_RUN_IDS_FILE": str(report_dir / "llm-smoke-run-ids.txt"),
        "WMB_LOCOMO_MC10_SOURCE_FILE": str(locomo_fixture),
        "WMB_LLM_LIMIT": "2",
    }


def _fake_runtime_hook_dir(tmp_path: Path) -> Path:
    hook_dir = tmp_path / "fake-runtime-hook"
    hook_dir.mkdir(parents=True, exist_ok=True)
    (hook_dir / "sitecustomize.py").write_text(
        textwrap.dedent(
            """
            import importlib.machinery
            import json
            import sys
            import types

            import numpy as np

            if os.environ.get("WMB_FAKE_LITELLM") == "1":
                fake_litellm = types.ModuleType("litellm")
                fake_litellm.__spec__ = importlib.machinery.ModuleSpec("litellm", loader=None)

                class _FakeMessage:
                    def __init__(self, content: str) -> None:
                        self.content = content

                class _FakeChoice:
                    def __init__(self, content: str) -> None:
                        self.message = _FakeMessage(content)

                class _FakeUsage:
                    def __init__(self) -> None:
                        self.prompt_tokens = 11
                        self.completion_tokens = 7

                class _FakeResponse:
                    def __init__(self, content: str) -> None:
                        self.choices = [_FakeChoice(content)]
                        self.usage = _FakeUsage()

                def _first_chunk_id(prompt: str) -> str:
                    for line in prompt.splitlines():
                        if line.startswith("Chunk ID: "):
                            return line.split("Chunk ID: ", 1)[1].strip()
                    return "chunk-0"

                def completion(*, messages, **kwargs):
                    prompt = messages[0]["content"]
                    chunk_id = _first_chunk_id(prompt)
                    if '"answer": str' in prompt:
                        payload = {
                            "answer": "stub answer",
                            "rationale": "Fake open-QA response for smoke testing.",
                            "citations": [chunk_id],
                        }
                    else:
                        payload = {
                            "choice_index": 0,
                            "choice_text": "choice-0",
                            "rationale": "Fake multiple-choice response for smoke testing.",
                            "citations": [chunk_id],
                        }
                    return _FakeResponse(json.dumps(payload))

                def completion_cost(*args, **kwargs):
                    return 0.001

                fake_litellm.completion = completion
                fake_litellm.completion_cost = completion_cost
                sys.modules["litellm"] = fake_litellm

                fake_sentence_transformers = types.ModuleType("sentence_transformers")
                fake_sentence_transformers.__spec__ = importlib.machinery.ModuleSpec("sentence_transformers", loader=None)

                class SentenceTransformer:
                    def __init__(self, *args, **kwargs) -> None:
                        pass

                    def encode(self, texts, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False):
                        rows = []
                        for text in texts:
                            lowered = text.lower()
                            vector = np.array(
                                [
                                    float(sum(ord(char) for char in lowered) % 101 + 1),
                                    float(len(lowered.split()) + 1),
                                    float(lowered.count("aurora") + 1),
                                    float(lowered.count("seattle") + 1),
                                ],
                                dtype=float,
                            )
                            if normalize_embeddings:
                                norm = np.linalg.norm(vector)
                                if norm:
                                    vector = vector / norm
                            rows.append(vector)
                        return np.vstack(rows)

                fake_sentence_transformers.SentenceTransformer = SentenceTransformer
                sys.modules["sentence_transformers"] = fake_sentence_transformers
            """
        ).replace("import numpy as np", "import os\nimport numpy as np"),
        encoding="utf-8",
    )
    return hook_dir


def _run_script(tmp_path: Path, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = _base_env(tmp_path)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(_script_path())],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def test_llm_smoke_script_requires_integration_opt_in(tmp_path: Path) -> None:
    result = _run_script(
        tmp_path,
        {
            "LLM_MODEL": "fake-model",
            "LLM_API_KEY": "fake-key",
        },
    )

    assert result.returncode != 0
    assert "WMB_RUN_LLM_INTEGRATION=1" in (result.stderr or result.stdout)


def test_llm_smoke_script_requires_llm_model(tmp_path: Path) -> None:
    result = _run_script(
        tmp_path,
        {
            "WMB_RUN_LLM_INTEGRATION": "1",
            "LLM_API_KEY": "fake-key",
        },
    )

    assert result.returncode != 0
    assert "LLM_MODEL is required" in (result.stderr or result.stdout)


def test_llm_smoke_script_requires_api_key_unless_allowed(tmp_path: Path) -> None:
    result = _run_script(
        tmp_path,
        {
            "WMB_RUN_LLM_INTEGRATION": "1",
            "LLM_MODEL": "fake-model",
        },
    )

    assert result.returncode != 0
    assert "LLM_API_KEY is required" in (result.stderr or result.stdout)


def test_llm_smoke_script_mocked_path_writes_report_and_artifacts(tmp_path: Path) -> None:
    hook_dir = _fake_runtime_hook_dir(tmp_path)
    result = _run_script(
        tmp_path,
        {
            "WMB_RUN_LLM_INTEGRATION": "1",
            "LLM_MODEL": "fake-model",
            "WMB_ALLOW_MISSING_LLM_API_KEY": "1",
            "WMB_FAKE_LITELLM": "1",
            "PYTHONPATH": f"{hook_dir}:{os.environ.get('PYTHONPATH', '')}".rstrip(":"),
        },
    )

    assert result.returncode == 0, result.stderr or result.stdout

    report_path = tmp_path / "reports" / "llm-smoke-results.md"
    assert report_path.exists()
    report_text = report_path.read_text(encoding="utf-8")
    assert "fake-model" in report_text
    assert "LLM Smoke Results" in report_text
    assert "Answerer Mode" in report_text
    assert "Judge Mode" in report_text
    assert "Prompt Artifact Path" in report_text
    assert "Avg Cost" in report_text

    artifact_files = sorted((tmp_path / "wmb-home" / "runs").rglob("artifacts/llm/answerer/*.json"))
    assert artifact_files
    artifact_payload = artifact_files[0].read_text(encoding="utf-8")
    assert "\"prompt\"" in artifact_payload
    assert "\"parsed_response\"" in artifact_payload
