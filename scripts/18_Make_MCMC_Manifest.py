#!/usr/bin/env python3
"""
Build one SLURM array task per (source x colour x chain) for label sensitivity.

Main equal-cohort only: Qwen-7B, Qwen-72B, Llama-70B on the n=1,149 intersection.
Baseline / four_source are not included.

Reads  : label_sensitivity/species_color_environment_{qwen7b,qwen72b,llama70b}.csv
         label_sensitivity/coverage_summary.json
Writes : label_sensitivity/mcmc_manifest.csv  (exactly 27 tasks)

Usage:
  python scripts/18_Make_MCMC_Manifest.py
"""

from __future__ import annotations

import os

import csv
import hashlib
import json
import sys
from pathlib import Path

BASE = (
    Path(os.environ["THESIS_ROOT"]).expanduser().resolve()
    if os.environ.get("THESIS_ROOT")
    else Path(__file__).resolve().parents[1]
)
VARDIR = BASE / "Processed Data" / "experiments" / "label_sensitivity"
MANIFEST = VARDIR / "mcmc_manifest.csv"
COVERAGE = VARDIR / "coverage_summary.json"
CATEGORISER = BASE / "scripts" / "lib" / "colour_categoriser.py"

COLORS = [("WHITE", "is_white"), ("YELLOW", "is_yellow"), ("REDTYPE", "is_redtype")]
CHAIN_SEEDS = {1: 42, 2: 123, 3: 456}
LLM_SOURCES = ("qwen7b", "qwen72b", "llama70b")
PC_COLS = [f"PC{i}" for i in range(1, 11)]
NITT = 1050000
BURNIN = 50000
THIN = 100
EXPECTED_N = 1149
EXPECTED_TASKS = 27


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def dataset_path(variant: str) -> Path:
    return VARDIR / f"species_color_environment_{variant}.csv"


def chain_stem(variant: str, color: str, chain: int) -> str:
    return f"{variant}_{color}_chain{chain}"


def assert_equal_cohort(datasets: dict[str, list[dict]]) -> None:
    names = {src: [r["query_name"] for r in rows] for src, rows in datasets.items()}
    ns = {src: len(rows) for src, rows in datasets.items()}
    if any(n != EXPECTED_N for n in ns.values()):
        raise SystemExit(f"expected n={EXPECTED_N} for all sources, got {ns}")
    ref_src = LLM_SOURCES[0]
    ref = names[ref_src]
    for src, seq in names.items():
        if seq != ref:
            raise SystemExit(
                f"query_name set/order differs: {ref_src} vs {src}")
        if len(seq) != len(set(seq)):
            raise SystemExit(f"duplicate query_name in {src}")
    ref_rows = datasets[ref_src]
    for src, rows in datasets.items():
        for a, b in zip(ref_rows, rows):
            if a["query_name"].split()[0] != b["query_name"].split()[0]:
                raise SystemExit(f"genus differs for {a['query_name']} ({src})")
            for pc in PC_COLS:
                if a[pc] != b[pc]:
                    raise SystemExit(
                        f"PC values differ for {a['query_name']} ({src}/{pc})")


def main() -> None:
    if not COVERAGE.exists():
        raise SystemExit(f"missing {COVERAGE}; run scripts/17_Build_Label_Variant.py first")
    summary = json.loads(COVERAGE.read_text(encoding="utf-8"))
    reported = list(summary.get("main_cohort", {}).get("variants", []))
    if reported != list(LLM_SOURCES):
        raise SystemExit(
            f"coverage_summary main_cohort variants={reported}, "
            f"expected {list(LLM_SOURCES)}")

    cat_sha = sha256_file(CATEGORISER)
    if not cat_sha:
        raise SystemExit("failed to hash colour_categoriser.py")

    datasets: dict[str, list[dict]] = {}
    digests: dict[str, str] = {}
    for variant in LLM_SOURCES:
        ds = dataset_path(variant)
        if not ds.exists():
            raise FileNotFoundError(f"variant dataset missing: {ds}")
        if "wp4_label_variants" in str(ds) or "four_source" in str(ds):
            raise SystemExit(
                f"prohibited legacy path in label-sensitivity inputs: {ds}"
            )
        digest = sha256_file(ds)
        if not digest:
            raise SystemExit(f"failed to hash {ds}")
        rows = read_rows(ds)
        datasets[variant] = rows
        digests[variant] = digest

    assert_equal_cohort(datasets)

    chaindir = VARDIR / "mcmc_chains"
    rows_out = []
    tid = 0
    for variant in LLM_SOURCES:
        ds = dataset_path(variant)
        data = datasets[variant]
        n = len(data)
        for color_label, response_col in COLORS:
            positive_n = sum(int(float(r[response_col])) for r in data)
            for chain, seed in CHAIN_SEEDS.items():
                stem = chain_stem(variant, color_label, chain)
                expected_output = str(chaindir / f"{stem}.rds")
                rows_out.append(dict(
                    task_id=tid,
                    cohort="llm_common",
                    variant=variant,
                    dataset_path=str(ds),
                    dataset_sha256=digests[variant],
                    categorizer_sha256=cat_sha,
                    n=n,
                    n_species=n,
                    positive_n=positive_n,
                    color_label=color_label,
                    response_col=response_col,
                    chain=chain,
                    seed=seed,
                    nitt=NITT,
                    burnin=BURNIN,
                    thin=THIN,
                    chain_stem=stem,
                    expected_output=expected_output,
                ))
                tid += 1

    if len(rows_out) != EXPECTED_TASKS:
        raise SystemExit(f"expected {EXPECTED_TASKS} tasks, got {len(rows_out)}")
    if any(r["variant"] == "baseline" for r in rows_out):
        raise SystemExit("baseline must not appear in main manifest")
    if any(r["cohort"] != "llm_common" for r in rows_out):
        raise SystemExit("only llm_common cohort allowed")
    if any("wp4_label_variants" in r["dataset_path"] for r in rows_out):
        raise SystemExit(
            "prohibited legacy path in manifest: wp4_label_variants"
        )
    if any("/secondary/" in r["dataset_path"] for r in rows_out):
        raise SystemExit("secondary path must not appear in main manifest")

    with MANIFEST.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
        w.writeheader()
        w.writerows(rows_out)

    print(f"cohort=llm_common  n={EXPECTED_N}  variants={list(LLM_SOURCES)}")
    print(f"Wrote manifest with {len(rows_out)} tasks -> {MANIFEST}")
    print(f"categorizer_sha256={cat_sha}")
    print(f"Submit with:  sbatch --array=0-{len(rows_out)-1} "
          f"scripts/slurm/run_19_array.slurm")


if __name__ == "__main__":
    main()
