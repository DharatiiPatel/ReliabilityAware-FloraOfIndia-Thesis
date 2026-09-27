#!/usr/bin/env python3
"""
Extract species treatments from Flora of India volume text, dropping key stubs.

Reads  : raw_data/FLORA OF INDIA VOL*.txt
Writes : Processed Data/experiments/species_descriptions_treatments.csv

A heading is a treatment when genus is a full word, epithet is lowercase, and
the following block has a real description. Abbreviated-genus headings are
kept only if the block has a strong description and genus can be carried forward.
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
RAW = BASE / "raw_data"
OUT = BASE / "Processed Data" / "experiments" / "species_descriptions_treatments.csv"

HEADING = re.compile(r"\n\s*(\d+)\.\s+([A-Z][^\n]+)")
FULL_GENUS = re.compile(r"^[A-Z][a-z]{2,}$")
ABBREV_GENUS = re.compile(r"^([A-Z])[a-z]?\.$")
# epithet may be fused to author by OCR ("zeylanica(L.)"); take the leading word
EPITHET_LEAD = re.compile(r"^([a-z][a-z-]{2,})")

HABIT = re.compile(r"\b(Herbs?|Shrubs?|Under-?shrubs?|Trees?|Climbers?|Twiners?|"
                   r"Lianas?|Epiphytes?|Subshrubs?|Perennial|Annual|Biennial)\b")
MORPH = re.compile(r"\b(Leaves|Flowers?|Sepals?|Petals?|Stems?|Corolla|Calyx|"
                   r"Inflorescence|Fruits?|Seeds?|Follicles?|Stamens?|Ovary|Rhizome)\b")
SECTION = re.compile(r"(Fl\.|Fr\.|Distrib|Fig\.)")

# Morphological / structural headers that OCR can look like genera.
# Kept in sync with scripts/04e_Parse_Fascicles.py FALSE_GENERA (+ extras).
FALSE_GENERA = {
    "Habit", "Herbs", "Herb", "Shrubs", "Shrub", "Stems", "Stem", "Upper",
    "Same", "Figs", "Fig", "Type", "Leaves", "Leaf", "Flowers", "Flower",
    "Fruits", "Fruit", "Sepals", "Sepal", "Petals", "Petal", "Seeds", "Seed",
    "KEY", "Key", "Woody", "Annual", "Perennial", "Biennial", "Climbers",
    "Trees", "Tree", "Inflorescence", "Corolla", "Calyx", "Rhizome",
}


def description_score(block: str) -> int:
    """Higher = more like a real treatment description."""
    s = 0
    if HABIT.search(block[:80]):
        s += 2
    s += min(len(MORPH.findall(block)), 4)
    if SECTION.search(block):
        s += 1
    return s


def strong_desc(block: str) -> bool:
    return bool(HABIT.search(block[:80])) and bool(SECTION.search(block))


def clean_epithet(tok: str):
    m = EPITHET_LEAD.match(tok)
    return m.group(1).rstrip("-") if m else None


def parse_volume(text: str, volume):
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    matches = list(HEADING.finditer(text))
    last_full = None
    out = []
    stats = {"headings": len(matches), "accept_full": 0, "accept_abbrev": 0,
             "drop_key": 0, "drop_genus_hdr": 0, "drop_garbled": 0}

    for i, m in enumerate(matches):
        num = m.group(1)
        headline = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end].strip()

        toks = headline.split()
        genus_tok = toks[0] if toks else ""
        epi_tok = toks[1] if len(toks) > 1 else ""

        is_full = bool(FULL_GENUS.match(genus_tok))
        ab = ABBREV_GENUS.match(genus_tok)
        epi = clean_epithet(epi_tok)

        # Reject morphological headers masquerading as binomials
        if genus_tok in FALSE_GENERA:
            stats["drop_genus_hdr"] += 1
            continue

        if is_full:
            # Carry forward full genus token (not just initial letter)
            last_full = genus_tok

        # Path 1: full genus + a lowercase epithet -> real species (any description)
        if is_full and epi:
            out.append((num, volume, genus_tok, epi, headline, block, description_score(block)))
            stats["accept_full"] += 1
            continue

        # Path 2: abbreviated genus + STRONG description.
        # Resolve the abbreviation against the most recently seen full genus
        # whose initial matches the abbreviation letter (length >= 3). This does
        # not detect or reject ambiguity among multiple recent genera that share
        # the same initial; only the latest matching full genus is carried.
        if (
            ab and epi and strong_desc(block) and last_full
            and last_full[0] == ab.group(1)
            and len(last_full) >= 3
            and last_full not in FALSE_GENERA
        ):
            out.append((num, volume, last_full, epi, f"{last_full} {epi}", block,
                        description_score(block)))
            stats["accept_abbrev"] += 1
            continue

        # otherwise classify what we dropped
        if ab:
            stats["drop_key"] += 1
        elif is_full and not epi:
            stats["drop_genus_hdr"] += 1   # e.g. "Clematis", "Aconitum L."
        else:
            stats["drop_garbled"] += 1     # genus itself OCR-garbled

    return out, stats


def main():
    txts = sorted(RAW.glob("FLORA OF INDIA VOL*.txt"))
    if not txts:
        raise SystemExit(f"No volume txt files in {RAW}")

    all_rows = []
    hdr = f"{'volume':>8} | {'headings':>8} | {'acc(full)':>9} | {'acc(abbr)':>9} | {'drop key':>8} | {'genus hdr':>9} | {'garbled':>7}"
    print(hdr)
    print("-" * len(hdr))
    grand = {"headings": 0, "accept_full": 0, "accept_abbrev": 0,
             "drop_key": 0, "drop_genus_hdr": 0, "drop_garbled": 0}

    for t in txts:
        mv = re.search(r"VOL\.?\s*(\d+)", t.name)
        volume = int(mv.group(1)) if mv else t.stem
        text = t.read_text(encoding="utf-8", errors="ignore")
        rows, stats = parse_volume(text, volume)
        all_rows.extend(rows)
        for k in grand:
            grand[k] += stats[k]
        print(f"{str(volume):>8} | {stats['headings']:>8} | {stats['accept_full']:>9} | "
              f"{stats['accept_abbrev']:>9} | {stats['drop_key']:>8} | {stats['drop_genus_hdr']:>9} | {stats['drop_garbled']:>7}")

    print("-" * len(hdr))
    print(f"{'TOTAL':>8} | {grand['headings']:>8} | {grand['accept_full']:>9} | "
          f"{grand['accept_abbrev']:>9} | {grand['drop_key']:>8} | {grand['drop_genus_hdr']:>9} | {grand['drop_garbled']:>7}")

    # Deduplicate by binomial, keeping the row with the LONGEST description block
    # (so a species' real treatment wins over any short key/list stub).
    best = {}
    for num, vol, genus, epi, headline, block, score in all_rows:
        binom = f"{genus} {epi}".lower()
        text_norm = " ".join(block.split())
        cur = best.get(binom)
        if cur is None or len(text_norm) > len(cur["raw_text"]):
            best[binom] = dict(species_id=f"{num}. {headline}", volume=vol, genus=genus,
                               epithet=epi, binomial=f"{genus} {epi}",
                               raw_text=text_norm, desc_score=score)

    n_with_desc = sum(1 for r in best.values() if r["desc_score"] >= 2)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["species_id", "volume", "genus", "epithet", "binomial", "raw_text", "has_description"])
        for r in best.values():
            w.writerow([r["species_id"], r["volume"], r["genus"], r["epithet"],
                        r["binomial"], r["raw_text"], int(r["desc_score"] >= 2)])

    print()
    print(f"Accepted rows (pre-dedup) : {len(all_rows)}")
    print(f"Unique binomials (output) : {len(best)}")
    print(f"  ...with real description: {n_with_desc}")
    print(f"Output                    : {OUT}")


if __name__ == "__main__":
    main()
