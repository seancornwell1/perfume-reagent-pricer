"""Decide whether a product title is the reagent we're looking for."""
import re
from typing import Optional

from .models import Reagent

_GREEK = {"α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta", "ε": "epsilon"}
_PREFIX = {"a": "alpha", "b": "beta", "g": "gamma", "d": "delta"}
_ISOMER_WORDS = {"alpha", "beta", "gamma", "delta", "epsilon"}


def normalize(text: str) -> str:
    t = (text or "").lower()
    for k, v in _GREEK.items():
        t = t.replace(k, f" {v} ")
    # "b-ionone" -> "beta ionone", "d-decalactone" -> "delta decalactone"
    t = re.sub(r"(?<![a-z0-9])([abgd])-(?=[a-z])", lambda m: _PREFIX[m.group(1)] + " ", t)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return " ".join(t.split())


def _has_phrase(norm_text: str, phrase: str) -> bool:
    p = normalize(phrase)
    return bool(p) and re.search(rf"(?<![a-z0-9]){re.escape(p)}(?![a-z0-9])", norm_text) is not None


def match(reagent: Reagent, title: str) -> Optional[str]:
    """Return a short reason if title matches reagent, else None."""
    raw = title or ""
    norm = normalize(raw)
    tokens = set(norm.split())

    for ex in reagent.exclude:
        if _has_phrase(norm, ex):
            return None

    for cas in reagent.cas:
        if cas in raw:
            return f"CAS {cas}"

    for syn in [reagent.name] + reagent.synonyms:
        syn_tokens = normalize(syn).split()
        if not syn_tokens or not set(syn_tokens) <= tokens:
            continue
        # Short synonyms (e.g. "aag") must appear as a whole word, which the token check ensures.
        # Reject other isomers: "alpha beta ionone" or "gamma decalactone".
        extra_isomers = (tokens & _ISOMER_WORDS) - set(syn_tokens)
        if extra_isomers:
            continue
        return f"name '{syn}'"
    return None
