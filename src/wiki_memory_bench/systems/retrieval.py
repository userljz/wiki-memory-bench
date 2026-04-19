"""Shared retrieval helpers for baseline systems."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

import numpy as np

from wiki_memory_bench.schemas import HistoryClip, PreparedExample


class TextEmbedder(Protocol):
    """Minimal protocol for text embedding backends."""

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        """Embed a batch of texts into a 2D numpy array."""


class SentenceTransformerEmbedder:
    """Lazy sentence-transformers wrapper with normalized embeddings."""

    def __init__(self, model_name: str, cache_folder: str | None = None) -> None:
        self.model_name = model_name
        self.cache_folder = cache_folder
        self._model = None

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, 0), dtype=float)
        model = self._load_model()
        return model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name, cache_folder=self.cache_folder)
        return self._model


class InMemoryEmbeddingIndex:
    """In-memory embedding cache for v0.1 retrieval experiments."""

    def __init__(self, embedder: TextEmbedder) -> None:
        self.embedder = embedder
        self._cache: dict[str, np.ndarray] = {}

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, 0), dtype=float)

        missing_texts = [text for text in dict.fromkeys(texts) if text not in self._cache]
        if missing_texts:
            embeddings = self.embedder.embed_texts(missing_texts)
            for text, embedding in zip(missing_texts, embeddings, strict=True):
                self._cache[text] = embedding

        return np.vstack([self._cache[text] for text in texts])

    @property
    def cache_size(self) -> int:
        """Return the number of cached text embeddings."""

        return len(self._cache)


def session_turns_to_text(session_turns: object) -> str:
    """Flatten a haystack session into plain text."""

    turns = [f"{turn.role}: {turn.content}" for turn in session_turns]
    return "\n".join(turns)


def build_session_documents(example: PreparedExample) -> list[HistoryClip]:
    """Build retrieval documents from session summaries and full session text."""

    if example.haystack_sessions and example.haystack_session_ids and example.haystack_session_datetimes:
        documents: list[HistoryClip] = []
        conversation_id = example.question_id.rsplit("_q", 1)[0] if example.question_id else example.example_id

        for index, session_id in enumerate(example.haystack_session_ids):
            session_datetime = example.haystack_session_datetimes[index]
            summary_text = example.haystack_session_summaries[index] if index < len(example.haystack_session_summaries) else ""
            full_text = session_turns_to_text(example.haystack_sessions[index])

            if summary_text.strip():
                documents.append(
                    HistoryClip(
                        clip_id=f"{example.question_id}:{session_id}:summary",
                        conversation_id=conversation_id,
                        session_id=session_id,
                        speaker="session-summary",
                        timestamp=session_datetime,
                        text=summary_text,
                        source_ref=f"{session_id}:summary",
                        metadata={"doc_type": "summary"},
                    )
                )

            documents.append(
                HistoryClip(
                    clip_id=f"{example.question_id}:{session_id}:full",
                    conversation_id=conversation_id,
                    session_id=session_id,
                    speaker="session-full",
                    timestamp=session_datetime,
                    text=full_text,
                    source_ref=f"{session_id}:full",
                    metadata={"doc_type": "full_session"},
                )
            )

        return documents

    return sorted(example.history_clips, key=lambda clip: clip.timestamp)


def default_embedding_model_name() -> str:
    """Return the default local embedding model name."""

    return os.getenv("WMB_VECTOR_RAG_MODEL", "sentence-transformers/all-MiniLM-L6-v2")


def default_embedding_cache_folder() -> str | None:
    """Return optional embedding cache folder override."""

    cache_folder = os.getenv("WMB_EMBEDDING_CACHE_DIR")
    if not cache_folder:
        return None
    return str(Path(cache_folder).expanduser().resolve())
