#!/usr/bin/env python3
"""
Download BSI Fascicles of Flora of India PDFs into raw_data/fascicles/.

Skips files that already exist and look complete (>100 KB).
Source: http://bsi.gov.in/page/en/fascicles-of-flora-of-india

Usage:  python scripts/04b_Download_Fascicles.py
"""

from __future__ import annotations

import os

import csv
import ssl
import sys
import urllib.parse
import urllib.request
from pathlib import Path

BASE = (
    Path(os.environ["THESIS_ROOT"]).expanduser().resolve()
    if os.environ.get("THESIS_ROOT")
    else Path(__file__).resolve().parents[1]
)
OUT = BASE / "raw_data" / "fascicles"
MANIFEST = BASE / "scripts" / "lib" / "fascicle_manifest.csv"
URL_BASE = (
    "https://bsi.gov.in/uploads/documents/Public_Information/publication/"
    "books/fascicles_of_flora_of_India_latest/"
)
MIN_BYTES = 100_000

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ctx = ssl.create_default_context()
    # Some campus proxies present odd cert chains; BSI is public gov content.
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    rows = [r for r in csv.reader(MANIFEST.open(encoding="utf-8"))
            if r and not r[0].startswith("#") and len(r) >= 3]
    ok = skip = fail = 0
    for n, slug, pdf_name in rows:
        dest = OUT / f"F{n}_{slug}.pdf"
        # Keep legacy F11_Cucurbitaceae.pdf name as alias if present
        legacy = OUT / "F11_Cucurbitaceae.pdf"
        if n == "11" and legacy.exists() and legacy.stat().st_size > MIN_BYTES:
            if not dest.exists():
                dest.write_bytes(legacy.read_bytes())
                print(f"F{n}: copied from legacy {legacy.name} -> {dest.name}")
            else:
                print(f"F{n}: already present ({dest.stat().st_size} bytes)")
            skip += 1
            continue
        if dest.exists() and dest.stat().st_size > MIN_BYTES:
            print(f"F{n}: already present ({dest.stat().st_size} bytes)")
            skip += 1
            continue
        url = URL_BASE + urllib.parse.quote(pdf_name)
        print(f"F{n}: downloading {pdf_name} ...", flush=True)
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 ThesisOCR/1.0"})
            with urllib.request.urlopen(req, context=ctx, timeout=180) as r:
                data = r.read()
            if len(data) < MIN_BYTES:
                raise RuntimeError(f"too small ({len(data)} bytes)")
            dest.write_bytes(data)
            print(f"F{n}: wrote {dest.name} ({len(data)} bytes)")
            ok += 1
        except Exception as e:
            print(f"F{n}: FAILED {e}", file=sys.stderr)
            fail += 1
    print(f"\ndone: downloaded={ok} skipped={skip} failed={fail}")
    if fail:
        sys.exit(1)

if __name__ == "__main__":
    main()
