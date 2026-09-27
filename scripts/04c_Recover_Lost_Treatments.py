#!/usr/bin/env python3
"""
Recover treatment text for species lost to parse failures.

Targets UNKNOWN rows diagnosed as EMPTY / NOT_A_DESCRIPTION / TRUNCATED_PRE_FLOWER.
Located-but-no-colour rows are still written so the LLM extractor can decide.

Reads  : Processed Data/experiments/unknown_diagnosis.csv
         Processed Data/experiments/clean_color_categories.csv
         raw_data/FLORA OF INDIA VOL*.txt
Writes : Processed Data/experiments/recovered_treatments.csv
         Processed Data/experiments/recovered_treatments_summary.json

Usage:  python scripts/04c_Recover_Lost_Treatments.py
"""

from __future__ import annotations

import os

import csv
import glob
import json
import re
import sys
from collections import Counter
from pathlib import Path

BASE = (
    Path(os.environ["THESIS_ROOT"]).expanduser().resolve()
    if os.environ.get("THESIS_ROOT")
    else Path(__file__).resolve().parents[1]
)
EXP = BASE / "Processed Data" / "experiments"
RAW = BASE / "raw_data"

csv.field_size_limit(sys.maxsize)

PARSE_FAIL = {"EMPTY", "NOT_A_DESCRIPTION", "TRUNCATED_PRE_FLOWER"}
WINDOW = 2200
MIN_MORPH_HITS = 3

FLOWER_ORGAN = re.compile(
    r"\b(flowers?|florets?|corollas?|petals?|perianth|calyx|sepals?|tepals?)\b", re.I)
COLOUR = re.compile(
    r"\b(white|yellow|red|pink|purple|blue|greenish|orange|violet|crimson|"
    r"scarlet|lilac|mauve|rose|cream|magenta|maroon|golden|"
    r"whitish|yellowish|reddish|purplish|bluish|pinkish)\b", re.I)
APPENDAGE = re.compile(
    r"\b(hairs?|hairy|pappus|filaments?|margins?|margined|scarious|ciliate|"
    r"pubescen(t|ce)|tomentose|villous|puberulous|stellate|bristles?|"
    r"anthers?|styles?|stigmas?|glands?|scales?|veins?|midribs?)\b", re.I)
MORPH = re.compile(
    r"\b(herbs?|shrubs?|trees?|leaves|leaflets?|stems?|branch(es|lets)?|"
    r"petioles?|lamina|inflorescences?|racemes?|panicles?|spikes?|umbels?|"
    r"cymes?|bracts?|ovary|stamens?|capsules?|seeds?|fruits?|glabrous|"
    r"pubescent|erect|ovate|lanceolate|oblong|elliptic|acute|obtuse)\b", re.I)
BOUNDARY = re.compile(
    r"(\n\s*\d{1,3}\s*\.\s+[A-Z][a-z]{2,}\s+[a-z]{3,})"
    r"|(\bFig\s*\.?\s*\d+)"
    r"|(\n\s*[A-Z]{4,}(?:\s+[A-Z]{4,})*\s*\n)"
)

def load_volumes() -> dict[str, str]:
    vols = {}
    for path in glob.glob(str(RAW / "FLORA OF INDIA VOL*.txt")):
        m = re.search(r"VOL\.?\s*(\d+)", Path(path).name, re.I)
        if m:
            vols[m.group(1)] = Path(path).read_text(encoding="utf-8", errors="ignore")
    return vols

def looks_like_index(window: str) -> bool:
    if not window:
        return True
    digits = sum(c.isdigit() for c in window[:400])
    return digits > len(window[:400]) * 0.22

def cut_at_boundary(window: str) -> str:
    m = BOUNDARY.search(window)
    return window[:m.start()] if m else window

