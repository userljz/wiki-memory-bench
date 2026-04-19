"""Deterministic text normalization and token estimation helpers."""

from __future__ import annotations

import re
from collections.abc import Iterable

WORD_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_\-]*")
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_\-]+|[^\w\s]")
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "my",
    "of",
    "on",
    "or",
    "our",
    "the",
    "this",
    "to",
    "what",
    "when",
    "which",
    "who",
    "with",
}


def normalize_text(text: str) -> str:
    """Normalize whitespace and casing for deterministic comparisons."""

    return " ".join(text.strip().lower().split())


def tokenize_words(text: str) -> list[str]:
    """Split text into lowercase lexical tokens."""

    return [token.lower() for token in WORD_PATTERN.findall(text)]


def content_tokens(text: str) -> list[str]:
    """Return lexical tokens with a small stopword list removed."""

    return [token for token in tokenize_words(text) if token not in STOPWORDS]


def estimate_text_tokens(text: str) -> int:
    """Estimate token count using regex token chunks.

    This is intentionally deterministic and local; it is not meant to match a
    provider tokenizer exactly.
    """

    parts = TOKEN_PATTERN.findall(text)
    return max(1, len(parts)) if text.strip() else 0


def estimate_token_total(texts: Iterable[str]) -> int:
    """Estimate the combined token count for multiple text fragments."""

    return sum(estimate_text_tokens(text) for text in texts)
