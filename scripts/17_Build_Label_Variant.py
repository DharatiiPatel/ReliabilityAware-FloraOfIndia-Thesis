#!/usr/bin/env python3
"""
Build equal-cohort label-source datasets for label sensitivity analysis.

Design:
  * Anchor species and PC scores to the published n=1,438 env table.
  * Report source-specific known-colour coverage on that table separately.
  * Main equal cohort = intersection where Qwen-7B, Qwen-72B, and Llama-70B
    all give a known colour (WHITE/YELLOW/REDTYPE) under the V2 categoriser.
  * Secondary four-source cohort = main intersection further restricted to
    species the rule baseline also labels as known.

Labels are produced by applying scripts/14_Categorize_v2.py to stored free text
(no LLM re-inference).

Writes under Processed Data/experiments/label_sensitivity/:
  coverage_summary.json
  source_coverage.csv
  cohort_llm_common.csv
  cohort_four_source.csv
  species_color_environment_{qwen7b,qwen72b,llama70b}.csv
  secondary/species_color_environment_{baseline,qwen7b,qwen72b,llama70b}.csv

Usage:
  python scripts/17_Build_Label_Variant.py
"""

from __future__ import annotations

import os

import csv
import importlib.util
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
ENV = (EXP / "expansion" / "step05b_outputs" /
       "species_color_environment_final_expanded.csv")
RELIABILITY = EXP / "reliability" / "species_reliability.csv"
OUTDIR = EXP / "label_sensitivity"
SECONDARY = OUTDIR / "secondary"

KNOWN = {"WHITE", "YELLOW", "REDTYPE"}
LLM_SOURCES = ("qwen7b", "qwen72b", "llama70b")
ALL_SOURCES = ("baseline", "qwen7b", "qwen72b", "llama70b")
FREE_COLS = {
    "baseline": "baseline_free_text",
    "qwen7b": "qwen7b_free_text",
    "qwen72b": "qwen72b_free_text",
    "llama70b": "llama70b_free_text",
}
PC_COLS = [f"PC{i}" for i in range(1, 11)]

csv.field_size_limit(sys.maxsize)


