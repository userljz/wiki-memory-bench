"""Full-context baselines."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter

from wiki_memory_bench.schemas import Citation, PreparedExample, RetrievedItem, SystemResult, TaskType, TokenUsage
from wiki_memory_bench.systems.answering import build_answerer, build_open_qa_answerer
from wiki_memory_bench.systems.base import SystemAdapter, choice_index, choose_multiple_choice_answer, register_system
from wiki_memory_bench.utils.tokens import estimate_text_tokens, estimate_token_total


class _BaseFullContextBaseline(SystemAdapter):
    """Shared full-context behavior."""

    baseline_type = "heuristic_reference"

    def __init__(self, answerer: str = "deterministic", **_: object) -> None:
        self.answerer_mode = answerer
        self.answerer = build_answerer(answerer, task_name="mc-answerer")
        self.open_qa_answerer = build_open_qa_answerer(answerer, task_name="open-qa-answerer")

    def prepare_run(self, run_dir: Path, dataset_name: str) -> None:
        if hasattr(self.answerer, "set_artifact_dir"):
            self.answerer.set_artifact_dir(run_dir / "artifacts" / "llm" / "answerer")
        if hasattr(self.open_qa_answerer, "set_artifact_dir"):
            self.open_qa_answerer.set_artifact_dir(run_dir / "artifacts" / "llm" / "answerer")

    def _retrieved_items(self, example: PreparedExample) -> list[RetrievedItem]:
        ordered_clips = sorted(example.history_clips, key=lambda clip: clip.timestamp)
        return [
            RetrievedItem(
                clip_id=clip.clip_id,
                rank=index + 1,
                score=1.0,
                text=clip.text,
                retrieved_tokens=estimate_text_tokens(clip.text),
            )
            for index, clip in enumerate(ordered_clips)
        ]

    def _oracle_choice(self, example: PreparedExample):
        return example.choices[example.correct_choice_index]

    def _select_mc_answer(
        self,
        example: PreparedExample,
        ordered_clips,
        retrieved_items: list[RetrievedItem],
    ):
        lexical_choice, supporting_clip, confidence = choose_multiple_choice_answer(example, ordered_clips)
        if self.answerer_mode == "llm":
            selection = self.answerer.select_choice(example, retrieved_items)
            selected_choice = selection.choice
            if selection.supporting_item is not None:
                supporting_clip = next(
                    (clip for clip in ordered_clips if clip.clip_id == selection.supporting_item.clip_id),
                    supporting_clip,
                )
            confidence = selection.confidence
            llm_rationale = selection.rationale
            llm_usage = selection.token_usage
            selection_mode = "llm"
        else:
            selected_choice, supporting_clip, confidence, llm_rationale, llm_usage, selection_mode = self._deterministic_mc(
                example,
                lexical_choice,
                supporting_clip,
                confidence,
            )

        return lexical_choice, selected_choice, supporting_clip, confidence, llm_rationale, llm_usage, selection_mode

    def _deterministic_mc(self, example, lexical_choice, supporting_clip, confidence):
        raise NotImplementedError

    def run(self, example: PreparedExample) -> SystemResult:
        started = perf_counter()
        ordered_clips = sorted(example.history_clips, key=lambda clip: clip.timestamp)
        retrieved_items = self._retrieved_items(example)
        citations = []

        if example.task_type == TaskType.MULTIPLE_CHOICE:
            lexical_choice, selected_choice, supporting_clip, confidence, llm_rationale, llm_usage, selection_mode = self._select_mc_answer(
                example,
                ordered_clips,
                retrieved_items,
            )

            if supporting_clip is not None:
                citations.append(
                    Citation(
                        clip_id=supporting_clip.clip_id,
                        source_ref=supporting_clip.source_ref,
                        quote=supporting_clip.text,
                    )
                )

            input_tokens = estimate_token_total(
                [clip.text for clip in ordered_clips] + [example.question] + [choice.text for choice in example.choices]
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
                    input_tokens=llm_usage.input_tokens or input_tokens,
                    output_tokens=llm_usage.output_tokens or output_tokens,
                    estimated_cost_usd=llm_usage.estimated_cost_usd,
                ),
                latency_ms=latency_ms,
                metadata={
                    "confidence": round(confidence, 4),
                    "context_size": len(ordered_clips),
                    "selection_mode": selection_mode,
                    "baseline_type": self.baseline_type,
                    "lexical_fallback_choice": lexical_choice.choice_id,
                    "llm_rationale": llm_rationale,
                    "retrieval_top_k": len(retrieved_items),
                },
            )

        selection = self.open_qa_answerer.answer_question(example, retrieved_items)
        if selection.supporting_item is not None:
            supporting_clip = next((clip for clip in ordered_clips if clip.clip_id == selection.supporting_item.clip_id), None)
            if supporting_clip is not None:
                citations.append(
                    Citation(
                        clip_id=supporting_clip.clip_id,
                        source_ref=supporting_clip.source_ref,
                        quote=supporting_clip.text,
                    )
                )

        input_tokens = estimate_token_total([clip.text for clip in ordered_clips] + [example.question])
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
                "context_size": len(ordered_clips),
                "answerer_mode": self.answerer_mode,
                "baseline_type": self.baseline_type,
                "llm_rationale": selection.rationale,
                "retrieval_top_k": len(retrieved_items),
                **selection.metadata,
            },
        )


@register_system
class FullContextOracleBaseline(_BaseFullContextBaseline):
    """Oracle upper-bound full-context baseline."""

    name = "full-context-oracle"
    description = "Full-context sanity upper bound. Deterministic mode uses the gold answer and is not a fair deployable baseline."
    baseline_type = "oracle_upper_bound"

    def _deterministic_mc(self, example, lexical_choice, supporting_clip, confidence):
        return self._oracle_choice(example), supporting_clip, confidence, None, TokenUsage(), "oracle"


@register_system
class FullContextHeuristicBaseline(_BaseFullContextBaseline):
    """Non-oracle full-context heuristic baseline."""

    name = "full-context-heuristic"
    description = "Full-context heuristic baseline using the same deterministic answerer family as retrieval baselines."
    baseline_type = "heuristic_reference"

    def _deterministic_mc(self, example, lexical_choice, supporting_clip, confidence):
        return lexical_choice, supporting_clip, confidence, None, TokenUsage(), "heuristic"


# Backward-compatible import alias for older code paths.
FullContextBaseline = FullContextOracleBaseline
