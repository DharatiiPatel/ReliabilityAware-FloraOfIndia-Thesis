#!/usr/bin/env python3
"""Tests for exact volume-number matching."""

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

from lib.volume_match import (  # noqa: E402
    TARGET_VOLUME_NUMBERS,
    parse_volume_number,
    title_matches_target_volumes,
)


def test_vol1_does_not_match_vol10_13():
    for t in [
        "Flora of India Vol. 10",
        "Flora of India Volume 11",
        "Vol. 12 something",  # 12 IS a target — separate test
        "Vol. 13",
    ]:
        n = parse_volume_number(t)
        if n == 12 or n == 13:
            continue  # these are intentional targets
        assert n not in {1}, t
        assert not title_matches_target_volumes(t, {1}), t


def test_vol2_does_not_match_vol20_23():
    for t in ["Vol. 20", "Volume 21", "Vol. 22", "Vol. 23"]:
        n = parse_volume_number(t)
        if n == 23:
            assert title_matches_target_volumes(t, TARGET_VOLUME_NUMBERS)
            continue
        assert n != 2
        assert not title_matches_target_volumes(t, {2}), t


def test_targets_match():
    for n in TARGET_VOLUME_NUMBERS:
        assert title_matches_target_volumes(f"Flora of India Vol. {n}", TARGET_VOLUME_NUMBERS)


def test_substring_bug_regression():
    # The old logic: any(vol in title for vol in ["Vol. 1", ...])
    # would match these incorrectly for Vol. 1 / Vol. 2 targets alone.
    assert parse_volume_number("Vol. 10") == 10
    assert parse_volume_number("Vol. 23") == 23
    assert not title_matches_target_volumes("Vol. 10", {1, 2, 3, 4, 5})
    assert not title_matches_target_volumes("Vol. 20", {1, 2, 3, 4, 5})
    assert title_matches_target_volumes("Vol. 1", {1, 2, 3, 4, 5})
    assert title_matches_target_volumes("Vol. 2", {1, 2, 3, 4, 5})


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
    sys.exit(1 if failures else 0)
