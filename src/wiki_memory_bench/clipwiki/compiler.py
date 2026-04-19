"""Deterministic compiler for the ClipWiki baseline."""

from __future__ import annotations

import math
import random
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from wiki_memory_bench.clipwiki.markdown_store import MarkdownPage, MarkdownStore
from wiki_memory_bench.schemas import PreparedExample, SessionTurn
from wiki_memory_bench.utils.tokens import content_tokens, estimate_text_tokens

NAME_PATTERN = re.compile(r"\[([A-Z][A-Z\s'\-]+)\]")
DATE_PATTERN = re.compile(r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}\s+[A-Z][a-z]+\s+\d{4})\b")
PREFERENCE_KEYWORDS = ("favorite", "prefer", "likes", "like", "love", "enjoy", "wants", "plan", "plans")


@dataclass(slots=True)
class CompiledWiki:
    """Compiled wiki pages and size metadata."""

    pages: list[MarkdownPage]
    wiki_size_pages: int
    wiki_size_tokens: int
    selected_session_ids: list[str]


def compile_clipwiki(
    example: PreparedExample,
    output_dir: Path,
    mode: str,
    curated_top_k: int = 3,
    noisy_extra_sessions: int = 2,
) -> CompiledWiki:
    """Compile a deterministic markdown wiki for a single example."""

    selected_indices = select_session_indices(
        example,
        mode=mode,
        curated_top_k=curated_top_k,
        noisy_extra_sessions=noisy_extra_sessions,
    )
    selected_session_ids = [example.haystack_session_ids[index] for index in selected_indices]

    store = MarkdownStore(output_dir)
    for directory_name in ("sources", "concepts", "people", "events", "preferences"):
        (output_dir / directory_name).mkdir(parents=True, exist_ok=True)
    pages: list[MarkdownPage] = []
    source_page_ids: list[str] = []
    speaker_sources: dict[str, list[str]] = {}
    preference_pages: list[MarkdownPage] = []

    for index in selected_indices:
        session_id = example.haystack_session_ids[index]
        session_datetime = example.haystack_session_datetimes[index]
        summary = example.haystack_session_summaries[index] if index < len(example.haystack_session_summaries) else ""
        session_turns = example.haystack_sessions[index]
        transcript = session_to_markdown(session_turns)
        source_page_id = f"sources/{session_id}"
        source_page_ids.append(source_page_id)

        fact_lines = extract_fact_candidates(f"{summary}\n{transcript}")
        source_page = MarkdownPage(
            page_id=source_page_id,
            relative_path=f"sources/{session_id}.md",
            title=f"Source {session_id}",
            source_ids=[source_page_id],
            content="\n".join(
                [
                    f"# Source {session_id}",
                    "",
                    f"- Date: `{session_datetime.isoformat()}`",
                    f"- Summary: {summary or 'No summary available.'}",
                    "",
                    "## Facts",
                    *([f"- {fact}" for fact in fact_lines] if fact_lines else ["- No deterministic facts extracted."]),
                    "",
                    "## Transcript",
                    transcript,
                    "",
                ]
            ),
        )
        pages.append(source_page)
        store.write_page(source_page)

        for speaker_name in extract_speaker_names(transcript):
            speaker_sources.setdefault(speaker_name, []).append(source_page_id)

        preference_lines = [line for line in fact_lines if any(keyword in line.lower() for keyword in PREFERENCE_KEYWORDS)]
        if preference_lines:
            preference_page = MarkdownPage(
                page_id=f"preferences/{session_id}",
                relative_path=f"preferences/{session_id}.md",
                title=f"Preferences from {session_id}",
                source_ids=[source_page_id],
                content="\n".join(
                    [
                        f"# Preferences from {session_id}",
                        "",
                        *[f"- {line}" for line in preference_lines],
                        "",
                        f"Sources: [[{source_page_id}]]",
                        "",
                    ]
                ),
            )
            preference_pages.append(preference_page)
            pages.append(preference_page)
            store.write_page(preference_page)

        event_page = MarkdownPage(
            page_id=f"events/{session_id}",
            relative_path=f"events/{session_id}.md",
            title=f"Event {session_id}",
            source_ids=[source_page_id],
            content="\n".join(
                [
                    f"# Event {session_id}",
                    "",
                    f"- Date: `{session_datetime.date().isoformat()}`",
                    f"- Summary: {summary or 'No summary available.'}",
                    "",
                    f"Sources: [[{source_page_id}]]",
                    "",
                ]
            ),
        )
        pages.append(event_page)
        store.write_page(event_page)

    for speaker_name, linked_sources in sorted(speaker_sources.items()):
        slug = slugify(speaker_name)
        people_page = MarkdownPage(
            page_id=f"people/{slug}",
            relative_path=f"people/{slug}.md",
            title=speaker_name,
            source_ids=sorted(set(linked_sources)),
            content="\n".join(
                [
                    f"# {speaker_name}",
                    "",
                    "## Source Pages",
                    *[f"- [[{source_id}]]" for source_id in sorted(set(linked_sources))],
                    "",
                ]
            ),
        )
        pages.append(people_page)
        store.write_page(people_page)

    concept_page = MarkdownPage(
        page_id=f"concepts/{example.question_type}",
        relative_path=f"concepts/{slugify(example.question_type)}.md",
        title=f"Question type: {example.question_type}",
        source_ids=source_page_ids,
        content="\n".join(
            [
                f"# Concept: {example.question_type}",
                "",
                f"- Question: {example.question}",
                "",
                "## Relevant Sources",
                *[f"- [[{source_id}]]" for source_id in source_page_ids],
                "",
            ]
        ),
    )
    pages.append(concept_page)
    store.write_page(concept_page)

    index_page = MarkdownPage(
        page_id="index",
        relative_path="index.md",
        title="Index",
        source_ids=source_page_ids,
        content="\n".join(
            [
                "# ClipWiki Index",
                "",
                f"- Mode: `{mode}`",
                f"- Selected sessions: {', '.join(selected_session_ids)}",
                "",
                "## Source Pages",
                *[
                    f"- [[sources/{example.haystack_session_ids[index]}]]: "
                    f"{example.haystack_session_summaries[index] if index < len(example.haystack_session_summaries) else 'No summary available.'}"
                    for index in selected_indices
                ],
                "",
            ]
        ),
    )
    pages.append(index_page)
    store.write_page(index_page)

    log_page = MarkdownPage(
        page_id="log",
        relative_path="log.md",
        title="Log",
        source_ids=source_page_ids,
        content="\n".join(
            [
                "# ClipWiki Log",
                "",
                f"- Example: `{example.example_id}`",
                f"- Question type: `{example.question_type}`",
                f"- Mode: `{mode}`",
                f"- Selected sessions: `{', '.join(selected_session_ids)}`",
                "",
            ]
        ),
    )
    pages.append(log_page)
    store.write_page(log_page)

    wiki_size_tokens = sum(estimate_text_tokens(page.content) for page in pages)
    return CompiledWiki(
        pages=pages,
        wiki_size_pages=len(pages),
        wiki_size_tokens=wiki_size_tokens,
        selected_session_ids=selected_session_ids,
    )


