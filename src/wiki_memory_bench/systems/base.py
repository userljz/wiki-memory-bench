"""System adapter interfaces, registry, and shared multiple-choice helpers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from wiki_memory_bench.schemas import ChoiceOption, HistoryClip, PreparedExample, SystemResult
from wiki_memory_bench.utils.tokens import content_tokens, normalize_text

SYSTEM_REGISTRY: dict[str, type["SystemAdapter"]] = {}
SYSTEM_ALIASES: dict[str, str] = {"full-context": "full-context-oracle"}
ABSTENTION_MARKERS = ("not enough information", "insufficient information", "unknown", "not answerable")
NON_ORACLE_LABEL = "non-oracle"
ORACLE_UPPER_BOUND_LABEL = "oracle-upper-bound"


class SystemAdapter(ABC):
    """Abstract benchmark system."""

    name: ClassVar[str]
    description: ClassVar[str]

    def prepare_run(self, run_dir: Path, dataset_name: str) -> None:
        """Optional hook executed once before a benchmark run starts."""

    def finalize_run(self) -> None:
        """Optional hook executed once after a benchmark run finishes."""

    @abstractmethod
    def run(self, example: PreparedExample) -> SystemResult:
        """Run the system on a single prepared example."""


def register_system(system_class: type[SystemAdapter]) -> type[SystemAdapter]:
    """Register a system adapter class by public name."""

    SYSTEM_REGISTRY[system_class.name] = system_class
    return system_class


def get_system(name: str, **kwargs: object) -> SystemAdapter:
    """Instantiate a system adapter by name."""

    resolved_name = SYSTEM_ALIASES.get(name, name)
    try:
        system_class = SYSTEM_REGISTRY[resolved_name]
    except KeyError as error:
        available = ", ".join(sorted(SYSTEM_REGISTRY))
        raise KeyError(f"Unknown system '{name}'. Available systems: {available}") from error
    if kwargs:
        return system_class(**kwargs)
    return system_class()


def list_systems() -> list[SystemAdapter]:
    """Return system adapters sorted by name."""

    return [SYSTEM_REGISTRY[name]() for name in sorted(SYSTEM_REGISTRY)]


def fairness_metadata(
    *,
    uses_gold_labels: bool,
    gold_label_fields_used: list[str] | None = None,
    oracle_label: str | None = None,
) -> dict[str, object]:
    """Return the standard oracle/gold-label metadata for a system result."""

    fields = list(gold_label_fields_used or [])
    oracle_mode = bool(uses_gold_labels)
    return {
        "uses_gold_labels": oracle_mode,
        "oracle_mode": oracle_mode,
        "oracle_label": oracle_label or (ORACLE_UPPER_BOUND_LABEL if oracle_mode else NON_ORACLE_LABEL),
        "gold_label_fields_used": fields if oracle_mode else [],
    }


def non_oracle_fairness_metadata() -> dict[str, object]:
    """Return standard metadata for systems that do not use gold labels."""

    return fairness_metadata(uses_gold_labels=False)


def is_abstention_choice(choice: ChoiceOption) -> bool:
    """Return true when a choice represents abstention."""

    normalized = normalize_text(choice.text)
    return any(marker in normalized for marker in ABSTENTION_MARKERS)


def choice_index(example: PreparedExample, choice: ChoiceOption) -> int:
    """Return the zero-based index for a choice option."""

    return example.choices.index(choice)


def choose_multiple_choice_answer(
    example: PreparedExample,
    context_clips: list[HistoryClip],
) -> tuple[ChoiceOption, HistoryClip | None, float]:
    """Choose a multiple-choice answer using lexical overlap and recency.

    The heuristic is intentionally simple, local, and deterministic.
    """

    question_tokens = set(content_tokens(example.question))
    clip_positions = {clip.clip_id: index for index, clip in enumerate(context_clips or example.history_clips)}
    abstention_choice = next((choice for choice in example.choices if is_abstention_choice(choice)), None)

    best_choice = abstention_choice or example.choices[0]
    best_clip: HistoryClip | None = None
    best_score = 0.0

    for choice in example.choices:
        if is_abstention_choice(choice):
            continue

        choice_tokens = set(content_tokens(choice.text))
        normalized_choice = normalize_text(choice.text)

        for clip in context_clips:
            clip_tokens = set(content_tokens(clip.text))
            overlap = len(choice_tokens & clip_tokens)
            phrase_bonus = 3.0 if normalized_choice and normalized_choice in normalize_text(clip.text) else 0.0
            if overlap == 0 and phrase_bonus == 0.0:
                continue

            question_overlap = len(question_tokens & clip_tokens)
            recency_bonus = (clip_positions.get(clip.clip_id, 0) + 1) / max(1, len(context_clips))
            score = overlap * 2.0 + phrase_bonus + question_overlap * 0.35 + recency_bonus * 0.25

            if score > best_score:
                best_choice = choice
                best_clip = clip
                best_score = score

    if abstention_choice is not None and best_score < 2.0:
        return abstention_choice, None, best_score

    return best_choice, best_clip, best_score
