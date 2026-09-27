#!/usr/bin/env python3
"""
Parse OCR'd Fascicles of Flora of India into treatment rows.

Uses the same heading/description rules as 01c_Parse_Treatments.py.

  READS  : raw_data/fascicles/F{N}_{slug}.txt  (sidecar from OCR array)
           scripts/lib/fascicle_manifest.csv
  WRITES : Processed Data/experiments/expansion/fascicle_descriptions.csv

Usage:  python scripts/04e_Parse_Fascicles.py
"""

from __future__ import annotations

import os

import csv
import importlib.util
import sys
from pathlib import Path

BASE = (
    Path(os.environ["THESIS_ROOT"]).expanduser().resolve()
    if os.environ.get("THESIS_ROOT")
    else Path(__file__).resolve().parents[1]
)
FASC = BASE / "raw_data" / "fascicles"
MANIFEST = BASE / "scripts" / "lib" / "fascicle_manifest.csv"
OUTDIR = BASE / "Processed Data" / "experiments" / "expansion"
OUT = OUTDIR / "fascicle_descriptions.csv"

FALSE_GENERA = {
    "Habit", "Herbs", "Stems", "Upper", "Same", "Figs", "Fig", "Type",
    "Leaves", "Flowers", "KEY", "Key", "Woody", "Annual", "Perennial",
}

def load_parser():
    spec = importlib.util.spec_from_file_location(
        "parse", BASE / "scripts" / "01c_Parse_Treatments.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def main():
    OUTDIR.mkdir(parents=True, exist_ok=True)
    p = load_parser()
    manifest = list(csv.reader(MANIFEST.open(encoding="utf-8")))

    all_rows = []
    for n, slug, _pdf in manifest:
        # Prefer canonical name; fall back to pilot F11 name
        candidates = [
            FASC / f"F{n}_{slug}.txt",
            FASC / "F11_Cucurbitaceae.txt" if n == "11" else None,
        ]
        path = next((c for c in candidates if c and c.exists()), None)
        if path is None:
            print(f"F{n}: MISSING txt - skip", file=sys.stderr)
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if len(text) < 5000:
            print(f"F{n}: txt too small ({len(text)} chars) - skip", file=sys.stderr)
            continue
        rows, stats = p.parse_volume(text, volume=f"F{n}")
        # Dedup by binomial, keep best score; drop figure junk
        best = {}
        for num, vol, genus, epi, headline, block, score in rows:
            if genus in FALSE_GENERA or score < 2:
                continue
            key = f"{genus} {epi}".lower()
            if key not in best or score > best[key][6]:
                best[key] = (num, vol, genus, epi, headline, block, score)
        kept = list(best.values())
        print(f"F{n} ({slug}): chars={len(text)} headings={stats['headings']} "
              f"kept={len(kept)}")
        for num, vol, genus, epi, headline, block, score in kept:
            all_rows.append({
                "species_id": f"F{n}.{num}. {genus} {epi}",
                "volume": vol,
                "genus": genus,
                "epithet": epi,
                "binomial": f"{genus} {epi}",
                "raw_text": block,
                "has_description": "1" if block.strip() else "0",
                "desc_score": score,
                "source": "fascicle",
            })

    if not all_rows:
        raise SystemExit("No fascicle treatments parsed - were OCR jobs finished?")

    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(all_rows[0]))
        w.writeheader()
        w.writerows(all_rows)
    print(f"\nwrote {OUT} ({len(all_rows)} treatments)")

if __name__ == "__main__":
    main()
