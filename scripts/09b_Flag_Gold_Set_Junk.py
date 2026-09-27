#!/usr/bin/env python3
"""
Pre-flag likely junk / genus-header rows in the gold-set template so the human
labeller (you) doesn't waste time puzzling over them.

Flags added to the 'notes' column (does NOT touch gold_free_text/gold_category
- those stay for you to fill in by hand):
  AUTO-FLAG: possible genus-level header (epithet token = '<X>', not lowercase)
  AUTO-FLAG: species_id looks garbled / non-taxonomic (collector list, OCR noise)
  AUTO-FLAG: very short description snippet - may lack real info

SAFE: only edits the 'notes' column of gold_set_template.csv; every other
column (including any labels you've already typed) is preserved untouched.
"""
import os

import csv
import re
from pathlib import Path

BASE = (
    Path(os.environ["THESIS_ROOT"]).expanduser().resolve()
    if os.environ.get("THESIS_ROOT")
    else Path(__file__).resolve().parents[1]
)
PATH = BASE / "Processed Data" / "experiments" / "gold_set_template.csv"

NUM_PREFIX = re.compile(r"^\s*\d+\.?\s*")
LOWER_EPITHET = re.compile(r"^[a-z][a-z-]{2,}")
FULL_GENUS = re.compile(r"^[A-Z][a-z]{2,}$")
ABBREV_GENUS = re.compile(r"^[A-Z]\.?$")
COMMON_NOUN = re.compile(r"^(Shrubs?|Herbs?|Trees?|Leaves|Flowers?|Stems?|Fruits?|Seeds?)[,.]?$", re.I)


def flag_row(species_id: str, snippet: str) -> str:
    flags = []
    name = NUM_PREFIX.sub("", species_id).strip()
    toks = name.split()

    genus = toks[0] if toks else ""
    epithet = toks[1] if len(toks) > 1 else ""

    if genus and COMMON_NOUN.match(genus):
        # heading regex accidentally matched mid-description text, not a real heading
        flags.append("AUTO-FLAG: species_id is not a real taxon heading (matched mid-description text) - verify the row before labelling, may need to re-check raw text")

    elif genus and ABBREV_GENUS.match(genus):
        # e.g. "C. elliptica" - abbreviated genus key-stub (same OCR issue as the main pipeline)
        flags.append(f"AUTO-FLAG: abbreviated genus ('{genus}') - this is likely a duplicate identification-key stub, not the real species treatment; the full name may appear elsewhere in the volume")

    elif genus and epithet and not LOWER_EPITHET.match(epithet) and not FULL_GENUS.match(genus):
        flags.append(f"AUTO-FLAG: species_id looks garbled/non-taxonomic (genus token='{genus}') - verify before labelling")

    elif genus and epithet and not LOWER_EPITHET.match(epithet):
        # full genus but second token isn't a lowercase epithet (e.g. "L.", "DC.", "Adans.")
        flags.append(f"AUTO-FLAG: possible genus-level header (epithet token='{epithet}', not lowercase) - likely describes the whole genus, not one species")

    elif not epithet:
        flags.append("AUTO-FLAG: could not find a second token (epithet) - inspect species_id manually")

    if len(snippet.strip()) < 60:
        flags.append("AUTO-FLAG: very short description snippet - may lack real info")

    return " | ".join(flags)


def main():
    rows = list(csv.DictReader(PATH.open(encoding="utf-8")))
    fieldnames = list(rows[0].keys())

    n_flagged = 0
    for r in rows:
        auto_note = flag_row(r["species_id"], r["raw_text_snippet"])
        if auto_note:
            n_flagged += 1
            existing = r.get("notes", "").strip()
            r["notes"] = auto_note if not existing else f"{existing} | {auto_note}"

    with PATH.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(f"Checked {len(rows)} rows.")
    print(f"Auto-flagged {n_flagged} rows as likely junk/genus-header/short.")
    print(f"Clean (unflagged) rows to focus on: {len(rows) - n_flagged}")
    print(f"\nUpdated in place: {PATH}")
    print("Only the 'notes' column was touched - your gold_free_text/gold_category cells are untouched.")


if __name__ == "__main__":
    main()
