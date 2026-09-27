#!/usr/bin/env python3
"""Unit test for corrected CATEGORY_PRIORITY logic."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

def _repo_root() -> Path:
    import os
    env = os.environ.get("THESIS_ROOT")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parents[1]


ROOT = _repo_root()
spec = importlib.util.spec_from_file_location(
    "err", ROOT / "scripts" / "13_Error_Taxonomy.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_clean_wrong_extraction_not_priority():
    # gold red, pred white — independent wrong answer, NOT priority artifact
    assert not mod.is_priority_artifact(
        "flowers red", "flowers white", "REDTYPE", "WHITE")


def test_competing_colours_in_pred_is_priority():
    assert mod.is_priority_artifact(
        "flowers red", "flowers pink or white", "REDTYPE", "WHITE")


def test_same_class_false():
    assert not mod.is_priority_artifact(
        "flowers red", "flowers scarlet", "REDTYPE", "REDTYPE")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
    print("OK")