def _load_c2():
    spec = importlib.util.spec_from_file_location(
        "c2", BASE / "scripts" / "14_Categorize_v2.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _read(path: Path):
    with path.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _write(path: Path, rows: list[dict], fields: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def _label(c2, free: str) -> str:
    t = (free or "").strip()
    if not t or t.lower() == "uncertain":
        return "UNKNOWN"
    return c2.to_class(c2.categorize_v2(t))


def _ecology_row(env: dict, color_group: str) -> dict:
    out = {
        "query_name": env["query_name"],
        "color_group": color_group,
        "n_records": env["n_records"],
        "is_white": 1 if color_group == "WHITE" else 0,
        "is_yellow": 1 if color_group == "YELLOW" else 0,
        "is_redtype": 1 if color_group == "REDTYPE" else 0,
    }
    for c in PC_COLS:
        out[c] = env[c]
    return out


def _assert_equal_cohort(datasets: dict[str, list[dict]], label: str):
    names = {src: [r["query_name"] for r in rows] for src, rows in datasets.items()}
    ref_src = next(iter(names))
    ref = names[ref_src]
    for src, seq in names.items():
        if seq != ref:
            raise SystemExit(
                f"{label}: species lists differ between {ref_src} and {src} "
                f"(n={len(ref)} vs {len(seq)})")
        if len(seq) != len(set(seq)):
            raise SystemExit(f"{label}/{src}: duplicate query_name")
    ns = {src: len(rows) for src, rows in datasets.items()}
    if len(set(ns.values())) != 1:
        raise SystemExit(f"{label}: unequal n across sources: {ns}")
    ref_rows = datasets[ref_src]
    for src, rows in datasets.items():
        for a, b in zip(ref_rows, rows):
            if a["query_name"] != b["query_name"]:
                raise SystemExit(f"{label}/{src}: query_name order differs")
            for pc in PC_COLS:
                if a[pc] != b[pc]:
                    raise SystemExit(f"{label}/{src}: PC values differ")
            if a["query_name"].split()[0] != b["query_name"].split()[0]:
                raise SystemExit(f"{label}/{src}: genus differs")
    return len(ref)


def main():
    c2 = _load_c2()
    sha = c2.module_sha256()
    env_rows = _read(ENV)
    env_by = {r["query_name"].strip(): r for r in env_rows}
    if len(env_by) != len(env_rows):
        raise SystemExit("duplicate query_name in published env table")
    if len(env_rows) != 1438:
        raise SystemExit(f"published env n={len(env_rows)}, expected 1438")

    rel = _read(RELIABILITY)
    if len(rel) != len(env_rows):
        raise SystemExit(
            f"reliability table n={len(rel)} != published env n={len(env_rows)}")
    rel_by = {r["query_name"].strip(): r for r in rel}
    missing = set(env_by) - set(rel_by)
    if missing:
        raise SystemExit(f"{len(missing)} env species missing from reliability")

    labels_by = {name: {} for name in env_by}
    coverage_rows = []
    known_sets = {src: set() for src in ALL_SOURCES}
    for name, env in env_by.items():
        r = rel_by[name]
        row = {"query_name": name, "published_color_group": env["color_group"]}
        for src in ALL_SOURCES:
            free = r.get(FREE_COLS[src]) or ""
            lab = _label(c2, free)
            labels_by[name][src] = lab
            known = lab in KNOWN
            row[f"{src}_label"] = lab
            row[f"{src}_known"] = "TRUE" if known else "FALSE"
            if known:
                known_sets[src].add(name)
        coverage_rows.append(row)

    llm_common = sorted(
        known_sets["qwen7b"] & known_sets["qwen72b"] & known_sets["llama70b"])
    four_source = sorted(set(llm_common) & known_sets["baseline"])

    main_ds = {}
    for src in LLM_SOURCES:
        rows = []
        for name in llm_common:
            lab = labels_by[name][src]
            if lab not in KNOWN:
                raise SystemExit(f"{src} not known on llm_common species {name}")
            rows.append(_ecology_row(env_by[name], lab))
        main_ds[src] = rows
    n_main = _assert_equal_cohort(main_ds, "llm_common")

    secondary = {}
    for src in ALL_SOURCES:
        rows = []
        for name in four_source:
            lab = labels_by[name][src]
            if lab not in KNOWN:
                raise SystemExit(f"{src} not known on four_source species {name}")
            rows.append(_ecology_row(env_by[name], lab))
        secondary[src] = rows
    n_fs = _assert_equal_cohort(secondary, "four_source")

    fields = ["query_name", "color_group"] + PC_COLS + \
             ["n_records", "is_white", "is_yellow", "is_redtype"]

    OUTDIR.mkdir(parents=True, exist_ok=True)
    SECONDARY.mkdir(parents=True, exist_ok=True)

    _write(OUTDIR / "source_coverage.csv", coverage_rows,
           ["query_name", "published_color_group"] +
           [f"{s}_{x}" for s in ALL_SOURCES for x in ("label", "known")])
    _write(OUTDIR / "cohort_llm_common.csv",
           [{"query_name": n} for n in llm_common], ["query_name"])
    _write(OUTDIR / "cohort_four_source.csv",
           [{"query_name": n} for n in four_source], ["query_name"])

    for src, rows in main_ds.items():
        _write(OUTDIR / f"species_color_environment_{src}.csv", rows, fields)
    for src, rows in secondary.items():
        _write(SECONDARY / f"species_color_environment_{src}.csv", rows, fields)

    summary = {
        "primary_anchor_n": 1438,
        "categorizer_name": "V2",
        "categorizer_version": 2,
        "categorizer_sha256": sha,
        "label_coding": "scripts/14_Categorize_v2.py on stored free text",
        "source_specific_known_n": {src: len(known_sets[src]) for src in ALL_SOURCES},
        "source_specific_known_colour_counts": {
            src: dict(Counter(labels_by[n][src] for n in sorted(known_sets[src])))
            for src in ALL_SOURCES
        },
        "main_cohort": {
            "name": "llm_common",
            "definition": "Qwen-7B ∩ Qwen-72B ∩ Llama-70B all known colour under V2",
            "n": n_main,
            "variants": list(LLM_SOURCES),
            "colour_counts_by_variant": {
                src: dict(Counter(r["color_group"] for r in rows))
                for src, rows in main_ds.items()
            },
            "species_set_identical_across_variants": True,
        },
        "secondary_cohort": {
            "name": "four_source",
            "definition": ("llm_common ∩ baseline known; rule baseline is "
                           "secondary only, not in the main equal-cohort "
                           "comparison"),
            "n": n_fs,
            "variants": list(ALL_SOURCES),
            "colour_counts_by_variant": {
                src: dict(Counter(r["color_group"] for r in rows))
                for src, rows in secondary.items()
            },
            "species_set_identical_across_variants": True,
        },
        "note": (
            "The 1,438-species primary cohort was constructed before the "
            "categorisation refinement. V2 is applied within that cohort for "
            "label sensitivity without changing the environmental species sample."
        ),
    }
    with (OUTDIR / "coverage_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("Primary anchor n:", 1438)
    print("Source-specific known n:", summary["source_specific_known_n"])
    print(f"Main llm_common n={n_main}  variants={list(LLM_SOURCES)}")
    for src, rows in main_ds.items():
        print(f"  {src}: {dict(Counter(r['color_group'] for r in rows))}")
    print(f"Secondary four_source n={n_fs}")
    print("Wrote", OUTDIR / "coverage_summary.json")


if __name__ == "__main__":
    main()
