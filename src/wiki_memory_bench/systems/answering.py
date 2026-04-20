"""Deterministic and LLM answerers shared by baseline systems."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import numpy as np

from wiki_memory_bench.metrics.multiple_choice import normalize_choice_prediction
from wiki_memory_bench.schemas import ChoiceOption, PreparedExample, RetrievedItem, SystemResult, TokenUsage
from wiki_memory_bench.systems.base import is_abstention_choice
from wiki_memory_bench.systems.retrieval import InMemoryEmbeddingIndex
from wiki_memory_bench.utils.llm import LiteLLMRuntime
from wiki_memory_bench.utils.tokens import content_tokens, normalize_text


@dataclass(slots=True)
class AnswerSelection:
    """Normalized answerer output consumed by systems."""

    choice: ChoiceOption
    supporting_item: RetrievedItem | None
    confidence: float
    rationale: str | None = None
    citation_ids: list[str] = field(default_factory=list)
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class OpenQASelection:
    """Normalized open-QA answerer output."""

    answer_text: str
    supporting_item: RetrievedItem | None
    confidence: float
    rationale: str | None = None
    citation_ids: list[str] = field(default_factory=list)
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    metadata: dict[str, object] = field(default_factory=dict)


class DeterministicMultipleChoiceAnswerer:
    """Deterministic answerer that combines lexical and embedding signals."""

    def __init__(self, embedding_index: InMemoryEmbeddingIndex | None = None) -> None:
        self.embedding_index = embedding_index

    def set_artifact_dir(self, artifact_dir: Path) -> None:
        """Deterministic answerer does not emit LLM prompt artifacts."""

    def select_choice(
        self,
        example: PreparedExample,
        retrieved_items: Sequence[RetrievedItem],
    ) -> AnswerSelection:
        question_tokens = set(content_tokens(example.question))
        abstention_choice = next((choice for choice in example.choices if is_abstention_choice(choice)), None)
        max_retrieval_score = max((item.score for item in retrieved_items), default=1.0) or 1.0

        choice_embeddings = self._embed_choice_texts(example.choices)
        chunk_embeddings = self._embed_chunk_texts(retrieved_items)

        best_choice = abstention_choice or example.choices[0]
        best_item: RetrievedItem | None = None
        best_score = float("-inf")

        for choice_index, choice in enumerate(example.choices):
            if is_abstention_choice(choice):
                continue

            choice_tokens = set(content_tokens(choice.text))
            normalized_choice = normalize_text(choice.text)
            total_score = 0.0
            supporting_item: RetrievedItem | None = None
            supporting_item_score = float("-inf")

            for item_index, item in enumerate(retrieved_items):
                item_tokens = set(content_tokens(item.text))
                overlap = len(choice_tokens & item_tokens)
                phrase_bonus = 3.0 if normalized_choice and normalized_choice in normalize_text(item.text) else 0.0
                embedding_score = self._embedding_score(choice_embeddings, chunk_embeddings, choice_index, item_index)
                if overlap == 0 and phrase_bonus == 0.0 and embedding_score == 0.0:
                    continue

                question_overlap = len(question_tokens & item_tokens)
                normalized_retrieval = max(0.0, item.score) / max_retrieval_score
                lexical_score = overlap * 2.0 + phrase_bonus + question_overlap * 0.35 + normalized_retrieval * 0.75
                item_score = lexical_score + embedding_score
                total_score += item_score

                if item_score > supporting_item_score:
                    supporting_item_score = item_score
                    supporting_item = item

            if total_score > best_score:
                best_choice = choice
                best_item = supporting_item
                best_score = total_score

        if abstention_choice is not None and best_score < 2.0:
            return AnswerSelection(choice=abstention_choice, supporting_item=None, confidence=best_score)

        return AnswerSelection(
            choice=best_choice,
            supporting_item=best_item,
            confidence=best_score,
            citation_ids=[best_item.clip_id] if best_item is not None else [],
        )

    def _embed_choice_texts(self, choices: Sequence[ChoiceOption]) -> np.ndarray | None:
        if self.embedding_index is None:
            return None
        return self.embedding_index.embed_texts([choice.text for choice in choices])

    def _embed_chunk_texts(self, retrieved_items: Sequence[RetrievedItem]) -> np.ndarray | None:
        if self.embedding_index is None:
            return None
        return self.embedding_index.embed_texts([item.text for item in retrieved_items])

    def _embedding_score(
        self,
        choice_embeddings: np.ndarray | None,
        chunk_embeddings: np.ndarray | None,
        choice_index: int,
        item_index: int,
    ) -> float:
        if choice_embeddings is None or chunk_embeddings is None:
            return 0.0

        cosine_similarity = float(np.dot(choice_embeddings[choice_index], chunk_embeddings[item_index]))
        return max(0.0, cosine_similarity) * 2.5


class LLMMultipleChoiceAnswerer:
    """LLM answerer that returns structured JSON for multiple-choice tasks."""

    def __init__(self, runtime: LiteLLMRuntime) -> None:
        self.runtime = runtime

    def set_artifact_dir(self, artifact_dir: Path) -> None:
        self.runtime.set_artifact_dir(artifact_dir)

    def select_choice(
        self,
        example: PreparedExample,
        retrieved_items: Sequence[RetrievedItem],
    ) -> AnswerSelection:
        prompt = build_multiple_choice_prompt(example, retrieved_items)
        parsed, token_usage, metadata = self.runtime.complete_json(prompt)
        normalized_prediction = SystemResult(
            example_id=example.example_id,
            system_name="llm-answerer",
            selected_choice_index=parsed.get("choice_index"),
            selected_choice_text=parsed.get("choice_text"),
            answer_text=parsed.get("choice_text"),
        )
        choice_id, choice_index, choice_text = normalize_choice_prediction(example, normalized_prediction)
        if choice_index is None:
            raise ValueError("LLM answerer did not return a valid choice")

        supporting_item = next((item for item in retrieved_items if item.clip_id in set(parsed.get("citations", []))), None)
        return AnswerSelection(
            choice=example.choices[choice_index],
            supporting_item=supporting_item,
            confidence=1.0,
            rationale=str(parsed.get("rationale", "")),
            citation_ids=[str(value) for value in parsed.get("citations", [])],
            token_usage=token_usage,
            metadata={
                "llm_response": parsed,
                "llm_cached": metadata.get("cached", False),
                "llm_artifact_path": metadata.get("artifact_path"),
            },
        )


def build_multiple_choice_prompt(example: PreparedExample, retrieved_items: Sequence[RetrievedItem]) -> str:
    """Build the JSON-only prompt used by the LLM multiple-choice answerer."""

    chunks = "\n\n".join(
        f"Chunk ID: {item.clip_id}\nScore: {item.score:.4f}\nText:\n{item.text}"
        for item in retrieved_items
    )
    choices = "\n".join(
        f"- index {index}: {choice.text} (label {choice.label}, id {choice.choice_id})"
        for index, choice in enumerate(example.choices)
    )
    return "\n".join(
        [
            "You are a multiple-choice answerer for a memory benchmark.",
            "Answer ONLY with a JSON object.",
            'Use this schema: {"choice_index": int, "choice_text": str, "rationale": str, "citations": [str]}',
            "Citations must be chunk ids copied exactly from the retrieved chunks.",
            "",
            f"Question: {example.question}",
            "",
            "Choices:",
            choices,
            "",
            "Retrieved chunks:",
            chunks or "(no retrieved chunks)",
            "",
            "Return the best answer as JSON only.",
        ]
    )


class DeterministicOpenQAAnswerer:
    """Deterministic open-QA answerer using retrieved snippets."""

    def set_artifact_dir(self, artifact_dir: Path) -> None:
        """Deterministic answerer does not emit LLM prompt artifacts."""

    def answer_question(
        self,
        example: PreparedExample,
        retrieved_items: Sequence[RetrievedItem],
    ) -> OpenQASelection:
        if not retrieved_items:
            return OpenQASelection(answer_text="", supporting_item=None, confidence=0.0)

        question_tokens = set(content_tokens(example.question))
        best_item = retrieved_items[0]
        best_snippet = best_item.text
        best_score = float("-inf")

        for item in retrieved_items:
            for snippet in _candidate_snippets(item.text):
                snippet_tokens = set(content_tokens(snippet))
                overlap = len(question_tokens & snippet_tokens)
                score = overlap * 2.0 + (item.score if item.score > 0 else 0.0)
                if score > best_score:
                    best_score = score
                    best_item = item
                    best_snippet = _format_open_answer(example.question, snippet)

        return OpenQASelection(
            answer_text=best_snippet,
            supporting_item=best_item,
            confidence=best_score,
            citation_ids=[best_item.clip_id],
        )


class LLMOpenQAAnswerer:
    """Optional LLM answerer for open QA tasks."""

    def __init__(self, runtime: LiteLLMRuntime) -> None:
        self.runtime = runtime

    def set_artifact_dir(self, artifact_dir: Path) -> None:
        self.runtime.set_artifact_dir(artifact_dir)

    def answer_question(
        self,
        example: PreparedExample,
        retrieved_items: Sequence[RetrievedItem],
    ) -> OpenQASelection:
        prompt = build_open_qa_prompt(example, retrieved_items)
        parsed, token_usage, metadata = self.runtime.complete_json(prompt)
        answer_text = str(parsed.get("answer", "")).strip()
        citation_ids = [str(value) for value in parsed.get("citations", [])]
        supporting_item = next((item for item in retrieved_items if item.clip_id in set(citation_ids)), None)
        return OpenQASelection(
            answer_text=answer_text,
            supporting_item=supporting_item,
            confidence=1.0,
            rationale=str(parsed.get("rationale", "")),
            citation_ids=citation_ids,
            token_usage=token_usage,
            metadata={
                "llm_response": parsed,
                "llm_cached": metadata.get("cached", False),
                "llm_artifact_path": metadata.get("artifact_path"),
            },
        )


def build_open_qa_prompt(example: PreparedExample, retrieved_items: Sequence[RetrievedItem]) -> str:
    """Build a JSON-only prompt for open QA answering."""

    chunks = "\n\n".join(
        f"Chunk ID: {item.clip_id}\nScore: {item.score:.4f}\nText:\n{item.text}"
        for item in retrieved_items
    )
    return "\n".join(
        [
            "You are an open-question answerer for a memory benchmark.",
            "Answer ONLY with a JSON object.",
            'Use this schema: {"answer": str, "rationale": str, "citations": [str]}',
            "Citations must be chunk ids copied exactly from the retrieved chunks.",
            "",
            f"Question: {example.question}",
            "",
            "Retrieved chunks:",
            chunks or "(no retrieved chunks)",
            "",
            "Return the best answer as JSON only.",
        ]
    )


def build_answerer(
    mode: str,
    *,
    embedding_index: InMemoryEmbeddingIndex | None = None,
    task_name: str = "answerer",
) -> DeterministicMultipleChoiceAnswerer | LLMMultipleChoiceAnswerer:
    """Construct the requested answerer implementation."""

    if mode == "deterministic":
        return DeterministicMultipleChoiceAnswerer(embedding_index=embedding_index)
    if mode == "llm":
        return LLMMultipleChoiceAnswerer(LiteLLMRuntime(task_name=task_name))
    raise ValueError(f"Unsupported answerer mode: {mode}")


def build_open_qa_answerer(mode: str, *, task_name: str = "open-qa-answerer") -> DeterministicOpenQAAnswerer | LLMOpenQAAnswerer:
    """Construct an open-QA answerer implementation."""

    if mode == "deterministic":
        return DeterministicOpenQAAnswerer()
    if mode == "llm":
        return LLMOpenQAAnswerer(LiteLLMRuntime(task_name=task_name))
    raise ValueError(f"Unsupported answerer mode: {mode}")


def _candidate_snippets(text: str) -> list[str]:
    lines = [line.strip("- ").strip() for line in text.splitlines() if line.strip()]
    snippets: list[str] = []
    for line in lines:
        snippets.extend([part.strip() for part in line.replace("?", ".").split(".") if part.strip()])
    return snippets or [text.strip()]


def _format_open_answer(question: str, snippet: str) -> str:
    lowered_question = question.lower()
    if lowered_question.startswith("when "):
        return snippet
    if lowered_question.startswith(("what ", "which ", "who ", "where ", "how ")):
        return snippet
    return snippet
