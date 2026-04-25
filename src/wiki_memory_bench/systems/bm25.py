"""Simple lexical BM25 baseline."""

from __future__ import annotations

import math
from collections import Counter
from pathlib import Path
from time import perf_counter

from wiki_memory_bench.schemas import Citation, PreparedExample, RetrievedItem, SystemResult, TaskType, TokenUsage
from wiki_memory_bench.systems.answering import build_answerer, build_open_qa_answerer
from wiki_memory_bench.systems.base import SystemAdapter, choice_index, register_system
from wiki_memory_bench.systems.retrieval import build_session_documents
from wiki_memory_bench.utils.tokens import content_tokens, estimate_text_tokens, estimate_token_total


def _bm25_scores(query_tokens: list[str], documents: list[list[str]], k1: float = 1.5, b: float = 0.75) -> list[float]:
    """Compute simple BM25 scores for a tokenized document corpus."""

    if not documents:
        return []

    document_frequencies: Counter[str] = Counter()
    for document in documents:
        document_frequencies.update(set(document))

    average_length = sum(len(document) for document in documents) / len(documents)
    scores: list[float] = []

    for document in documents:
        term_frequencies = Counter(document)
        doc_length = max(1, len(document))
        score = 0.0

        for token in query_tokens:
            frequency = term_frequencies.get(token, 0)
            if frequency == 0:
                continue

            document_frequency = document_frequencies[token]
            inverse_document_frequency = math.log(
                1.0 + (len(documents) - document_frequency + 0.5) / (document_frequency + 0.5)
            )
            denominator = frequency + k1 * (1.0 - b + b * (doc_length / max(1.0, average_length)))
            score += inverse_document_frequency * ((frequency * (k1 + 1.0)) / denominator)

        scores.append(score)

    return scores
@register_system
class BM25Baseline(SystemAdapter):
    """Answer multiple-choice questions over top lexical matches."""

    name = "bm25"
    description = "Retrieves session summaries and full sessions with a local BM25 scorer before choosing an answer."
    def __init__(self, answerer: str = "deterministic", top_k: int = 4, **_: object) -> None:
        self.top_k = top_k
        self.answerer_mode = answerer
        self.answerer = build_answerer(answerer, task_name="mc-answerer")
        self.open_qa_answerer = build_open_qa_answerer(answerer, task_name="open-qa-answerer")

    def prepare_run(self, run_dir: Path, dataset_name: str) -> None:
        if hasattr(self.answerer, "set_artifact_dir"):
            self.answerer.set_artifact_dir(run_dir / "artifacts" / "llm" / "answerer")
        if hasattr(self.open_qa_answerer, "set_artifact_dir"):
            self.open_qa_answerer.set_artifact_dir(run_dir / "artifacts" / "llm" / "answerer")

    def run(self, example: PreparedExample) -> SystemResult:
        started = perf_counter()
        retrieval_documents = build_session_documents(example)
        query_tokens = content_tokens(example.question)
        documents = [content_tokens(document.text) for document in retrieval_documents]
        scores = _bm25_scores(query_tokens, documents)

        ranked_pairs = sorted(
            zip(retrieval_documents, scores, strict=True),
            key=lambda pair: (-pair[1], pair[0].timestamp, pair[0].clip_id),
        )
        retrieved_pairs = ranked_pairs[: self.top_k]
        retrieved_items = [
            RetrievedItem(
                clip_id=clip.clip_id,
                rank=index + 1,
                score=round(score, 6),
                text=clip.text,
                retrieved_tokens=estimate_text_tokens(clip.text),
            )
            for index, (clip, score) in enumerate(retrieved_pairs)
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
                    "retrieved_count": len(retrieved_pairs),
                    "retrieval_top_k": self.top_k,
                    "answerer_mode": self.answerer_mode,
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
                "retrieved_count": len(retrieved_pairs),
                "retrieval_top_k": self.top_k,
                "answerer_mode": self.answerer_mode,
                **selection.metadata,
            },
        )
