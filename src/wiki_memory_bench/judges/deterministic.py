"""Deterministic judge helpers."""

from __future__ import annotations


def judge_multiple_choice(selected_index: int | None, correct_index: int) -> tuple[int, str]:
    """Return a binary score and short reason for multiple-choice tasks."""

    if selected_index == correct_index:
        return 1, "Selected choice matches the gold choice index."
    return 0, "Selected choice does not match the gold choice index."