def select_session_indices(
    example: PreparedExample,
    mode: str,
    curated_top_k: int = 3,
    noisy_extra_sessions: int = 2,
) -> list[int]:
    """Choose which sessions to compile for a given ClipWiki mode."""

    total_sessions = len(example.haystack_session_ids)
    all_indices = list(range(total_sessions))

    if mode == "full-wiki":
        return all_indices

    curated = _gold_or_heuristic_session_indices(example, top_k=curated_top_k)
    if mode == "oracle-curated":
        return curated

    if mode == "noisy-curated":
        remaining = [index for index in all_indices if index not in curated]
        rng = random.Random(example.question_id or example.example_id)
        noisy_count = min(noisy_extra_sessions, len(remaining))
        noisy_indices = sorted(rng.sample(remaining, noisy_count)) if noisy_count > 0 else []
        return sorted(set(curated + noisy_indices))

    raise ValueError(f"Unsupported ClipWiki mode: {mode}")


def retrieve_wiki_pages(question: str, wiki: CompiledWiki, top_k: int = 4) -> list[MarkdownPage]:
    """Retrieve wiki pages with BM25-style lexical scoring."""

    documents = wiki.pages
    if not documents:
        return []

    query_tokens = content_tokens(question)
    tokenized_docs = [content_tokens(page.content) for page in documents]
    scores = _bm25_scores(query_tokens, tokenized_docs)
    ranked = sorted(
        zip(documents, scores, strict=True),
        key=lambda item: (-item[1], item[0].page_id),
    )
    return [page for page, _ in ranked[:top_k]]


def page_score_lookup(question: str, wiki: CompiledWiki) -> dict[str, float]:
    """Return BM25 scores keyed by page id for all compiled pages."""

    documents = wiki.pages
    query_tokens = content_tokens(question)
    tokenized_docs = [content_tokens(page.content) for page in documents]
    scores = _bm25_scores(query_tokens, tokenized_docs)
    return {page.page_id: score for page, score in zip(documents, scores, strict=True)}


def session_to_markdown(session_turns: list[SessionTurn]) -> str:
    """Convert session turns into a markdown transcript block."""

    return "\n".join(f"- **{turn.role}**: {turn.content}" for turn in session_turns)


def extract_speaker_names(text: str) -> list[str]:
    """Extract likely speaker names from transcript text."""

    names = {normalize_name(match.group(1)) for match in NAME_PATTERN.finditer(text)}
    return sorted(name for name in names if name)


def extract_fact_candidates(text: str) -> list[str]:
    """Extract a few deterministic fact-like lines from text."""

    candidates: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip().lstrip("-").strip()
        if not line:
            continue
        lowered = line.lower()
        if any(keyword in lowered for keyword in PREFERENCE_KEYWORDS) or DATE_PATTERN.search(line):
            candidates.append(line)
        elif " is " in lowered or " was " in lowered or " are " in lowered:
            candidates.append(line)
        if len(candidates) >= 6:
            break
    return candidates


def slugify(value: str) -> str:
    """Convert a string into a filesystem-friendly slug."""

    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "page"


def normalize_name(value: str) -> str:
    """Normalize speaker names extracted from brackets."""

    return " ".join(part.capitalize() for part in value.strip().split())


def _gold_or_heuristic_session_indices(example: PreparedExample, top_k: int) -> list[int]:
    if example.gold_evidence:
        selected = [
            index
            for index, session_id in enumerate(example.haystack_session_ids)
            if session_id in set(example.gold_evidence)
        ]
        if selected:
            return selected[:top_k]

    session_texts = []
    for index, session_id in enumerate(example.haystack_session_ids):
        summary = example.haystack_session_summaries[index] if index < len(example.haystack_session_summaries) else ""
        transcript = session_to_markdown(example.haystack_sessions[index])
        session_texts.append(f"{session_id}\n{summary}\n{transcript}")

    scores = _bm25_scores(content_tokens(example.question), [content_tokens(text) for text in session_texts])
    ranked = sorted(enumerate(scores), key=lambda item: (-item[1], item[0]))
    return sorted(index for index, _ in ranked[: min(top_k, len(ranked))])


def _bm25_scores(query_tokens: list[str], documents: list[list[str]], k1: float = 1.5, b: float = 0.75) -> list[float]:
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
