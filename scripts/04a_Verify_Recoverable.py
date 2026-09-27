#!/usr/bin/env python3
"""
Locate lost-species treatments in volume text and check whether they name a colour.

A species counts as recoverable if it is UNKNOWN from a parse failure, its
treatment can be located, and that treatment names a colour on a flower organ.
The locator scores every binomial occurrence and rejects index-like windows.
A control pass on known-colour species reports whether the locator is trustworthy.

Reads  : raw_data/FLORA OF INDIA VOL.*.txt
         Processed Data/experiments/unknown_diagnosis.csv
         Processed Data/experiments/clean_color_categories.csv
Writes : Processed Data/experiments/recoverable_verified.csv

Usage:  python 04a_Verify_Recoverable.py [--limit 400] [--control 150]
"""

from __future__ import annotations

import os

import argparse
import csv
import glob
import random
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

csv.field_size_limit(sys.maxsize)

WINDOW = 2200          # chars of treatment text to read after a name match
MIN_MORPH_HITS = 3     # morphology terms needed before we call a window a treatment

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


def load_volumes() -> dict[str, str]:
    vols = {}
    for path in glob.glob(str(BASE / "raw_data" / "*.txt")):
        m = re.search(r"VOL\.?\s*(\d+)", Path(path).name, re.I)
        if m:
            vols[m.group(1)] = Path(path).read_text(encoding="utf-8", errors="ignore")
    return vols


def looks_like_index(window: str) -> bool:
    """Index runs are dense in digits and sparse in prose."""
    if not window:
        return True
    digits = sum(c.isdigit() for c in window[:400])
    return digits > len(window[:400]) * 0.22


    # Cut the window at the next numbered treatment, figure caption, or family heading.
BOUNDARY = re.compile(
    r"(\n\s*\d{1,3}\s*\.\s+[A-Z][a-z]{2,}\s+[a-z]{3,})"      # '2. Myricaria davurica'
    r"|(\bFig\s*\.?\s*\d+)"                                    # figure caption
    r"|(\n\s*[A-Z]{4,}(?:\s+[A-Z]{4,})*\s*\n)",                # FAMILY heading
    re.I if False else 0)


def cut_at_boundary(window: str) -> str:
    m = BOUNDARY.search(window)
    return window[:m.start()] if m else window


def locate_treatment(text: str, genus: str, epithet: str) -> str | None:
    """Return the best candidate treatment window for this binomial."""
    if not genus or not epithet:
        return None
    # Genus is often abbreviated to its initial after first mention.
    pattern = re.compile(
        r"\b(?:" + re.escape(genus) + r"|" + re.escape(genus[0]) + r"\.?)\s+"
        + re.escape(epithet) + r"\b", re.I)

    best, best_score = None, 0
    for m in pattern.finditer(text):
        window = cut_at_boundary(text[m.end():m.end() + WINDOW])
        if looks_like_index(window):
            continue
        score = len(set(x.group(0).lower() for x in MORPH.finditer(window)))
        if score > best_score:
            best, best_score = window, score
    return best if best_score >= MIN_MORPH_HITS else None


