"""Vector RAG baseline with in-memory embeddings."""

from __future__ import annotations

import os
from pathlib import Path
from time import perf_counter

import numpy as np

from wiki_memory_bench.schemas import Citation, PreparedExample, RetrievedItem, SystemResult, TaskType, TokenUsage
from wiki_memory_bench.systems.answering import build_answerer, build_open_qa_answerer
from wiki_memory_bench.systems.base import SystemAdapter, choice_index, register_system
from wiki_memory_bench.systems.retrieval import (
    InMemoryEmbeddingIndex,
    SentenceTransformerEmbedder,
    TextEmbedder,
    build_session_documents,
    default_embedding_cache_folder,
    default_embedding_model_name,
)
from wiki_memory_bench.utils.tokens import estimate_text_tokens, estimate_token_total


def _cosine_scores(query_embedding: np.ndarray, document_embeddings: np.ndarray) -> np.ndarray:
    """Compute cosine scores for normalized embeddings."""

    if document_embeddings.size == 0:
        return np.array([], dtype=float)
    return document_embeddings @ query_embedding


@register_system
class VectorRAGBaseline(SystemAdapter):
    """Retrieve top-k chunks with local embeddings and answer deterministically."""

    name = "vector-rag"
    description = "Embeds session chunks with sentence-transformers and answers with a deterministic retrieval-aware scorer."

    def __init__(
        self,
        embedder: TextEmbedder | None = None,
        model_name: str | None = None,
        top_k: int | None = None,
        answerer: str = "deterministic",
        **_: object,
    ) -> None:
        self.model_name = model_name or default_embedding_model_name()
        self.top_k = top_k or int(os.getenv("WMB_VECTOR_RAG_TOP_K", "4"))
        self.answerer_mode = answerer
        self.embedder = embedder or SentenceTransformerEmbedder(
            model_name=self.model_name,
            cache_folder=default_embedding_cache_folder(),
        )
        self.embedding_index = InMemoryEmbeddingIndex(self.embedder)
        self.answerer = build_answerer(answerer, embedding_index=self.embedding_index, task_name="mc-answerer")
        self.open_qa_answerer = build_open_qa_answerer(answerer, task_name="open-qa-answerer")

    def prepare_run(self, run_dir: Path, dataset_name: str) -> None:
        if hasattr(self.answerer, "set_artifact_dir"):
            self.answerer.set_artifact_dir(run_dir / "artifacts" / "llm" / "answerer")
        if hasattr(self.open_qa_answerer, "set_artifact_dir"):
            self.open_qa_answerer.set_artifact_dir(run_dir / "artifacts" / "llm" / "answerer")

    def run(self, example: PreparedExample) -> SystemResult:
        started = perf_counter()
        retrieval_documents = build_session_documents(example)
        document_texts = [document.text for document in retrieval_documents]
        document_embeddings = self.embedding_index.embed_texts(document_texts)
        query_embedding = self.embedding_index.embed_texts([example.question])[0]
        scores = _cosine_scores(query_embedding, document_embeddings)

        ranked_pairs = sorted(
            zip(retrieval_documents, scores.tolist(), strict=True),
            key=lambda pair: (-pair[1], pair[0].timestamp, pair[0].clip_id),
        )
        retrieved_pairs = ranked_pairs[: self.top_k]
        retrieved_items = [
            RetrievedItem(
                clip_id=document.clip_id,
                rank=index + 1,
                score=float(score),
                text=document.text,
                retrieved_tokens=estimate_text_tokens(document.text),
            )
            for index, (document, score) in enumerate(retrieved_pairs)
        ]

        citations = []
        if example.task_type == TaskType.MULTIPLE_CHOICE:
            selection = self.answerer.select_choice(example, retrieved_items)
            selected_choice = selection.choice
            supporting_item = selection.supporting_item
            confidence = selection.confidence
            citation_ids = set(selection.citation_ids or ([supporting_item.clip_id] if supporting_item is not None else []))
            for item in retrieved_items:
                if item.clip_id in citation_ids:
                    citations.append(Citation(clip_id=item.clip_id, source_ref=None, quote=item.text))
            if not citations and supporting_item is not None:
                citations.append(Citation(clip_id=supporting_item.clip_id, source_ref=None, quote=supporting_item.text))

            input_tokens = estimate_token_total(
                [item.text for item in retrieved_items] + [example.question] + [choice.text for choice in example.choices]
            )
            output_tokens = estimate_text_tokens(selected_choice.text)
            latency_ms = (perf_counter() - started) * 1000.0

            return SystemResult(
                example_id=example.example_id,
                system_name=self.name,
                selected_choice_id=selected_choice.choice_id,
                selected_choice_index=choice_index(example, selected_choice),
                selected_choice_text=selected_choice.text,
                answer_text=selected_choice.text,
                citations=citations,
                retrieved_items=retrieved_items,
                token_usage=TokenUsage(
                    input_tokens=selection.token_usage.input_tokens or input_tokens,
                    output_tokens=selection.token_usage.output_tokens or output_tokens,
                    estimated_cost_usd=selection.token_usage.estimated_cost_usd,
                ),
                latency_ms=latency_ms,
                metadata={
                    "confidence": round(confidence, 4),
                    "retrieved_count": len(retrieved_items),
                    "retrieval_top_k": self.top_k,
                    "embedding_model": self.model_name,
                    "answerer_mode": self.answerer_mode,
                    "embedding_cache_size": self.embedding_index.cache_size,
                    **selection.metadata,
                },
            )

        selection = self.open_qa_answerer.answer_question(example, retrieved_items)
        supporting_item = selection.supporting_item
        citation_ids = set(selection.citation_ids or ([supporting_item.clip_id] if supporting_item is not None else []))
        for item in retrieved_items:
            if item.clip_id in citation_ids:
                citations.append(Citation(clip_id=item.clip_id, source_ref=None, quote=item.text))
        if not citations and supporting_item is not None:
            citations.append(Citation(clip_id=supporting_item.clip_id, source_ref=None, quote=supporting_item.text))

        input_tokens = estimate_token_total([item.text for item in retrieved_items] + [example.question])
        output_tokens = estimate_text_tokens(selection.answer_text)
        latency_ms = (perf_counter() - started) * 1000.0
        return SystemResult(
            example_id=example.example_id,
            system_name=self.name,
            answer_text=selection.answer_text,
            citations=citations,
            retrieved_items=retrieved_items,
            token_usage=TokenUsage(
                input_tokens=selection.token_usage.input_tokens or input_tokens,
                output_tokens=selection.token_usage.output_tokens or output_tokens,
                estimated_cost_usd=selection.token_usage.estimated_cost_usd,
            ),
            latency_ms=latency_ms,
            metadata={
                "confidence": round(selection.confidence, 4),
                "retrieved_count": len(retrieved_items),
                "retrieval_top_k": self.top_k,
                "embedding_model": self.model_name,
                "answerer_mode": self.answerer_mode,
                "embedding_cache_size": self.embedding_index.cache_size,
                **selection.metadata,
            },
        )
