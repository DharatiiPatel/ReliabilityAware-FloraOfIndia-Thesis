#!/usr/bin/env python3
"""
V2 categoriser (shared module).

TERMINOLOGY
-----------
- V1: original categoriser (scripts/03_04_Categorize_and_Prepare.py). Unchanged.
- V2: this module — categoriser used for label sensitivity and reliability
      within the existing 1,438-species primary cohort.

Active scripts should import via scripts/14_Categorize_v2.py.

DISCLOSURE
----------
V2 is not externally validated. It was developed after inspection of the
existing gold set and known V1 failure modes. Benchmark numbers that use
the same gold set are method-development evaluation, not independent
external validation.

METADATA
--------
Downstream outputs should record:
  categorizer_name, categorizer_version, categorizer_sha256, primary_anchor_n
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Union

CATEGORIZER_NAME = "V2"
CATEGORIZER_VERSION = 2
# Back-compat string alias used in a few older callers
V2_VERSION = CATEGORIZER_VERSION
V2_MODULE_PATH = Path(__file__).resolve()

# ---------------------------------------------------------------------------
# Machine-readable ontology (analytical groupings, not botanical universals)
# ---------------------------------------------------------------------------
V2_ONTOLOGY: Dict[str, Any] = {
    "categorizer_name": CATEGORIZER_NAME,
    "categorizer_version": CATEGORIZER_VERSION,
    "analysis_classes": ["WHITE", "YELLOW", "REDTYPE", "UNKNOWN", "OTHER"],
    "multicolour_rule": (
        "After compound normalisation, the first left-to-right recognised "
        "colour expression wins (lead pigment). No global WHITE/YELLOW "
        "priority over REDTYPE."
    ),
    "analytical_groupings": {
        "plain_orange": "YELLOW",
        "cream_cream_coloured": "YELLOW",
        "cream_white": "WHITE",
        "green_greenish": "OTHER",
        "buff_brown_flesh": "OTHER",
    },
    "redtype_terms": [
        "red", "reddish", "scarlet", "crimson", "pink", "pinkish",
        "purple", "purplish", "violet", "blue", "bluish", "maroon",
        "magenta", "rose", "coral",
    ],
    "redtype_compounds": [
        "orange-red", "orange red", "reddish-orange", "red-orange",
        "orange-scarlet", "scarlet-orange", "brick-red",
        "coral-pink", "coral-red", "rose-coloured", "rose-colored",
    ],
    "unknown_triggers": [
        "blank", "no flower colour/color mentioned", "uncertain",
        "unknown", "not mentioned", "flower colour/color not mentioned",
    ],
}

KNOWN_ECOLOGY = frozenset({"WHITE", "YELLOW", "REDTYPE"})


@dataclass
class V2Result:
    analysis_class: str
    fine_category: str
    matched_expression: str
    rule: str
    categorizer_name: str = CATEGORIZER_NAME
    categorizer_version: int = CATEGORIZER_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# --- abstention / UNKNOWN -------------------------------------------------
_ABSTAIN_PATTERNS = [
    (re.compile(r"no\s+flower\s+colou?r(?:\s+mentioned)?", re.I),
     "abstain:no_flower_colour"),
    (re.compile(r"flower\s+colou?r\s+not\s+mentioned", re.I),
     "abstain:flower_colour_not_mentioned"),
    (re.compile(r"(?:^|[^a-z])uncertain(?:[^a-z]|$)", re.I),
     "abstain:uncertain"),
    (re.compile(r"(?:^|[^a-z])unknown(?:[^a-z]|$)", re.I),
     "abstain:unknown"),
    (re.compile(r"\bnot\s+mentioned\b", re.I),
     "abstain:not_mentioned"),
]

# --- compound rewrites (applied before first-mention search) --------------
# Each: (regex, replacement_token, rule_id)
# Replacement tokens are canonical colour words already in COLOUR_PATTERNS.
_COMPOUND_RULES = [
    # Red–orange family → scarlet (REDTYPE)
    (re.compile(
        r"\b(?:orange[\s\-]+scarlet|scarlet[\s\-]+orange|"
        r"orange[\s\-]+red(?:dish)?|red(?:dish)?[\s\-]+orange|"
        r"brick[\s\-]+red|coral[\s\-]+pink|coral[\s\-]+red)\b",
        re.I), "scarlet", "compound:orange_red_family"),
    # Rose as colour (rose-coloured / rose colored / rose petals handled via rose token)
    (re.compile(r"\brose[\s\-]?colou?red\b", re.I), "rose", "compound:rose_coloured"),
    # Modifier + white → white
    (re.compile(
        r"\b(?:greenish|yellowish|creamy|cream|greyish|grayish|bluish|pinkish|"
        r"purplish|reddish|pale|dull|bright|dirty)[\s\-]+white\b",
        re.I), "white", "compound:modifier_white"),
    # Modifier + yellow → yellow
    (re.compile(
        r"\b(?:greenish|creamy|cream|pale|dull|bright|dirty)[\s\-]+yellow\b",
        re.I), "yellow", "compound:modifier_yellow"),
    # cream / cream-coloured → yellow (analytical ontology)
    (re.compile(r"\bcream(?:[\s\-]?colou?red)?\b", re.I),
     "yellow", "ontology:cream_to_yellow"),
]

_BARE_ORANGE = re.compile(r"\borange\b", re.I)

# Fine patterns for first left-to-right match (after compounds).
# More specific forms listed so same-start ties prefer them via alternation order
# inside each regex; across groups, earliest span wins.
COLOUR_PATTERNS = [
    (r"whitish|\bwhite\b", "WHITE", "term:white"),
    (r"yellowish|\byellow\b|\bgolden\b", "YELLOW", "term:yellow"),
    (r"pinkish|\bpink\b", "PINK", "term:pink"),
    (r"scarlet|\bcrimson\b|\breddish\b|\bmaroon\b|\bmagenta\b|\brose\b|\bcoral\b|\bred\b",
     "RED", "term:red_family"),
    (r"purplish|\bpurple\b|\bviolet\b|\bbluish\b|\bblue\b", "PURPLE/BLUE",
     "term:purple_blue"),
    (r"\borange\b", "YELLOW", "ontology:plain_orange_to_yellow"),
    (r"greenish|\bgreen\b", "GREEN", "term:green"),
    (r"\bbuff\b|\bbrown\b|\bflesh\b", "OTHER_FINE", "term:buff_brown_flesh"),
]

_COMBINED = re.compile(
    "|".join(f"(?P<c{i}>{pat})" for i, (pat, _, __) in enumerate(COLOUR_PATTERNS)),
    re.I,
)


def module_sha256() -> str:
    data = V2_MODULE_PATH.read_bytes()
    return hashlib.sha256(data).hexdigest()


def _apply_compounds(tl: str) -> tuple[str, list[str]]:
    applied = []
    for rx, repl, rule_id in _COMPOUND_RULES:
        if rx.search(tl):
            tl = rx.sub(repl, tl)
            applied.append(rule_id)
    # Plain orange → yellow ONLY after red-orange compounds handled
    if _BARE_ORANGE.search(tl):
        tl = _BARE_ORANGE.sub("yellow", tl)
        applied.append("ontology:plain_orange_to_yellow")
    return tl, applied


def categorize_v2(
    free_text: Optional[str],
    *,
    return_audit: bool = False,
) -> Union[str, V2Result]:
    """
    V2 categoriser.

    Returns analysis class string by default, or V2Result if return_audit=True.
    Never mutates the caller's stored free text.
    """
    if free_text is None or not str(free_text).strip():
        res = V2Result("UNKNOWN", "UNKNOWN", "", "abstain:blank")
        return res if return_audit else res.analysis_class

    raw = str(free_text).strip()
    tl = re.sub(r"\s+", " ", raw.lower())

    for rx, rule_id in _ABSTAIN_PATTERNS:
        if rx.search(tl):
            res = V2Result("UNKNOWN", "UNKNOWN", rx.pattern, rule_id)
            return res if return_audit else res.analysis_class

    tl, compound_rules = _apply_compounds(tl)
    m = _COMBINED.search(tl)
    if not m:
        res = V2Result("OTHER", "OTHER", "", "fallback:no_colour_term")
        return res if return_audit else res.analysis_class

    fine = "OTHER_FINE"
    matched = ""
    term_rule = "fallback"
    for i, (_, cat, rule_id) in enumerate(COLOUR_PATTERNS):
        g = m.group(f"c{i}")
        if g:
            fine = cat
            matched = g
            term_rule = rule_id
            break

    analysis = to_analysis_class(fine)
    rule = "+".join(compound_rules + [term_rule]) if compound_rules else term_rule
    res = V2Result(analysis, fine, matched, rule)
    return res if return_audit else res.analysis_class


def to_analysis_class(fine_category: str) -> str:
    """Map fine category → WHITE/YELLOW/REDTYPE/UNKNOWN/OTHER."""
    f = (fine_category or "").strip().upper().replace(" ", "")
    if f == "WHITE":
        return "WHITE"
    if f == "YELLOW":
        return "YELLOW"
    if f in {"RED", "PINK", "PURPLE/BLUE", "PURPLEBLUE", "REDTYPE"}:
        return "REDTYPE"
    if f == "UNKNOWN":
        return "UNKNOWN"
    # GREEN, GREENISH, OTHER_FINE, OTHER → OTHER
    return "OTHER"


def is_ecology_known(analysis_class: str) -> bool:
    return (analysis_class or "").upper() in KNOWN_ECOLOGY


# ---- aliases -------------------------------------------------------------
def categorize_fine(text: Optional[str]) -> str:
    r = categorize_v2(text, return_audit=True)
    assert isinstance(r, V2Result)
    return r.fine_category


def categorize_coarse(text: Optional[str]) -> str:
    return categorize_v2(text)  # analysis class


def to_coarse(fine: str) -> str:
    return to_analysis_class(fine)


# Historical name used in some scripts
categorize_color = categorize_coarse
