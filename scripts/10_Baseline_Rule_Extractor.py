#!/usr/bin/env python3
"""
Rule-based (non-LLM) flower-colour extractor -- the benchmark FLOOR.

This is the "dumb baseline" every extraction benchmark needs: a transparent
keyword/regex heuristic with no machine learning. It lets you quantify how much
the LLMs actually buy you over a naive approach.

Heuristic:
  1. Split the description into sentences.
  2. Keep only sentences that mention a floral organ
     (flower/flowers/petal/petals/corolla/perianth/tepal/floret).
  3. Within those, find the FIRST colour keyword.
  4. Emit "flowers <colour>"; if no floral-organ sentence has a colour,
     emit "no flower colour mentioned".

This deliberately does NOT try to resolve fruit/leaf colour, multi-colour, etc.
-- that is exactly the gap the LLMs are supposed to close.

Runs on CPU. Output format matches the LLM extractor (id, flower_color_free_text)
so 12_Score_Models_vs_Gold.py can treat it as just another 'model'.

Usage
-----
  python 10_Baseline_Rule_Extractor.py \
      --task "Processed Data/experiments/gold_set_template.csv::raw_text_snippet::species_id::Processed Data/experiments/benchmark/gold_pred_baseline.csv" \
      --task "Processed Data/experiments/species_descriptions_treatments.csv::raw_text::species_id::Processed Data/experiments/benchmark/treatments_pred_baseline.csv"
"""
import os

import argparse
import csv
import re
import sys
from pathlib import Path

BASE = (
    Path(os.environ["THESIS_ROOT"]).expanduser().resolve()
    if os.environ.get("THESIS_ROOT")
    else Path(__file__).resolve().parents[1]
)
csv.field_size_limit(sys.maxsize)

FLORAL = re.compile(
    r"\b(flowers?|petals?|corolla|perianth|tepals?|florets?|blossoms?)\b", re.I)

# ordered so more specific colours win; each maps to a canonical word
COLOUR_WORDS = [
    ("whitish", "white"), ("white", "white"),
    ("yellowish", "yellow"), ("yellow", "yellow"), ("golden", "yellow"),
    ("pinkish", "pink"), ("pink", "pink"),
    ("purplish", "purple"), ("purple", "purple"), ("violet", "purple"),
    ("bluish", "blue"), ("blue", "blue"),
    ("reddish", "red"), ("scarlet", "red"), ("crimson", "red"), ("red", "red"),
    ("orange", "orange"),
    ("greenish", "greenish"), ("green", "greenish"),
    ("cream", "cream"),
]
COLOUR_RE = re.compile(
    r"\b(" + "|".join(re.escape(w) for w, _ in COLOUR_WORDS) + r")\b", re.I)
CANON = {w: c for w, c in COLOUR_WORDS}


def extract(description: str) -> str:
    if not description or not description.strip():
        return "no flower colour mentioned"
    # naive sentence split on . ; and newlines
    sentences = re.split(r"[.;\n]", description)
    for sent in sentences:
        if not FLORAL.search(sent):
            continue
        m = COLOUR_RE.search(sent)
        if m:
            return f"flowers {CANON[m.group(1).lower()]}"
    return "no flower colour mentioned"


def resolve(p: str) -> Path:
    q = Path(p)
    return q if q.is_absolute() else BASE / q


def run_task(spec: str):
    parts = spec.split("::")
    if len(parts) != 4:
        raise ValueError(f"--task must be INPUT::TEXT_COL::ID_COL::OUTPUT, got {spec!r}")
    in_csv, text_col, id_col, out_csv = parts
    in_path, out_path = resolve(in_csv), resolve(out_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(in_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print(f"(no rows in {in_path.name})")
        return
    if text_col not in rows[0] or id_col not in rows[0]:
        raise KeyError(f"Columns {text_col!r}/{id_col!r} not in {in_path.name}: "
                       f"{list(rows[0].keys())}")

    with open(out_path, "w", newline="", encoding="utf-8") as f_out:
        w = csv.DictWriter(f_out, fieldnames=[id_col, "flower_color_free_text"])
        w.writeheader()
        for r in rows:
            w.writerow({id_col: r.get(id_col, ""),
                        "flower_color_free_text": extract(r.get(text_col, ""))})
    print(f"{in_path.name} -> {out_path}  ({len(rows)} rows)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", action="append", required=True,
                    help="INPUT_CSV::TEXT_COL::ID_COL::OUTPUT_CSV (repeatable)")
    args = ap.parse_args()
    for spec in args.task:
        run_task(spec)
    print("Baseline extraction complete.")


if __name__ == "__main__":
    main()
