from __future__ import annotations

from pathlib import Path

import numpy as np
from typer.testing import CliRunner

from tests.locomo_fixture import write_locomo_fixture
from wiki_memory_bench.cli import app
from wiki_memory_bench.datasets.locomo_mc10 import convert_locomo_record
from wiki_memory_bench.systems.retrieval import InMemoryEmbeddingIndex
from wiki_memory_bench.systems.vector_rag import VectorRAGBaseline


class FakeEmbedder:
    def __init__(self, model_name: str = "fake", cache_folder: str | None = None) -> None:
        self.model_name = model_name
        self.cache_folder = cache_folder
        self.calls = 0

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        self.calls += 1
        embeddings = [self._vectorize(text) for text in texts]
        return np.vstack(embeddings)

    def _vectorize(self, text: str) -> np.ndarray:
        normalized = text.lower()
        vector = np.array(
            [
                2.0 if "aurora" in normalized else 0.0,
                2.0 if "seattle" in normalized else 0.0,
                2.0 if "postgresql" in normalized else 0.0,
                2.0 if "2026-04-21" in normalized else 0.0,
                1.0 if "project" in normalized or "codename" in normalized else 0.0,
                1.0 if "office" in normalized else 0.0,
                1.0 if "database" in normalized else 0.0,
                1.0 if "review" in normalized or "architecture" in normalized else 0.0,
                1.0 if "not answerable" in normalized or "not enough information" in normalized else 0.0,
                max(1, len(normalized.split())) / 100.0,
            ],
            dtype=float,
        )
        norm = np.linalg.norm(vector)
        if norm == 0:
            return vector
        return vector / norm


def test_embedding_index_caches_repeated_texts() -> None:
    embedder = FakeEmbedder()
    index = InMemoryEmbeddingIndex(embedder)

    first = index.embed_texts(["Aurora", "Aurora", "Seattle"])
    second = index.embed_texts(["Aurora", "Seattle"])

    assert first.shape[0] == 3
    assert second.shape[0] == 2
    assert embedder.calls == 1
    assert index.cache_size == 2


def test_vector_rag_retrieves_relevant_chunk_and_answers() -> None:
    record = {
        "question_id": "conv-1_q1",
        "question_type": "single_hop",
        "question": "Which project codename is active?",
        "choices": [
            "Aurora",
            "Seattle",
            "PostgreSQL",
            "Not answerable",
            "wrong-4",
            "wrong-5",
            "wrong-6",
            "wrong-7",
            "wrong-8",
            "wrong-9",
        ],
        "correct_choice_index": 0,
        "answer": "Aurora",
        "haystack_sessions": [
            [
                {"role": "user", "content": "Let's talk about planning."},
                {"role": "assistant", "content": "The active project codename is Aurora."},
            ]
        ],
        "haystack_session_ids": ["session_1"],
        "haystack_session_summaries": ["Session summary: the active project codename is Aurora."],
        "haystack_session_datetimes": ["2023-05-08T13:56:00"],
        "num_choices": 10,
        "num_sessions": 1,
    }
    example = convert_locomo_record(record)
    system = VectorRAGBaseline(embedder=FakeEmbedder(), model_name="fake-model", top_k=2)

    prediction = system.run(example)

    assert prediction.selected_choice_text == "Aurora"
    assert prediction.selected_choice_index == 0
    assert prediction.retrieved_items
    assert "Aurora" in prediction.retrieved_items[0].text


def test_cli_vector_rag_smoke(tmp_path: Path, monkeypatch) -> None:
    fixture_path = write_locomo_fixture(tmp_path / "locomo_mc10.json")
    runner = CliRunner()

    import wiki_memory_bench.systems.vector_rag as vector_rag_module

    monkeypatch.setattr(vector_rag_module, "SentenceTransformerEmbedder", FakeEmbedder)
    env = {
        "WMB_HOME": str(tmp_path),
        "WMB_LOCOMO_MC10_SOURCE_FILE": str(fixture_path),
    }

    prepare_result = runner.invoke(app, ["datasets", "prepare", "locomo-mc10", "--limit", "5"], env=env)
    assert prepare_result.exit_code == 0

    run_result = runner.invoke(
        app,
        ["run", "--dataset", "locomo-mc10", "--system", "vector-rag", "--limit", "5"],
        env=env,
    )
    assert run_result.exit_code == 0
    assert "Run Complete" in run_result.output
    assert "Retrieval top-k" in run_result.output
