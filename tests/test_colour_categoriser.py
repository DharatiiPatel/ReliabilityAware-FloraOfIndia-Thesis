#!/usr/bin/env python3
"""Unit tests for final frozen V2 flower-colour categoriser.

Run:
  python tests/test_colour_categoriser.py
"""

from __future__ import annotations

import sys
from pathlib import Path

def _repo_root() -> Path:
    import os
    env = os.environ.get("THESIS_ROOT")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parents[1]


ROOT = _repo_root()
sys.path.insert(0, str(ROOT / "scripts"))

from lib.colour_categoriser import (  # noqa: E402
    CATEGORIZER_VERSION,
    V2_VERSION,
    categorize_v2,
    is_ecology_known,
    to_analysis_class,
)

REDTYPE = [
    "flowers red",
    "flowers reddish",
    "flowers scarlet",
    "flowers crimson",
    "petals pink",
    "flowers purple",
    "petals violet",
    "flowers blue",
    "petals maroon coloured",
    "flowers rose-coloured",
    "flowers magenta",
    "flowers coral-pink",
    "petals orange-red",
    "petals orange red",
    "petals reddish-orange",
    "petals red-orange",
    "petals brick-red",
]

NOT_REDTYPE_SUBSTRING = [
    ("cream-coloured flowers", "YELLOW"),
    ("buff-coloured flowers", "OTHER"),
    ("brightly coloured nerves", "OTHER"),
    ("leaves covered with hairs", "OTHER"),
    ("reduced petals", "OTHER"),
]

WHITE = [
    "flowers white",
    "flowers whitish",
    "greenish-white corolla",
    "cream-white petals",
]

YELLOW = [
    "flowers yellow",
    "flowers golden",
    "flowers cream-coloured",
    "flowers plain orange",
    "flowers orange",
]

UNKNOWN = [
    "",
    "no flower colour mentioned",
    "no flower color mentioned",
    "uncertain",
    "unknown",
    "flower colour not mentioned",
]

OTHER = [
    "flowers green",
    "flowers buff-coloured",
    "flowers brown",
    "flowers flesh-coloured",
]

# Multicolour: first recognised colour after compound normalisation.
MULTICOLOUR = [
    # scarlet before yellow → REDTYPE
    ("flowers brilliant scarlet, yellow in centre", "REDTYPE",
     "scarlet is first recognised colour"),
    # white before purple → WHITE
    ("flowers white with purple centre", "WHITE",
     "white is first recognised colour"),
    # pinkish before white → REDTYPE
    ("flowers pinkish or white", "REDTYPE",
     "pinkish is first recognised colour"),
    # yellow before purple → YELLOW
    ("flowers yellow with deep purple centre", "YELLOW",
     "yellow is first recognised colour"),
    # orange-red compound → scarlet token first → REDTYPE
    ("flowers orange-red or golden-yellow", "REDTYPE",
     "orange-red compound normalised before golden-yellow"),
    # pale orange → yellow ontology, precedes orange-red → YELLOW
    ("flowers pale orange, petals orange-red", "YELLOW",
     "plain/pale orange maps to YELLOW and appears before orange-red"),
]

KNOWN_FAILURES = [
    ("capitula orange-red", "REDTYPE"),  # Gynura nitida
    ("flowers pale orange, petals orange-red", "YELLOW"),  # Fissistigma poiyanthum
    ("petals maroon coloured", "REDTYPE"),  # Byttneria herbacea
    ("flowers rose-coloured", "REDTYPE"),  # Silene colorata
    ("flowers coral-pink, brick-red, orange-red, or yellowish", "REDTYPE"),  # Capparis
    ("flowers purple or bright orange-red with violet-pink or darker tips", "REDTYPE"),  # Corydalis
    ("flesh-coloured", "OTHER"),  # Uvaria narum — do not force REDTYPE
]


def _c(text: str) -> str:
    return categorize_v2(text)


def test_version():
    assert CATEGORIZER_VERSION == 2
    assert V2_VERSION == 2


def test_redtype():
    for t in REDTYPE:
        assert _c(t) == "REDTYPE", t


def test_not_substring_red():
    for t, exp in NOT_REDTYPE_SUBSTRING:
        got = _c(t)
        assert got == exp, f"{t!r}: got {got}, expected {exp}"
        assert got != "REDTYPE" or exp == "REDTYPE"


def test_white():
    for t in WHITE:
        assert _c(t) == "WHITE", t


def test_yellow():
    for t in YELLOW:
        assert _c(t) == "YELLOW", t


def test_unknown():
    for t in UNKNOWN:
        assert _c(t) == "UNKNOWN", repr(t)


def test_other():
    for t in OTHER:
        assert _c(t) == "OTHER", t


def test_multicolour():
    for t, exp, _why in MULTICOLOUR:
        got = _c(t)
        assert got == exp, f"{t!r}: got {got}, expected {exp}"


def test_known_failures():
    for t, exp in KNOWN_FAILURES:
        got = _c(t)
        assert got == exp, f"{t!r}: got {got}, expected {exp}"


def test_audit_and_determinism():
    t = "petals orange-red"
    a = categorize_v2(t, return_audit=True)
    b = categorize_v2(t, return_audit=True)
    assert a.analysis_class == b.analysis_class == "REDTYPE"
    assert a.matched_expression
    assert a.rule
    assert a.categorizer_version == CATEGORIZER_VERSION
    assert a.categorizer_name == "V2"


def test_ecology_known():
    assert is_ecology_known("WHITE")
    assert not is_ecology_known("UNKNOWN")
    assert not is_ecology_known("OTHER")
    assert to_analysis_class("GREEN") == "OTHER"
    assert to_analysis_class("PINK") == "REDTYPE"


def test_infrared_not_red():
    assert _c("infrared imaging") == "OTHER"


if __name__ == "__main__":
    failures = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS  {name}")
            except AssertionError as e:
                failures += 1
                print(f"FAIL  {name}: {e}")
    if failures:
        print(f"\n{failures} failed")
        sys.exit(1)
    print(f"\nAll V2 tests passed (categorizer_version={CATEGORIZER_VERSION}).")
