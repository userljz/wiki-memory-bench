"""System registry exports."""

from wiki_memory_bench.systems.basic_memory import BasicMemoryAdapter
from wiki_memory_bench.systems.base import get_system, list_systems
from wiki_memory_bench.systems.bm25 import BM25Baseline
from wiki_memory_bench.systems.clipwiki import ClipWikiBaseline
from wiki_memory_bench.systems.full_context import FullContextBaseline
from wiki_memory_bench.systems.vector_rag import VectorRAGBaseline

__all__ = [
    "BasicMemoryAdapter",
    "BM25Baseline",
    "ClipWikiBaseline",
    "FullContextBaseline",
    "VectorRAGBaseline",
    "get_system",
    "list_systems",
]
