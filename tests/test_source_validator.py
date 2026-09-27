#!/usr/bin/env python3
"""Unit tests for the lexical source-text validator (diagnostic flags only)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

def _repo_root() -> Path:
    import os
    env = os.environ.get("THESIS_ROOT")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parents[1]


ROOT = _repo_root()
sys.path.insert(0, str(ROOT / "scripts"))

from lib.source_validator import validate_prediction  # noqa: E402


class SourceValidatorTests(unittest.TestCase):
    def test_cream_coloured_flowers_yellow(self):
        r = validate_prediction(
            "Flowers cream-coloured, in axillary racemes.",
            "YELLOW",
            "cream",
        )
        self.assertTrue(r["supported_floral_evidence"])
        self.assertFalse(r["unsupported_known_colour"])

    def test_cream_white_petals_white(self):
        r = validate_prediction(
            "Petals cream-white, spreading.",
            "WHITE",
            "cream-white",
        )
        self.assertTrue(r["supported_floral_evidence"])
        self.assertFalse(r["unsupported_known_colour"])

    def test_plain_cream_not_white_support_token(self):
        # cream alone must not count as WHITE vocabulary (V2 maps cream → YELLOW).
        r = validate_prediction(
            "Flowers cream, nodding.",
            "WHITE",
            "white",
        )
        self.assertFalse(r["predicted_colour_in_source"])
        self.assertTrue(r["unsupported_known_colour"])

    def test_maroon_petals_redtype(self):
        r = validate_prediction("Petals maroon.", "REDTYPE", "maroon")
        self.assertTrue(r["supported_floral_evidence"])

    def test_rose_coloured_flowers_redtype(self):
        r = validate_prediction(
            "Flowers rose-coloured, in panicles.",
            "REDTYPE",
            "rose",
        )
        self.assertTrue(r["supported_floral_evidence"])

    def test_magenta_flowers_redtype(self):
        r = validate_prediction(
            "Flowers magenta, tubular.",
            "REDTYPE",
            "magenta",
        )
        self.assertTrue(r["supported_floral_evidence"])

    def test_coral_pink_flowers_redtype(self):
        r = validate_prediction(
            "Flowers coral-pink, zygomorphic.",
            "REDTYPE",
            "coral-pink",
        )
        self.assertTrue(r["supported_floral_evidence"])

    def test_yellow_ligules(self):
        r = validate_prediction(
            "Ligules yellow; disc florets darker.",
            "YELLOW",
            "yellow",
        )
        self.assertTrue(r["supported_floral_evidence"])

    def test_yellow_capitula_or_heads(self):
        r = validate_prediction(
            "Capitula yellow, solitary on long peduncles.",
            "YELLOW",
            "yellow",
        )
        self.assertTrue(r["supported_floral_evidence"])
        r2 = validate_prediction(
            "Flower heads yellow, in corymbs.",
            "YELLOW",
            "yellow",
        )
        self.assertTrue(r2["supported_floral_evidence"])

    def test_red_fruit_no_floral_not_supported(self):
        r = validate_prediction(
            "Fruits red, fleshy; leaves glabrous.",
            "REDTYPE",
            "red",
        )
        self.assertFalse(r["supported_floral_evidence"])
        self.assertTrue(r["wrong_context_evidence"] or r["unsupported_known_colour"])

    def test_white_hairs_no_floral_colour_not_supported(self):
        r = validate_prediction(
            "Leaves with white hairs; stems pubescent.",
            "WHITE",
            "white",
        )
        self.assertFalse(r["supported_floral_evidence"])
        self.assertTrue(r["unsupported_known_colour"])


if __name__ == "__main__":
    unittest.main()