def flower_colour_in(window: str) -> str | None:
    """Colour word sitting on a flower organ, ignoring hairs/margins/etc."""
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
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=400,
                    help="lost species to test (0 = all)")
    ap.add_argument("--control", type=int, default=150,
                    help="known-colour species used to validate the locator")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    vols = load_volumes()
    print(f"Loaded {len(vols)} volumes, "
          f"{sum(len(v) for v in vols.values()) / 1e6:.1f}M chars\n")

    diag = {r["species_id"]: r["cause"]
            for r in csv.DictReader((EXP / "unknown_diagnosis.csv").open(encoding="utf-8"))}
    with (EXP / "clean_color_categories.csv").open(encoding="utf-8-sig") as f:
        cats = list(csv.DictReader(f))

    PARSE_FAIL = {"EMPTY", "NOT_A_DESCRIPTION", "TRUNCATED_PRE_FLOWER"}
    lost = [r for r in cats if diag.get(r["species_id"]) in PARSE_FAIL]
    known = [r for r in cats
             if r["color_category"].strip().upper() not in ("UNKNOWN", "")]

    rng = random.Random(args.seed)

    # Control: agreement with already-known colours, not merely finding a colour word.
    import importlib.util
    spec = importlib.util.spec_from_file_location("c2", BASE / "scripts" / "14_Categorize_v2.py")
    c2 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(c2)

    ctrl = rng.sample(known, min(args.control, len(known)))
    ctrl_found = ctrl_colour = ctrl_match = 0
    for r in ctrl:
        w = locate_treatment(vols.get(r.get("volume", "").strip(), ""),
                             r.get("genus", "").strip(), r.get("epithet", "").strip())
        if w is None:
            continue
        ctrl_found += 1
        colour = flower_colour_in(w)
        if not colour:
            continue
        ctrl_colour += 1
        if c2.categorize_v2(colour).strip().upper() == r["color_category"].strip().upper():
            ctrl_match += 1

    print("CONTROL - locator run on species whose colour we already know")
    print("=" * 68)
    print(f"  treatment located      : {ctrl_found}/{len(ctrl)} ({ctrl_found / len(ctrl):.1%})")
    if ctrl_found:
        print(f"  a colour found in it   : {ctrl_colour}/{ctrl_found} "
              f"({ctrl_colour / ctrl_found:.1%})")
    if ctrl_colour:
        acc = ctrl_match / ctrl_colour
        print(f"  and it is the RIGHT one: {ctrl_match}/{ctrl_colour} ({acc:.1%})")
        print(f"  -> the locator is {'trustworthy' if acc >= 0.8 else 'NOT reliable enough'}"
              f" for the test below")
        if acc < 0.8:
            print("     Treat the recoverable count as an upper bound, not a result.")
    print()

    pool = lost if args.limit == 0 else rng.sample(lost, min(args.limit, len(lost)))
    rows, causes = [], Counter()
    for r in pool:
        sid = r["species_id"]
        w = locate_treatment(vols.get(r.get("volume", "").strip(), ""),
                             r.get("genus", "").strip(), r.get("epithet", "").strip())
        colour = flower_colour_in(w) if w else None
        status = ("RECOVERABLE" if colour else
                  "located_no_colour" if w else "not_located")
        causes[status] += 1
        rows.append({
            "species_id": sid, "volume": r.get("volume", ""),
            "genus": r.get("genus", ""), "epithet": r.get("epithet", ""),
            "diagnosis": diag.get(sid, ""), "status": status,
            "colour_found": colour or "",
            "evidence": (w or "")[:300].replace("\n", " "),
        })

    n = len(pool)
    rec = causes["RECOVERABLE"]
    print(f"TEST - {n} species diagnosed as lost to parsing")
    print("=" * 68)
    for k, c in causes.most_common():
        print(f"  {k:22s} {c:5d}  {c / n:6.1%}")
    print()
    print(f"  => {rec}/{n} ({rec / n:.1%}) have a locatable treatment that "
          f"states a flower colour")
    print(f"     extrapolated to all {len(lost)} parse-failed species: "
          f"~{int(rec / n * len(lost))} genuinely recoverable")
    print()

    print("EVIDENCE - species currently thrown away whose colour is in the source")
    print("=" * 68)
    shown = 0
    for r in rows:
        if r["status"] != "RECOVERABLE" or shown >= 8:
            continue
        shown += 1
        ev = re.sub(r"\s+", " ", r["evidence"])[:190]
        print(f"  {r['genus']} {r['epithet']} (vol {r['volume']}, {r['diagnosis']}) "
              f"-> {r['colour_found'].upper()}")
        print(f"     ...{ev}...")

    out = EXP / "recoverable_verified.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w_ = csv.DictWriter(f, fieldnames=list(rows[0]))
        w_.writeheader()
        w_.writerows(rows)
    print(f"\nwrote {out.name} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
