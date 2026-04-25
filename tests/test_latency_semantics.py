from __future__ import annotations

from pathlib import Path
import time

import numpy as np
import pytest

from wiki_memory_bench.datasets import get_dataset
from wiki_memory_bench.schemas import PreparedExample
from wiki_memory_bench.systems.answering import AnswerSelection
from wiki_memory_bench.systems.basic_memory import BasicMemoryAdapter
from wiki_memory_bench.systems.bm25 import BM25Baseline
from wiki_memory_bench.systems.clipwiki import ClipWikiBaseline
from wiki_memory_bench.systems.full_context import FullContextHeuristicBaseline
from wiki_memory_bench.systems.vector_rag import VectorRAGBaseline


SLEEP_SECONDS = 0.05
MIN_EXPECTED_LATENCY_MS = 40.0


class SlowChoiceAnswerer:
    def select_choice(self, example: PreparedExample, retrieved_items):  # type: ignore[no-untyped-def]
        time.sleep(SLEEP_SECONDS)
        supporting_item = retrieved_items[0] if retrieved_items else None
        return AnswerSelection(
            choice=example.choices[example.correct_choice_index],
            supporting_item=supporting_item,
            confidence=1.0,
            citation_ids=[supporting_item.clip_id] if supporting_item is not None else [],
        )


class FakeEmbedder:
    model_name = "fake"

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        rows = []
        for text in texts:
            lowered = text.lower()
            vector = np.array(
                [
                    float("postgresql" in lowered),
                    float("seattle" in lowered),
                    float(len(lowered.split()) + 1),
                ],
                dtype=float,
            )
            norm = np.linalg.norm(vector)
            rows.append(vector / norm if norm else vector)
        return np.vstack(rows)


@pytest.fixture
def example() -> PreparedExample:
    return get_dataset("synthetic-mini").load(limit=1).examples[0]


def _assert_answerer_latency_included(latency_ms: float) -> None:
    assert latency_ms >= MIN_EXPECTED_LATENCY_MS


def test_bm25_latency_includes_answerer_time(example: PreparedExample) -> None:
    system = BM25Baseline()
    system.answerer = SlowChoiceAnswerer()

    prediction = system.run(example)

    _assert_answerer_latency_included(prediction.latency_ms)


def test_vector_rag_latency_includes_answerer_time(example: PreparedExample) -> None:
    system = VectorRAGBaseline(embedder=FakeEmbedder(), model_name="fake-model")
    system.answerer = SlowChoiceAnswerer()

    prediction = system.run(example)

    _assert_answerer_latency_included(prediction.latency_ms)


def test_clipwiki_latency_includes_answerer_time(tmp_path: Path, example: PreparedExample) -> None:
    system = ClipWikiBaseline(mode="full-wiki")
    system.answerer = SlowChoiceAnswerer()
    system.prepare_run(tmp_path / "run", "synthetic-mini")

    prediction = system.run(example)

    _assert_answerer_latency_included(prediction.latency_ms)


def test_full_context_latency_includes_answerer_time(example: PreparedExample) -> None:
    system = FullContextHeuristicBaseline()
    system.answerer_mode = "llm"
    system.answerer = SlowChoiceAnswerer()

    prediction = system.run(example)

    _assert_answerer_latency_included(prediction.latency_ms)


def test_basic_memory_latency_includes_answerer_time(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, example: PreparedExample) -> None:
    monkeypatch.setattr("wiki_memory_bench.systems.basic_memory.shutil.which", lambda command: None)
    system = BasicMemoryAdapter()
    system.answerer = SlowChoiceAnswerer()
    system.prepare_run(tmp_path / "run", "synthetic-mini")

    prediction = system.run(example)

    _assert_answerer_latency_included(prediction.latency_ms)
