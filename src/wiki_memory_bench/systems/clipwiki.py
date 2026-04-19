"""Deterministic ClipWiki baseline."""

from __future__ import annotations

import tempfile
from pathlib import Path
from time import perf_counter

from wiki_memory_bench.clipwiki.compiler import compile_clipwiki, page_score_lookup, retrieve_wiki_pages
from wiki_memory_bench.schemas import Citation, PreparedExample, RetrievedItem, SystemResult, TaskType, TokenUsage
from wiki_memory_bench.systems.answering import build_answerer, build_open_qa_answerer
from wiki_memory_bench.systems.base import SystemAdapter, choice_index, register_system
from wiki_memory_bench.utils.tokens import estimate_text_tokens, estimate_token_total


@register_system
class ClipWikiBaseline(SystemAdapter):
    """Compile curated sessions into wiki pages and answer via page retrieval."""

    name = "clipwiki"
    description = "Compiles selected sessions into a deterministic markdown wiki and retrieves wiki pages with BM25."

    def __init__(
        self,
        mode: str = "full-wiki",
        retrieval_top_k: int = 4,
        noisy_extra_sessions: int = 2,
        answerer: str = "deterministic",
        **_: object,
    ) -> None:
        self.mode = mode
        self.retrieval_top_k = retrieval_top_k
        self.noisy_extra_sessions = noisy_extra_sessions
        self.answerer_mode = answerer
        self.answerer = build_answerer(answerer, task_name="mc-answerer")
        self.open_qa_answerer = build_open_qa_answerer(answerer, task_name="open-qa-answerer")
        self._wiki_root: Path | None = None

    def prepare_run(self, run_dir: Path, dataset_name: str) -> None:
        self._wiki_root = run_dir / "artifacts" / "wiki"
        self._wiki_root.mkdir(parents=True, exist_ok=True)
        if hasattr(self.answerer, "set_artifact_dir"):
            self.answerer.set_artifact_dir(run_dir / "artifacts" / "llm" / "answerer")
        if hasattr(self.open_qa_answerer, "set_artifact_dir"):
            self.open_qa_answerer.set_artifact_dir(run_dir / "artifacts" / "llm" / "answerer")

    def run(self, example: PreparedExample) -> SystemResult:
        started = perf_counter()
        wiki_root = self._wiki_root or Path(tempfile.mkdtemp(prefix="clipwiki-"))
        example_wiki_dir = wiki_root / example.example_id
        compiled_wiki = compile_clipwiki(
            example,
            output_dir=example_wiki_dir,
            mode=self.mode,
            noisy_extra_sessions=self.noisy_extra_sessions,
        )
        scores = page_score_lookup(example.question, compiled_wiki)
        retrieved_pages = retrieve_wiki_pages(example.question, compiled_wiki, top_k=self.retrieval_top_k)
        retrieved_items = [
            RetrievedItem(
                clip_id=page.page_id,
                rank=index + 1,
                score=float(scores.get(page.page_id, 0.0)),
                text=page.content,
                retrieved_tokens=estimate_text_tokens(page.content),
            )
            for index, page in enumerate(retrieved_pages)
        ]

        page_map = {page.page_id: page for page in compiled_wiki.pages}

        citations = []
        latency_ms = (perf_counter() - started) * 1000.0

        if example.task_type == TaskType.MULTIPLE_CHOICE:
            selection = self.answerer.select_choice(example, retrieved_items)
            selected_choice = selection.choice
            supporting_item = selection.supporting_item
            confidence = selection.confidence
            citation_ids = set(selection.citation_ids or ([supporting_item.clip_id] if supporting_item is not None else []))
            supporting_page = page_map.get(supporting_item.clip_id) if supporting_item is not None else None
            for page in retrieved_pages:
                if page.page_id in citation_ids:
                    citations.append(Citation(clip_id=page.page_id, source_ref=",".join(page.source_ids), quote=page.content))
            if not citations and supporting_page is not None:
                citations.append(Citation(clip_id=supporting_page.page_id, source_ref=",".join(supporting_page.source_ids), quote=supporting_page.content))

            input_tokens = estimate_token_total(
                [item.text for item in retrieved_items] + [example.question] + [choice.text for choice in example.choices]
            )
            output_tokens = estimate_text_tokens(selected_choice.text)
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
                wiki_size_pages=compiled_wiki.wiki_size_pages,
                wiki_size_tokens=compiled_wiki.wiki_size_tokens,
                latency_ms=latency_ms,
                metadata={
                    "confidence": round(confidence, 4),
                    "retrieved_count": len(retrieved_items),
                    "retrieval_top_k": self.retrieval_top_k,
                    "clipwiki_mode": self.mode,
                    "answerer_mode": self.answerer_mode,
                    "selected_session_ids": compiled_wiki.selected_session_ids,
                    "wiki_dir": str(example_wiki_dir),
                    **selection.metadata,
                },
            )

        selection = self.open_qa_answerer.answer_question(example, retrieved_items)
        supporting_item = selection.supporting_item
        confidence = selection.confidence
        citation_ids = set(selection.citation_ids or ([supporting_item.clip_id] if supporting_item is not None else []))
        supporting_page = page_map.get(supporting_item.clip_id) if supporting_item is not None else None
        for page in retrieved_pages:
            if page.page_id in citation_ids:
                citations.append(Citation(clip_id=page.page_id, source_ref=",".join(page.source_ids), quote=page.content))
        if not citations and supporting_page is not None:
            citations.append(Citation(clip_id=supporting_page.page_id, source_ref=",".join(supporting_page.source_ids), quote=supporting_page.content))

        input_tokens = estimate_token_total([item.text for item in retrieved_items] + [example.question])
        output_tokens = estimate_text_tokens(selection.answer_text)
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
            wiki_size_pages=compiled_wiki.wiki_size_pages,
            wiki_size_tokens=compiled_wiki.wiki_size_tokens,
            latency_ms=latency_ms,
            metadata={
                "confidence": round(confidence, 4),
                "retrieved_count": len(retrieved_items),
                "retrieval_top_k": self.retrieval_top_k,
                "clipwiki_mode": self.mode,
                "answerer_mode": self.answerer_mode,
                "selected_session_ids": compiled_wiki.selected_session_ids,
                "wiki_dir": str(example_wiki_dir),
                **selection.metadata,
            },
        )
