#!/usr/bin/env python3
"""
Build expansion analysis inputs from recovered and fascicle colour extracts.

Does not modify clean_color_categories.csv or step05b_outputs_clean.
All outputs go under Processed Data/experiments/expansion/.

Reads  : recovered_descriptions_for_extract.csv
         expansion/fascicle_descriptions.csv
         expansion/flower_color_new.csv (when present)
         step05b_outputs_clean/species_color_environment_final_clean.csv
Writes : expansion/new_descriptions_for_extract.csv
         expansion/color_categories_new.csv
         expansion/species_for_gbif_new.csv
         expansion/build_summary.json

Usage:
  python scripts/04g_Build_Analysis_Set.py --stage extract-input
  python scripts/04g_Build_Analysis_Set.py --stage gbif-input
"""

from __future__ import annotations

import os

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

BASE = (
    Path(os.environ["THESIS_ROOT"]).expanduser().resolve()
    if os.environ.get("THESIS_ROOT")
    else Path(__file__).resolve().parents[1]
)
EXP = BASE / "Processed Data" / "experiments"
OUTDIR = EXP / "expansion"
PRIMARY_FINAL = EXP / "step05b_outputs_clean" / "species_color_environment_final_clean.csv"

KNOWN = {"WHITE", "YELLOW", "RED", "PINK", "PURPLE/BLUE"}

csv.field_size_limit(sys.maxsize)

def categorize_color(text: str) -> str:
    if not text or not text.strip():
        return "UNKNOWN"
    t = text.lower()
    if "no flower colour" in t or "uncertain" in t:
        return "UNKNOWN"
    if "white" in t or "whitish" in t:
        return "WHITE"
    if "yellow" in t or "golden" in t:
        return "YELLOW"
    if "pink" in t or "pinkish" in t:
        return "PINK"
    if "red" in t:
        return "RED"
    if "purple" in t or "purplish" in t or "violet" in t or "blue" in t:
        return "PURPLE/BLUE"
    if "greenish" in t:
        return "GREENISH"
    return "OTHER"

def write_csv(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

def stage_extract_input():
    OUTDIR.mkdir(parents=True, exist_ok=True)
    recovered = EXP / "recovered_descriptions_for_extract.csv"
    fasc = OUTDIR / "fascicle_descriptions.csv"
    rows = []
    for path, source in ((recovered, "recovered"), (fasc, "fascicle")):
        if not path.exists():
            print(f"WARNING: missing {path}")
            continue
        with path.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                text = (r.get("raw_text") or "").strip()
                if not text:
                    continue
                rows.append({
                    "species_id": r["species_id"],
                    "volume": r.get("volume", ""),
                    "genus": r.get("genus", ""),
                    "epithet": r.get("epithet", ""),
                    "binomial": r.get("binomial") or f"{r.get('genus','')} {r.get('epithet','')}".strip(),
                    "raw_text": text,
                    "source": source,
                })
    if not rows:
        raise SystemExit("No descriptions available for extract-input stage")
    out = OUTDIR / "new_descriptions_for_extract.csv"
    write_csv(out, rows)
    print(f"wrote {out} ({len(rows)} rows)")
    by = Counter(r["source"] for r in rows)
    print("by source:", dict(by))
    return out

def stage_gbif_input():
    colours = OUTDIR / "flower_color_new.csv"
    if not colours.exists():
        raise SystemExit(f"Missing {colours} - GPU colour extract must finish first")

    primary_binomials = set()
    if PRIMARY_FINAL.exists():
        with PRIMARY_FINAL.open(encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                # primary table uses query_name as binomial
                q = (r.get("query_name") or "").strip().lower()
                if q:
                    primary_binomials.add(q)
    print(f"primary analysis binomials: {len(primary_binomials)}")

    cats = []
    new_for_gbif = []
    with colours.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            free = r.get("flower_color_free_text") or ""
            cat = categorize_color(free)
            binomial = (r.get("binomial") or f"{r.get('genus','')} {r.get('epithet','')}").strip()
            row = {
                "species_id": r["species_id"],
                "volume": r.get("volume", ""),
                "flower_color_free_text": free,
                "color_category": cat,
                "genus": r.get("genus", ""),
                "epithet": r.get("epithet", ""),
                "binomial": binomial,
                "is_species_level": "TRUE",
                "source": r.get("source", ""),
            }
            cats.append(row)
            if cat in KNOWN and binomial.lower() not in primary_binomials:
                new_for_gbif.append(row)

    write_csv(OUTDIR / "color_categories_new.csv", cats)
    if new_for_gbif:
        write_csv(OUTDIR / "species_for_gbif_new.csv", new_for_gbif)
    else:
        # still write empty-header file for downstream clarity
        write_csv(OUTDIR / "species_for_gbif_new.csv", [{
            "species_id": "", "volume": "", "flower_color_free_text": "",
            "color_category": "", "genus": "", "epithet": "", "binomial": "",
            "is_species_level": "TRUE", "source": "",
        }])

    summary = {
        "n_coloured_rows": len(cats),
        "category_counts": dict(Counter(r["color_category"] for r in cats)),
        "n_new_for_gbif": len(new_for_gbif),
        "n_already_in_primary": sum(
            1 for r in cats
            if r["color_category"] in KNOWN
            and r["binomial"].lower() in primary_binomials),
        "primary_n": len(primary_binomials),
    }
    (OUTDIR / "build_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    print(f"wrote species_for_gbif_new.csv ({len(new_for_gbif)} NEW colour-bearing species)")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True,
                    choices=["extract-input", "gbif-input"])
    args = ap.parse_args()
    if args.stage == "extract-input":
        stage_extract_input()
    else:
        stage_gbif_input()

if __name__ == "__main__":
    main()