def locate_treatment(text: str, genus: str, epithet: str) -> str | None:
    if not genus or not epithet or not text:
        return None
    pattern = re.compile(
        r"\b(?:" + re.escape(genus) + r"|" + re.escape(genus[0]) + r"\.?)\s+"
        + re.escape(epithet) + r"\b", re.I)
    best, best_score = None, 0
    for m in pattern.finditer(text):
        window = cut_at_boundary(text[m.end():m.end() + WINDOW])
        if looks_like_index(window):
            continue
        score = len({x.group(0).lower() for x in MORPH.finditer(window)})
        if score > best_score:
            best, best_score = window, score
    return best if best_score >= MIN_MORPH_HITS else None

def flower_colour_in(window: str) -> str | None:
    if not window:
        return None
    for m in COLOUR.finditer(window):
        ctx = window[max(0, m.start() - 40):m.end() + 40]
        if APPENDAGE.search(ctx):
            continue
        wide = window[max(0, m.start() - 70):m.end() + 70]
        if FLOWER_ORGAN.search(wide):
            return m.group(0).lower()
    return None

def main():
    diag = {r["species_id"]: r["cause"]
            for r in csv.DictReader((EXP / "unknown_diagnosis.csv").open(encoding="utf-8"))}
    with (EXP / "clean_color_categories.csv").open(encoding="utf-8-sig") as f:
        cats = list(csv.DictReader(f))

    targets = [r for r in cats if diag.get(r["species_id"]) in PARSE_FAIL]
    vols = load_volumes()
    print(f"volumes loaded: {sorted(vols)} ({sum(len(v) for v in vols.values())/1e6:.1f}M chars)")
    print(f"parse-fail targets: {len(targets)}")

    out_rows = []
    status_c = Counter()
    for r in targets:
        sid = r["species_id"]
        vol = (r.get("volume") or "").strip()
        genus = (r.get("genus") or "").strip()
        epi = (r.get("epithet") or "").strip()
        window = locate_treatment(vols.get(vol, ""), genus, epi)
        colour = flower_colour_in(window) if window else None
        if colour:
            status = "RECOVERABLE"
        elif window:
            status = "located_no_colour"
        else:
            status = "not_located"
        status_c[status] += 1
        out_rows.append({
            "species_id": sid,
            "volume": vol,
            "genus": genus,
            "epithet": epi,
            "binomial": f"{genus} {epi}".strip(),
            "diagnosis": diag.get(sid, ""),
            "status": status,
            "colour_heuristic": colour or "",
            "raw_text": window or "",
            "n_chars": len(window or ""),
        })

    out = EXP / "recovered_treatments.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0]))
        w.writeheader()
        w.writerows(out_rows)

    # Slim input for the colour extractor: located treatments only
    # (same columns as species_descriptions_treatments.csv)
    slim = EXP / "recovered_descriptions_for_extract.csv"
    with slim.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f, fieldnames=["species_id", "volume", "raw_text", "genus", "epithet", "binomial"])
        w.writeheader()
        for r in out_rows:
            if r["raw_text"].strip():
                w.writerow({
                    "species_id": r["species_id"],
                    "volume": r["volume"],
                    "raw_text": r["raw_text"],
                    "genus": r["genus"],
                    "epithet": r["epithet"],
                    "binomial": r["binomial"],
                })

    summary = {
        "n_targets": len(targets),
        "status_counts": dict(status_c),
        "n_with_text_for_extract": sum(1 for r in out_rows if r["raw_text"].strip()),
        "n_recoverable_heuristic": status_c["RECOVERABLE"],
        "outputs": {
            "full": str(out),
            "extract_input": str(slim),
        },
    }
    (EXP / "recovered_treatments_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")

    print("\nStatus counts:")
    for k, v in status_c.most_common():
        print(f"  {k:22s} {v:5d}  ({v/len(targets):.1%})")
    print(f"\nwrote {out.name} ({len(out_rows)} rows)")
    print(f"wrote {slim.name} "
          f"({summary['n_with_text_for_extract']} rows with text for colour extraction)")
    print(f"heuristic RECOVERABLE (colour in source): {status_c['RECOVERABLE']}")

if __name__ == "__main__":
    main()
