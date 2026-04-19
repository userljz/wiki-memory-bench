"""Optional Basic Memory adapter with CLI detection and file-compatible fallback."""

from __future__ import annotations

import json
import math
import shutil
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from wiki_memory_bench.schemas import Citation, PreparedExample, RetrievedItem, SystemResult, TaskType, TokenUsage
from wiki_memory_bench.systems.answering import build_answerer, build_open_qa_answerer
from wiki_memory_bench.systems.base import SystemAdapter, choice_index, register_system
from wiki_memory_bench.systems.retrieval import build_session_documents
from wiki_memory_bench.utils.tokens import content_tokens, estimate_text_tokens, estimate_token_total


@dataclass(slots=True)
class BasicMemoryStatus:
    """Detected Basic Memory CLI status."""

    available: bool
    command: str | None
    version: str | None
    tested_version: str
    mode: str
    limitations: list[str]


@dataclass(slots=True)
class BasicMemoryNote:
    """Local note artifact used by the adapter."""

    note_id: str
    title: str
    permalink: str
    file_path: Path
    content: str
    source_ids: list[str]


def detect_basic_memory_cli() -> BasicMemoryStatus:
    """Detect whether Basic Memory CLI is installed and usable."""

    tested_version = "basic-memory v0.19.x CLI contract"
    limitations = [
        "The adapter writes Basic Memory-compatible markdown notes first and falls back to local lexical retrieval if CLI search fails.",
        "The adapter does not require the MCP server; it currently uses the CLI if available.",
        "Basic Memory upstream documents Python 3.12+ for installation, so availability may vary by environment.",
    ]

    for command in ("bm", "basic-memory"):
        if shutil.which(command):
            version = None
            try:
                result = subprocess.run(
                    [command, "--version"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                version = (result.stdout or result.stderr).strip() or None
            except Exception:
                version = None
            return BasicMemoryStatus(
                available=True,
                command=command,
                version=version,
                tested_version=tested_version,
                mode="cli-enhanced-with-local-fallback",
                limitations=limitations,
            )

    return BasicMemoryStatus(
        available=False,
        command=None,
        version=None,
        tested_version=tested_version,
        mode="file-compatible-local-fallback",
        limitations=limitations,
    )


def basic_memory_doctor_payload() -> dict[str, object]:
    """Return structured doctor information for the Basic Memory adapter."""

    status = detect_basic_memory_cli()
    return {
        "adapter": "basic-memory",
        "available": status.available,
        "command": status.command,
        "version": status.version,
        "tested_version": status.tested_version,
        "mode": status.mode,
        "install_command": "uv tool install basic-memory",
        "docs": "docs/basic-memory-adapter.md",
        "limitations": status.limitations,
    }


@register_system
class BasicMemoryAdapter(SystemAdapter):
    """Optional external adapter for Basic Memory."""

    name = "basic-memory"
    description = "Optional Basic Memory adapter using file-compatible notes with best-effort CLI sync/search."

    def __init__(self, answerer: str = "deterministic", top_k: int = 4, **_: object) -> None:
        self.answerer_mode = answerer
        self.top_k = top_k
        self.answerer = build_answerer(answerer, task_name="mc-answerer")
        self.open_qa_answerer = build_open_qa_answerer(answerer, task_name="open-qa-answerer")
        self.status = detect_basic_memory_cli()
        self._artifact_root: Path | None = None

    def prepare_run(self, run_dir: Path, dataset_name: str) -> None:
        self._artifact_root = run_dir / "artifacts" / "basic-memory"
        self._artifact_root.mkdir(parents=True, exist_ok=True)
        if hasattr(self.answerer, "set_artifact_dir"):
            self.answerer.set_artifact_dir(run_dir / "artifacts" / "llm" / "answerer")
        if hasattr(self.open_qa_answerer, "set_artifact_dir"):
            self.open_qa_answerer.set_artifact_dir(run_dir / "artifacts" / "llm" / "answerer")

    def run(self, example: PreparedExample) -> SystemResult:
        started = perf_counter()
        artifact_root = self._artifact_root or Path.cwd() / ".basic-memory-artifacts"
        example_dir = artifact_root / example.example_id
        project_dir = example_dir / "project"

        self.reset(project_dir)
        notes = self.ingest(example, project_dir)
        sync_result = self._sync_project(project_dir)
        retrieved_notes, retrieval_backend = self.retrieve(example.question, notes, project_dir)

        retrieved_items = [
            RetrievedItem(
                clip_id=note.note_id,
                rank=index + 1,
                score=score,
                text=note.content,
                retrieved_tokens=estimate_text_tokens(note.content),
            )
            for index, (note, score) in enumerate(retrieved_notes)
        ]

        citations: list[Citation] = []
        if example.task_type == TaskType.MULTIPLE_CHOICE:
            selection = self.answerer.select_choice(example, retrieved_items)
            selected_choice = selection.choice
            citation_ids = set(selection.citation_ids or ([selection.supporting_item.clip_id] if selection.supporting_item is not None else []))
            for note, _ in retrieved_notes:
                if note.note_id in citation_ids:
                    citations.append(
                        Citation(
                            clip_id=note.note_id,
                            source_ref=",".join(note.source_ids),
                            quote=note.content,
                        )
                    )
            if not citations and selection.supporting_item is not None:
                note = next((candidate for candidate, _ in retrieved_notes if candidate.note_id == selection.supporting_item.clip_id), None)
                if note is not None:
                    citations.append(Citation(clip_id=note.note_id, source_ref=",".join(note.source_ids), quote=note.content))

            token_usage = TokenUsage(
                input_tokens=selection.token_usage.input_tokens or estimate_token_total(
                    [item.text for item in retrieved_items] + [example.question] + [choice.text for choice in example.choices]
                ),
                output_tokens=selection.token_usage.output_tokens or estimate_text_tokens(selected_choice.text),
                estimated_cost_usd=selection.token_usage.estimated_cost_usd,
            )
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
                token_usage=token_usage,
                latency_ms=latency_ms,
                metadata={
                    "confidence": round(selection.confidence, 4),
                    "retrieved_count": len(retrieved_items),
                    "retrieval_top_k": self.top_k,
                    "answerer_mode": self.answerer_mode,
                    "basic_memory_available": self.status.available,
                    "basic_memory_command": self.status.command,
                    "basic_memory_version": self.status.version,
                    "basic_memory_mode": self.status.mode,
                    "basic_memory_backend": retrieval_backend,
                    "basic_memory_sync_success": sync_result,
                    "basic_memory_project_dir": str(project_dir),
                    **selection.metadata,
                },
            )

        selection = self.open_qa_answerer.answer_question(example, retrieved_items)
        citation_ids = set(selection.citation_ids or ([selection.supporting_item.clip_id] if selection.supporting_item is not None else []))
        for note, _ in retrieved_notes:
            if note.note_id in citation_ids:
                citations.append(
                    Citation(
                        clip_id=note.note_id,
                        source_ref=",".join(note.source_ids),
                        quote=note.content,
                    )
                )
        if not citations and selection.supporting_item is not None:
            note = next((candidate for candidate, _ in retrieved_notes if candidate.note_id == selection.supporting_item.clip_id), None)
            if note is not None:
                citations.append(Citation(clip_id=note.note_id, source_ref=",".join(note.source_ids), quote=note.content))

        token_usage = TokenUsage(
            input_tokens=selection.token_usage.input_tokens or estimate_token_total([item.text for item in retrieved_items] + [example.question]),
            output_tokens=selection.token_usage.output_tokens or estimate_text_tokens(selection.answer_text),
            estimated_cost_usd=selection.token_usage.estimated_cost_usd,
        )
        latency_ms = (perf_counter() - started) * 1000.0
        return SystemResult(
            example_id=example.example_id,
            system_name=self.name,
            answer_text=selection.answer_text,
            citations=citations,
            retrieved_items=retrieved_items,
            token_usage=token_usage,
            latency_ms=latency_ms,
            metadata={
                "confidence": round(selection.confidence, 4),
                "retrieved_count": len(retrieved_items),
                "retrieval_top_k": self.top_k,
                "answerer_mode": self.answerer_mode,
                "basic_memory_available": self.status.available,
                "basic_memory_command": self.status.command,
                "basic_memory_version": self.status.version,
                "basic_memory_mode": self.status.mode,
                "basic_memory_backend": retrieval_backend,
                "basic_memory_sync_success": sync_result,
                "basic_memory_project_dir": str(project_dir),
                **selection.metadata,
            },
        )

    def reset(self, project_dir: Path) -> None:
        """Reset the per-example Basic Memory project directory."""

        if project_dir.exists():
            shutil.rmtree(project_dir)
        project_dir.mkdir(parents=True, exist_ok=True)

    def ingest(self, example: PreparedExample, project_dir: Path) -> list[BasicMemoryNote]:
        """Write Basic Memory-compatible markdown notes."""

        notes: list[BasicMemoryNote] = []
        sessions_dir = project_dir / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)

        retrieval_documents = build_session_documents(example)
        for document in retrieval_documents:
            note_slug = document.clip_id.replace(":", "-")
            title = f"Session {document.session_id} {document.metadata.get('doc_type', 'note')}"
            permalink = f"sessions/{note_slug}"
            note_path = sessions_dir / f"{note_slug}.md"
            content = self._build_note_content(title, permalink, example, document)
            note_path.write_text(content, encoding="utf-8")
            notes.append(
                BasicMemoryNote(
                    note_id=permalink,
                    title=title,
                    permalink=permalink,
                    file_path=note_path,
                    content=content,
                    source_ids=[document.session_id],
                )
            )

        index_path = project_dir / "index.md"
        index_path.write_text(
            "\n".join(
                [
                    "# Basic Memory Project Index",
                    "",
                    f"- Example: `{example.example_id}`",
                    "",
                    "## Notes",
                    *[f"- [[{note.permalink}]]" for note in notes],
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return notes

    def retrieve(self, query: str, notes: list[BasicMemoryNote], project_dir: Path) -> tuple[list[tuple[BasicMemoryNote, float]], str]:
        """Retrieve notes via Basic Memory CLI if available, otherwise local fallback."""

        if self.status.available and self.status.command is not None:
            cli_results = self._cli_search(query=query, notes=notes, project_dir=project_dir)
            if cli_results is not None:
                return cli_results, "basic-memory-cli"
        return self._local_search(query=query, notes=notes), "local-fallback"

    def _build_note_content(self, title: str, permalink: str, example: PreparedExample, document: object) -> str:
        tags = ["benchmark", "basic-memory", str(example.question_type or "unknown")]
        lines = [
            "---",
            f"title: {title}",
            "type: note",
            f"permalink: {permalink}",
            "tags:",
            *[f"- {tag}" for tag in tags],
            "---",
            "",
            f"# {title}",
            "",
            "## Observations",
            f"- [question] {example.question}",
            f"- [dataset] {example.dataset_name}",
            f"- [source] {document.source_ref or document.session_id}",
            "",
            "## Transcript",
            document.text,
            "",
        ]
        return "\n".join(lines)

    def _sync_project(self, project_dir: Path) -> bool:
        if not self.status.available or self.status.command is None:
            return False
        result = self._run_cli([self.status.command, "sync"], cwd=project_dir)
        return result.returncode == 0

    def _cli_search(
        self,
        *,
        query: str,
        notes: list[BasicMemoryNote],
        project_dir: Path,
    ) -> list[tuple[BasicMemoryNote, float]] | None:
        if self.status.command is None:
            return None
        result = self._run_cli(
            [self.status.command, "tool", "search-notes", query, "--page-size", str(self.top_k)],
            cwd=project_dir,
        )
        if result.returncode != 0:
            return None
        try:
            payload = json.loads(result.stdout.strip() or "{}")
        except json.JSONDecodeError:
            return None
        results = payload.get("results", [])
        note_by_permalink = {note.permalink: note for note in notes}
        note_by_path = {str(note.file_path.relative_to(project_dir)): note for note in notes}
        matched: list[tuple[BasicMemoryNote, float]] = []
        total = len(results) if results else 1
        for index, item in enumerate(results):
            permalink = item.get("permalink")
            file_path = item.get("file_path")
            note = note_by_permalink.get(permalink) or note_by_path.get(str(file_path))
            if note is not None:
                matched.append((note, float(total - index)))
        return matched or None

    def _local_search(self, *, query: str, notes: list[BasicMemoryNote]) -> list[tuple[BasicMemoryNote, float]]:
        documents = [content_tokens(note.content) for note in notes]
        scores = _bm25_scores(content_tokens(query), documents)
        ranked = sorted(
            zip(notes, scores, strict=True),
            key=lambda item: (-item[1], item[0].permalink),
        )
        return ranked[: self.top_k]

    def _run_cli(self, command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
        )


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
