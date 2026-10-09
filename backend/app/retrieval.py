"""Finding the passages that can answer a question.

Plain BM25 over a small knowledge base: no embeddings, no extra service, no cost.
A clinic's FAQ is a few dozen paragraphs, so this is fast and easy to reason about.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

STOPWORDS = frozenset(
    """a about an and any are as at be been but by can could do does for from had has have how i if in into
    is it its me my of on or our so than that the their them then there these they this to up us was we were
    what when where which who why will with would you your please hi hello thanks thank""".split()
)

_WORD = re.compile(r"[a-z0-9£]+")


def stem(word: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def tokenize(text: str) -> list[str]:
    return [stem(w) for w in _WORD.findall(text.lower()) if w not in STOPWORDS]


def chunk(text: str, max_chars: int = 600) -> list[str]:
    """Split on blank lines, merge short paragraphs, break long ones at sentence ends."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    pieces: list[str] = []
    for paragraph in paragraphs:
        if len(paragraph) <= max_chars:
            pieces.append(paragraph)
            continue
        current = ""
        for sentence in re.split(r"(?<=[.!?])\s+", paragraph):
            if current and len(current) + len(sentence) + 1 > max_chars:
                pieces.append(current)
                current = sentence
            else:
                current = f"{current} {sentence}".strip()
        if current:
            pieces.append(current)
    merged: list[str] = []
    for piece in pieces:
        if merged and len(merged[-1]) + len(piece) + 2 <= max_chars // 2:
            merged[-1] = f"{merged[-1]}\n\n{piece}"
        else:
            merged.append(piece)
    return merged


@dataclass(frozen=True)
class PassageRecord:
    id: str
    title: str
    text: str


@dataclass(frozen=True)
class Hit:
    id: str
    title: str
    text: str
    score: float
    # Share of the question's distinct words that this passage contains.
    coverage: float


def search(query: str, passages: list[PassageRecord], k: int = 4) -> list[Hit]:
    terms = list(dict.fromkeys(tokenize(query)))
    if not terms or not passages:
        return []
    docs = [Counter(tokenize(f"{p.title} {p.text}")) for p in passages]
    lengths = [sum(d.values()) or 1 for d in docs]
    average = sum(lengths) / len(lengths)
    n = len(passages)
    k1, b = 1.5, 0.75
    hits: list[Hit] = []
    for passage, counts, length in zip(passages, docs, lengths, strict=True):
        score = 0.0
        matched = 0
        for term in terms:
            tf = counts.get(term, 0)
            if not tf:
                continue
            matched += 1
            df = sum(1 for d in docs if term in d)
            idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
            score += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * length / average))
        if score > 0:
            hits.append(Hit(passage.id, passage.title, passage.text, score, matched / len(terms)))
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:k]
