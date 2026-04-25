from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from wiki_memory_bench.datasets import get_dataset
from wiki_memory_bench.runner.evaluator import run_benchmark
from wiki_memory_bench.systems import get_system
from wiki_memory_bench.systems.basic_memory import BasicMemoryAdapter
from wiki_memory_bench.systems.clipwiki import ClipWikiBaseline
from wiki_memory_bench.systems.vector_rag import VectorRAGBaseline


class FakeEmbedder:
    model_name = "fake"

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        return np.vstack([self._vectorize(text) for text in texts])

    def _vectorize(self, text: str) -> np.ndarray:
        lowered = text.lower()
        vector = np.array(
            [
                1.0 if "postgresql" in lowered else 0.0,
                1.0 if "seattle" in lowered else 0.0,
                1.0 if "aurora" in lowered else 0.0,
                max(1, len(lowered.split())) / 100.0,
            ],
            dtype=float,
        )
        norm = np.linalg.norm(vector)
        return vector if norm == 0 else vector / norm


def _assert_fairness_metadata(metadata: dict[str, object], *, expected_oracle: bool) -> None:
    assert isinstance(metadata["uses_gold_labels"], bool)
    assert isinstance(metadata["oracle_mode"], bool)
    assert isinstance(metadata["oracle_label"], str)
    assert isinstance(metadata["gold_label_fields_used"], list)
    assert metadata["uses_gold_labels"] is expected_oracle
    assert metadata["oracle_mode"] is expected_oracle
    assert metadata["oracle_label"] == ("oracle-upper-bound" if expected_oracle else "non-oracle")
    assert bool(metadata["gold_label_fields_used"]) is expected_oracle


@pytest.mark.parametrize(
    ("case_name", "expected_oracle"),
    [
        ("bm25", False),
        ("vector-rag", False),
        ("basic-memory", False),
        ("clipwiki-full-wiki", False),
        ("clipwiki-curated", False),
        ("clipwiki-noisy-curated", False),
        ("clipwiki-oracle-curated", True),
        ("full-context-heuristic", False),
        ("full-context-oracle", True),
    ],
)
def test_system_result_fairness_metadata_fields_exist(
    case_name: str,
    expected_oracle: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("wiki_memory_bench.systems.basic_memory.shutil.which", lambda command: None)
    example = get_dataset("synthetic-mini").load().examples[1]
    system = _build_system(case_name)
    run_dir = tmp_path / case_name
    run_dir.mkdir()
    system.prepare_run(run_dir, "synthetic-mini")

    prediction = system.run(example)

    _assert_fairness_metadata(prediction.metadata, expected_oracle=expected_oracle)


def test_oracle_named_systems_must_report_gold_usage(tmp_path: Path) -> None:
    example = get_dataset("synthetic-mini").load().examples[0]
    system = get_system("full-context-oracle")
    system.prepare_run(tmp_path / "run", "synthetic-mini")

    prediction = system.run(example)

    assert "oracle" in prediction.system_name
    assert prediction.metadata["uses_gold_labels"] is True
    assert prediction.metadata["oracle_mode"] is True


@pytest.mark.parametrize(
    ("system_name", "system_options", "expected_oracle"),
    [
        ("bm25", None, False),
        ("full-context-heuristic", None, False),
        ("full-context-oracle", None, True),
        ("clipwiki", {"mode": "full-wiki"}, False),
        ("clipwiki", {"mode": "curated"}, False),
        ("clipwiki", {"mode": "noisy-curated"}, False),
        ("clipwiki", {"mode": "oracle-curated"}, True),
    ],
)
def test_runner_summary_aggregates_fairness_metadata(
    system_name: str,
    system_options: dict[str, object] | None,
    expected_oracle: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WMB_HOME", str(tmp_path))
    _, summary, _ = run_benchmark(
        dataset_name="synthetic-mini",
        system_name=system_name,
        limit=2,
        system_options=system_options,
    )

    assert summary.uses_gold_labels is expected_oracle
    assert summary.oracle_mode is expected_oracle
    assert summary.oracle_label == ("oracle-upper-bound" if expected_oracle else "non-oracle")


def _build_system(case_name: str):
    if case_name == "vector-rag":
        return VectorRAGBaseline(embedder=FakeEmbedder(), model_name="fake-model", top_k=2)
    if case_name == "basic-memory":
        return BasicMemoryAdapter()
    if case_name.startswith("clipwiki-"):
        mode = case_name.removeprefix("clipwiki-")
        return ClipWikiBaseline(mode=mode)
    return get_system(case_name)
