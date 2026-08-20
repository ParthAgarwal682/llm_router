"""Lightweight feature extraction for prompt complexity classification."""

from __future__ import annotations

import re

FEATURE_NAMES: list[str] = [
    "word_count",
    "char_count",
    "approx_token_count",
    "question_mark_count",
    "sentence_count",
    "avg_word_length",
    "analysis_word_count",
    "constraint_word_count",
    "code_word_count",
    "has_numbered_steps",
    "comma_count",
    "semicolon_count",
]

ANALYSIS_WORDS = {
    "analyze",
    "analyse",
    "compare",
    "contrast",
    "evaluate",
    "critique",
    "synthesize",
    "assess",
    "tradeoff",
    "tradeoffs",
    "recommend",
    "justify",
    "steelman",
    "debate",
}

CONSTRAINT_WORDS = {
    "must",
    "should",
    "exactly",
    "only",
    "require",
    "required",
    "constraints",
    "constraint",
    "format",
    "json",
    "cite",
    "criteria",
    "threshold",
    "thresholds",
    "under",
    "within",
    "limit",
}

CODE_WORDS = {
    "code",
    "function",
    "implement",
    "debug",
    "algorithm",
    "python",
    "api",
    "refactor",
    "database",
    "redis",
    "postgres",
    "rag",
}


def extract_features(prompt: str) -> list[float]:
    text = prompt.strip()
    lower = text.lower()
    words = re.findall(r"[a-z0-9']+", lower)
    word_count = len(words)
    char_count = len(text)
    # Rough token estimate used widely before a real tokenizer is needed
    approx_token_count = max(1, char_count // 4)
    question_mark_count = text.count("?")
    sentence_count = max(1, len(re.findall(r"[.!?]+", text)))
    avg_word_length = (sum(len(w) for w in words) / word_count) if words else 0.0

    analysis_word_count = sum(1 for w in words if w in ANALYSIS_WORDS)
    constraint_word_count = sum(1 for w in words if w in CONSTRAINT_WORDS)
    code_word_count = sum(1 for w in words if w in CODE_WORDS)
    has_numbered_steps = 1.0 if re.search(r"\b\d+[\.\)]\s|\b(first|second|third|then)\b", lower) else 0.0

    return [
        float(word_count),
        float(char_count),
        float(approx_token_count),
        float(question_mark_count),
        float(sentence_count),
        float(avg_word_length),
        float(analysis_word_count),
        float(constraint_word_count),
        float(code_word_count),
        has_numbered_steps,
        float(text.count(",")),
        float(text.count(";")),
    ]
