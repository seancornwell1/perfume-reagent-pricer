"""Parse pack sizes ("5 g", "1/2 oz", "10ml") and dilutions ("10% in DPG") from text."""
import re
from dataclasses import dataclass
from typing import Optional, Tuple

_MASS_G = {"mg": 0.001, "g": 1.0, "kg": 1000.0, "oz": 28.3495, "lb": 453.592}
_VOL_ML = {"ml": 1.0, "l": 1000.0, "floz": 29.5735, "dram": 3.6967}

_UNIT_ALIASES = [
    (r"fl\.?\s*oz", "floz"),
    (r"kgs?|kilos?|kilograms?", "kg"),
    (r"mg|milligrams?", "mg"),
    (r"grams?|gr|gms?|g", "g"),
    (r"ml|millilit(?:er|re)s?", "ml"),
    (r"lbs?|pounds?", "lb"),
    (r"oz|ounces?", "oz"),
    (r"drams?", "dram"),
    (r"lit(?:er|re)s?|l", "l"),
]
_NUM = r"(\d+\s*/\s*\d+|\d+(?:[.,]\d+)?)"
_SIZE_RE = re.compile(
    _NUM + r"\s*(" + "|".join(a for a, _ in _UNIT_ALIASES) + r")(?![a-z])", re.I
)


@dataclass
class Size:
    amount: float
    unit: str          # canonical unit key
    kind: str          # "mass" or "volume"
    text: str

    @property
    def grams(self) -> Optional[float]:
        return self.amount * _MASS_G[self.unit] if self.kind == "mass" else None

    @property
    def ml(self) -> Optional[float]:
        return self.amount * _VOL_ML[self.unit] if self.kind == "volume" else None


def _to_float(s: str) -> float:
    s = s.replace(" ", "")
    if "/" in s:
        a, b = s.split("/")
        return float(a) / float(b)
    return float(s.replace(",", "."))


def _canonical(unit_text: str) -> str:
    for pattern, key in _UNIT_ALIASES:
        if re.fullmatch(pattern, unit_text, re.I):
            return key
    raise ValueError(unit_text)


def parse_size(text: str) -> Optional[Size]:
    """Return the first pack size found in text, ignoring percentages."""
    if not text:
        return None
    for m in _SIZE_RE.finditer(text):
        # Skip "10% ..." style numbers and things like "5 g/mol"
        tail = text[m.end():m.end() + 1]
        if tail == "%":
            continue
        unit = _canonical(m.group(2))
        try:
            amount = _to_float(m.group(1))
        except (ValueError, ZeroDivisionError):
            continue
        if amount <= 0:
            continue
        kind = "volume" if unit in _VOL_ML else "mass"
        return Size(amount, unit, kind, m.group(0))
    return None


def pack_grams(size: Size, density: Optional[float]) -> Tuple[Optional[float], list]:
    """Convert a Size to grams of product. Returns (grams, flags)."""
    flags = []
    if size.kind == "mass":
        if size.unit == "oz":
            flags.append("'oz' assumed to be weight ounces")
        return size.grams, flags
    if density:
        flags.append(f"converted from {size.text} at density {density} g/mL")
        return size.ml * density, flags
    flags.append(f"volume pack ({size.text}) and no density set; assumed 1 g/mL")
    return size.ml, flags


_PCT_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")
_DILUTION_WORDS = re.compile(
    r"\b(dilut\w*|solution|soln|in\s+(?:dpg|tec|ipm|ipa|ethanol|alcohol|perfumer'?s?\s+alcohol|"
    r"benzyl\s+benzoate|bb|mct|jojoba|fractionated\s+coconut|carrier|tri\s*ethyl\s+citrate))\b",
    re.I,
)
_PURITY_WORDS = re.compile(r"\b(min\.?|minimum|purity|pure|assay|natural|nat)\b|[≥>]", re.I)


def parse_concentration(text: str) -> Tuple[Optional[float], bool]:
    """Return (fraction, is_dilution). fraction None means diluted at unknown strength.

    "10% in DPG" -> (0.1, True); "Ethylene brassylate 98%" -> (1.0, False);
    "1% solution" -> (0.01, True); "Damascone beta" -> (1.0, False).
    """
    text = text or ""
    has_words = bool(_DILUTION_WORDS.search(text))
    for m in _PCT_RE.finditer(text):
        pct = _to_float(m.group(1))
        if pct >= 100:
            continue
        before = text[max(0, m.start() - 12):m.start()]
        looks_like_purity = bool(_PURITY_WORDS.search(before)) or (pct >= 90 and not has_words)
        if looks_like_purity:
            continue
        if has_words or pct <= 50:
            return pct / 100.0, True
    if has_words:
        return None, True
    return 1.0, False
