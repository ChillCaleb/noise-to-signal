from __future__ import annotations

import math
import re
from collections import Counter
from difflib import SequenceMatcher
from typing import Dict, List

from rapidfuzz import fuzz


TOKEN_RE = re.compile(r"[a-zA-Z0-9']+")


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _tokenize(text: str) -> List[str]:
    return TOKEN_RE.findall(_normalize(text))


def _cosine_similarity(a: str, b: str) -> float:
    counts_a = Counter(_tokenize(a))
    counts_b = Counter(_tokenize(b))
    if not counts_a or not counts_b:
        return 0.0
    shared = set(counts_a) & set(counts_b)
    numerator = sum(counts_a[token] * counts_b[token] for token in shared)
    norm_a = math.sqrt(sum(value * value for value in counts_a.values()))
    norm_b = math.sqrt(sum(value * value for value in counts_b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return numerator / (norm_a * norm_b)


def score_stability(outputs: List[str]) -> Dict[str, object]:
    if not outputs:
        return {
            "runs": 0,
            "exact_match_rate": None,
            "mean_fuzzy_ratio": None,
            "mean_sequence_similarity": None,
            "mean_vector_cosine": None,
        }

    if len(outputs) == 1:
        return {
            "runs": 1,
            "exact_match_rate": 1.0,
            "mean_fuzzy_ratio": 100.0,
            "mean_sequence_similarity": 1.0,
            "mean_vector_cosine": 1.0,
            "unique_outputs": 1,
            "outputs_preview": outputs,
        }

    normalized = [_normalize(text) for text in outputs]
    total_pairs = 0
    exact_matches = 0
    fuzzy_total = 0.0
    sequence_total = 0.0
    cosine_total = 0.0

    for left in range(len(outputs)):
        for right in range(left + 1, len(outputs)):
            total_pairs += 1
            a = normalized[left]
            b = normalized[right]
            if a == b:
                exact_matches += 1
            fuzzy_total += fuzz.ratio(a, b)
            sequence_total += SequenceMatcher(None, a, b).ratio()
            cosine_total += _cosine_similarity(a, b)

    return {
        "runs": len(outputs),
        "unique_outputs": len(set(normalized)),
        "exact_match_rate": exact_matches / total_pairs if total_pairs else None,
        "mean_fuzzy_ratio": fuzzy_total / total_pairs if total_pairs else None,
        "mean_sequence_similarity": sequence_total / total_pairs if total_pairs else None,
        "mean_vector_cosine": cosine_total / total_pairs if total_pairs else None,
        "outputs_preview": outputs[:3],
    }
