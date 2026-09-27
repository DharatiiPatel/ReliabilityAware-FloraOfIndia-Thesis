#!/usr/bin/env python3
"""
Build a 100-species GOLD SET template for manual flower-colour labelling.

SAFE BY DESIGN:
  - READS  : Processed Data/flora_of_india_flower_color_categories.csv  (Qwen labels)
             Processed Data/flora_of_india_species_descriptions.csv     (raw text)
  - WRITES : Processed Data/experiments/gold_set_template.csv
  - Touches nothing in the real pipeline.

The template is STRATIFIED by difficulty so evaluation is meaningful:
  clear_white / clear_yellow / clear_redtype  -> easy cases (should be right)
  ambiguous                                   -> free text has 'to', 'tinged', 'or', etc.
  no_mention (UNKNOWN)                         -> should say 'no flower colour mentioned'

You then fill in TWO columns by hand:
  gold_free_text   : the colour phrase you judge correct (or 'no flower colour mentioned')
  gold_category    : WHITE / YELLOW / REDTYPE / OTHER / UNKNOWN
"""
import os

import csv
import random
from pathlib import Path

BASE = (
    Path(os.environ["THESIS_ROOT"]).expanduser().resolve()
    if os.environ.get("THESIS_ROOT")
    else Path(__file__).resolve().parents[1]
)
CAT_CSV  = BASE / "Processed Data" / "flora_of_india_flower_color_categories.csv"
DESC_CSV = BASE / "Processed Data" / "flora_of_india_species_descriptions.csv"
OUT_CSV  = BASE / "Processed Data" / "experiments" / "gold_set_template.csv"

random.seed(42)  # reproducible sample

# how many species per stratum (edit to taste; total ~100)
QUOTA = {
    "clear_white":   20,
    "clear_yellow":  20,
    "clear_redtype": 15,
    "ambiguous":     25,
    "no_mention":    20,
}

REDTYPE = {"RED", "PINK", "PURPLE/BLUE"}
AMBIG_HINTS = (" to ", "tinged", " or ", "pale", "variable", "sometimes",
               "becoming", "turning", "then", "streak", "veined")


def load_descriptions():
    d = {}
    for r in csv.DictReader(DESC_CSV.open(encoding="utf-8")):
        d[r["species_id"]] = r.get("raw_text", "")
    return d


def stratum_of(cat, free_text):
    ft = (free_text or "").lower()
    if cat == "UNKNOWN":
        return "no_mention"
    if any(h in ft for h in AMBIG_HINTS):
        return "ambiguous"
    if cat == "WHITE":
        return "clear_white"
    if cat == "YELLOW":
        return "clear_yellow"
    if cat in REDTYPE:
        return "clear_redtype"
    return None  # OTHER / GREENISH -> not sampled here


def main():
    desc = load_descriptions()
    buckets = {k: [] for k in QUOTA}

    for r in csv.DictReader(CAT_CSV.open(encoding="utf-8")):
        s = stratum_of(r["color_category"], r["flower_color_free_text"])
        if s in buckets:
            buckets[s].append(r)

    chosen = []
    for stratum, n in QUOTA.items():
        pool = buckets[stratum]
        random.shuffle(pool)
        take = pool[:n]
        for r in take:
            raw = desc.get(r["species_id"], "")
            chosen.append({
                "species_id": r["species_id"],
                "volume": r["volume"],
                "stratum": stratum,
                "qwen_free_text": r["flower_color_free_text"],
                "qwen_category": r["color_category"],
                # FULL text, not truncated: the flower-colour sentence can appear
                # anywhere in the description (sometimes past character 400+),
                # and Qwen sees the full text, so the human labeller must too -
                # otherwise "disagreements" are just an artifact of less information.
                "raw_text_snippet": raw,
                "gold_free_text": "",            # <-- YOU FILL THIS
                "gold_category": "",             # <-- YOU FILL THIS
                "notes": "",                     # <-- optional
            })
        print(f"{stratum:14s}: requested {n}, available {len(pool)}, took {len(take)}")

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(chosen[0].keys()))
        w.writeheader()
        w.writerows(chosen)

    print(f"\nWrote {len(chosen)} rows to {OUT_CSV}")
    print("Open it in Excel/LibreOffice and fill 'gold_free_text' + 'gold_category'.")


if __name__ == "__main__":
    main()
