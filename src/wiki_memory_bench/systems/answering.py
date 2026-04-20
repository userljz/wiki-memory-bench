"""Deterministic and LLM answerers shared by baseline systems."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Sequence

import numpy as np

from wiki_memory_bench.metrics.multiple_choice import normalize_choice_prediction
from wiki_memory_bench.schemas import ChoiceOption, PreparedExample, RetrievedItem, SystemResult, TokenUsage
from wiki_memory_bench.systems.base import is_abstention_choice
from wiki_memory_bench.systems.retrieval import InMemoryEmbeddingIndex
from wiki_memory_bench.utils.llm import LiteLLMRuntime
from wiki_memory_bench.utils.tokens import content_tokens, normalize_text

ABSTENTION_ANSWER = "Not enough information in memory."
METADATA_LINE_PREFIXES = ("Question:", "Tags:", "Concept:", "Why saved:", "Summary:", "Source:", "Evidence:")
PRIMARY_EVIDENCE_PREFIXES = ("sources/", "evidence/", "preferences/")
NAVIGATION_PREFIXES = ("concepts/", "people/", "events/", "index", "log")
FORGETTING_CUES = ("remove", "forget", "forgot", "do not keep", "don't keep", "temporary", "after use", "no longer")


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


@dataclass(slots=True)
class OpenQACandidate:
    """Single deterministic open-QA answer candidate."""

    snippet: str
    item: RetrievedItem
    score: float


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
            return OpenQASelection(answer_text=ABSTENTION_ANSWER, supporting_item=None, confidence=0.0)

        question_tokens = set(content_tokens(example.question))
        max_retrieval_score = max((item.score for item in retrieved_items), default=1.0) or 1.0
        candidates: list[OpenQACandidate] = []

        for item in retrieved_items:
            for snippet in _candidate_snippets(item.text):
                score = _score_open_qa_candidate(
                    question_tokens=question_tokens,
                    snippet=snippet,
                    item=item,
                    max_retrieval_score=max_retrieval_score,
                )
                if score > 0.0:
                    candidates.append(OpenQACandidate(snippet=snippet, item=item, score=score))

        if not candidates:
            return OpenQASelection(answer_text=ABSTENTION_ANSWER, supporting_item=None, confidence=0.0)

        candidates.sort(key=lambda candidate: (-candidate.score, candidate.item.rank, candidate.item.clip_id, candidate.snippet))
        best_candidate = candidates[0]

        if _should_abstain_from_candidate(example.question, best_candidate):
            return OpenQASelection(
                answer_text=ABSTENTION_ANSWER,
                supporting_item=best_candidate.item,
                confidence=best_candidate.score,
                citation_ids=[best_candidate.item.clip_id],
            )

        if _is_multi_snippet_question(example.question):
            combined_answer, combined_items = _combine_open_qa_candidates(candidates)
            if combined_answer is not None and combined_items:
                return OpenQASelection(
                    answer_text=_format_open_answer(example.question, combined_answer),
                    supporting_item=combined_items[0],
                    confidence=sum(candidate.score for candidate in candidates[: len(combined_items)]),
                    citation_ids=[item.clip_id for item in combined_items],
                )

        return OpenQASelection(
            answer_text=_format_open_answer(example.question, best_candidate.snippet),
            supporting_item=best_candidate.item,
            confidence=best_candidate.score,
            citation_ids=[best_candidate.item.clip_id],
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
    lines = [_normalize_candidate_line(line) for line in text.splitlines() if line.strip()]
    snippets: list[str] = []
    for line in lines:
        if not line:
            continue
        if _is_metadata_line(line) or line.startswith("#") or line.startswith("[["):
            continue
        snippets.append(line)
        snippets.extend([part.strip() for part in re.split(r"[.;]\s+", line) if part.strip() and part.strip() != line])
    return snippets or [text.strip()]


def _format_open_answer(question: str, snippet: str) -> str:
    lowered_question = question.lower()
    if lowered_question.startswith("when "):
        return snippet
    if lowered_question.startswith(("what ", "which ", "who ", "where ", "how ")):
        return snippet
    return snippet


def _score_open_qa_candidate(
    *,
    question_tokens: set[str],
    snippet: str,
    item: RetrievedItem,
    max_retrieval_score: float,
) -> float:
    snippet_tokens = set(content_tokens(snippet))
    if not snippet_tokens:
        return 0.0

    overlap = len(question_tokens & snippet_tokens)
    if overlap == 0 and not _looks_answer_bearing(snippet):
        return 0.0

    normalized_retrieval = max(0.0, item.score) / max_retrieval_score
    return (
        overlap * 2.0
        + normalized_retrieval * 0.75
        + _page_type_bonus(item.clip_id)
        + (0.75 if _looks_answer_bearing(snippet) else 0.0)
        + (0.5 if _looks_like_speaker_evidence(snippet) else 0.0)
    )


def _page_type_bonus(clip_id: str) -> float:
    if clip_id.startswith(PRIMARY_EVIDENCE_PREFIXES):
        return 1.5
    if clip_id.startswith(NAVIGATION_PREFIXES) or clip_id in NAVIGATION_PREFIXES:
        return -2.0
    return 0.0


def _looks_answer_bearing(snippet: str) -> bool:
    lowered = normalize_text(snippet)
    if re.search(r"\b\d{4}-\d{2}-\d{2}\b", snippet):
        return True
    return any(token in lowered for token in (" is ", " are ", " was ", " moved ", " update ", " current ", " favorite ", " prefer", ":"))


def _looks_like_speaker_evidence(snippet: str) -> bool:
    return bool(re.match(r"^[A-Za-z][A-Za-z\s'\-]{0,40}:\s+\S", snippet))


def _is_metadata_line(line: str) -> bool:
    normalized = _normalize_candidate_line(line)
    if any(normalized.startswith(prefix) for prefix in METADATA_LINE_PREFIXES):
        return True
    if normalized.startswith(("## ", "# ")):
        return True
    return normalized in {"Supports", "Source Pages", "Relevant Sources", "Relevant Evidence Pages"}


def _normalize_candidate_line(line: str) -> str:
    cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
    return cleaned.strip().lstrip("-").strip()


def _should_abstain_from_candidate(question: str, candidate: OpenQACandidate) -> bool:
    normalized_snippet = normalize_text(candidate.snippet)
    if candidate.score < 1.5:
        return True
    if any(cue in normalized_snippet for cue in FORGETTING_CUES):
        return True
    return "not enough information" in normalized_snippet or "unknown" in normalized_snippet


def _is_multi_snippet_question(question: str) -> bool:
    lowered = normalize_text(question)
    return any(token in lowered for token in (" two ", " both ", " aggregate ", " new things "))


def _combine_open_qa_candidates(candidates: Sequence[OpenQACandidate]) -> tuple[str | None, list[RetrievedItem]]:
    selected: list[OpenQACandidate] = []
    seen_clip_ids: set[str] = set()
    for candidate in candidates:
        if candidate.item.clip_id in seen_clip_ids:
            continue
        if _should_abstain_from_candidate("", candidate):
            continue
        selected.append(candidate)
        seen_clip_ids.add(candidate.item.clip_id)
        if len(selected) == 2:
            break

    if len(selected) < 2:
        return None, []

    combined_answer = " and ".join(candidate.snippet.rstrip(".") for candidate in selected)
    return combined_answer, [candidate.item for candidate in selected]
