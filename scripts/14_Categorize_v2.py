#!/usr/bin/env python3
"""
V2 categoriser — main scripts entry point.

Implementation: scripts/lib/colour_categoriser.py
Import V2 from this file (or the shared module; same functions).

Terminology
  V1 — original categoriser (scripts/03_04_Categorize_and_Prepare.py), unchanged.
  V2 — this categoriser (post-construction reclassification / sensitivity).

The 1,438-species primary cohort was constructed before the categorisation
refinement. Error analysis of V1 motivated V2. V2 was subsequently applied
within the primary cohort to evaluate label sensitivity and downstream
reliability without changing the environmental species sample.

Usage:
  python scripts/14_Categorize_v2.py              # self-check + metadata
  python scripts/14_Categorize_v2.py --rescore    # V1 vs V2 gold scores
  python scripts/14_Categorize_v2.py --version
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

BASE = (
    Path(os.environ["THESIS_ROOT"]).expanduser().resolve()
    if os.environ.get("THESIS_ROOT")
    else Path(__file__).resolve().parents[1]
)
V1_SOURCE = BASE / "scripts" / "03_04_Categorize_and_Prepare.py"
sys.path.insert(0, str(BASE / "scripts"))

from lib.colour_categoriser import (  # noqa: E402
    CATEGORIZER_NAME,
    CATEGORIZER_VERSION,
    V2_ONTOLOGY,
    categorize_coarse,
    categorize_fine,
    categorize_v2,
    is_ecology_known,
    module_sha256,
    to_analysis_class,
)

# Back-compat alias
V2_VERSION = CATEGORIZER_VERSION

__all__ = [
    "BASE",
    "V1_SOURCE",
    "CATEGORIZER_NAME",
    "CATEGORIZER_VERSION",
    "V2_VERSION",
    "V2_ONTOLOGY",
    "categorize_v2",
    "categorize_fine",
    "categorize_coarse",
    "to_analysis_class",
    "to_class",
    "is_ecology_known",
    "module_sha256",
    "categorize_v1",
]

to_class = to_analysis_class

EXP = BASE / "Processed Data" / "experiments"
GOLD = EXP / "gold_set_labeled.csv"
OUTDIR = EXP / "categorizer_evaluation"

PRED_FILES = {
    "baseline": EXP / "benchmark/gold_pred_baseline.csv",
    "qwen7b": EXP / "benchmark/gold_pred_qwen7b_full.csv",
    "qwen72b": EXP / "benchmark/gold_pred_qwen72b.csv",
    "llama70b": EXP / "benchmark/gold_pred_llama70b.csv",
}


def categorize_v1(text: str) -> str:
    """Historical V1 fine categoriser (loaded without modifying 03_04)."""
    import importlib.util
    path = V1_SOURCE
    if not path.is_file():
        raise FileNotFoundError(f"V1 categoriser not found at {path}")
    # Refuse silently reaching into another checkout.
    if path.resolve().parents[1] != BASE.resolve():
        raise RuntimeError(f"V1 source escapes package root: {path} vs {BASE}")
    spec = importlib.util.spec_from_file_location("cat_v1", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.categorize_color(text)


def score(pred_map, gold, categorizer_fine):
    import sys
    sys.path.insert(0, str(BASE / "scripts"))
    from lib.score_metrics import macro_f1_all5, macro_f1_target4

    ids = [sid for sid in gold if sid in pred_map]
    y_true = [gold[sid] for sid in ids]
    y_pred = [to_analysis_class(categorizer_fine(pred_map[sid])) for sid in ids]
    n = len(ids)
    correct = sum(a == b for a, b in zip(y_true, y_pred))
    acc = correct / n if n else 0.0
    m4 = macro_f1_target4(y_true, y_pred)
    m5 = macro_f1_all5(y_true, y_pred)
    po = acc
    labels = set(y_true) | set(y_pred)
    pe = 0.0
    for c in labels:
        pe += (sum(a == c for a in y_true) / n) * (sum(b == c for b in y_pred) / n)
    kappa = (po - pe) / (1 - pe) if (1 - pe) else 0.0
    return dict(
        n=n, accuracy=acc, kappa=kappa, n_wrong=n - correct,
        macro_f1_target4=m4, macro_f1_all5=m5,
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rescore", action="store_true",
                    help="Compare V1 vs V2 on gold predictions")
    ap.add_argument("--version", action="store_true")
    args = ap.parse_args()

    sha = module_sha256()
    if args.version:
        print(f"categorizer_name={CATEGORIZER_NAME}")
        print(f"categorizer_version={CATEGORIZER_VERSION}")
        print(f"categorizer_sha256={sha}")
        print(f"primary_anchor_n=1438")
        print(f"module=scripts/lib/colour_categoriser.py")
        print(f"entry=scripts/14_Categorize_v2.py")
        return

    if not args.rescore:
        print(f"V2 categoriser  version={CATEGORIZER_VERSION}  sha256={sha}")
        print("Self-check (analysis class):")
        cases = [
            ("flowers pinkish or white", "REDTYPE"),
            ("flowers brilliant scarlet, yellow in centre", "REDTYPE"),
            ("petals orange-red", "REDTYPE"),
            ("petals maroon coloured", "REDTYPE"),
            ("flowers rose-coloured", "REDTYPE"),
            ("cream-coloured flowers", "YELLOW"),
            ("no flower colour mentioned", "UNKNOWN"),
            ("uncertain", "UNKNOWN"),
            ("flesh-coloured", "OTHER"),
            ("flowers white", "WHITE"),
        ]
        for text, expect in cases:
            got = categorize_v2(text)
            ok = "OK" if got == expect else "FAIL"
            print(f"  [{ok}] {text!r} -> {got} (expect {expect})")
        return

    OUTDIR.mkdir(parents=True, exist_ok=True)
    with open(GOLD, encoding="utf-8-sig") as f:
        gold_rows = list(csv.DictReader(f))
    gold = {
        r["species_id"]: to_analysis_class(r["gold_category"])
        for r in gold_rows if (r.get("gold_category") or "").strip()
    }

    summary = []
    for model, path in PRED_FILES.items():
        if not path.exists():
            print(f"skip missing {path}")
            continue
        with open(path, encoding="utf-8-sig") as f:
            pred_map = {
                r["species_id"]: r.get("flower_color_free_text", "")
                for r in csv.DictReader(f)
            }
        s1 = score(pred_map, gold, categorize_v1)
        s2 = score(pred_map, gold, categorize_fine)
        summary.append(dict(
            model=model,
            n=s1["n"],
            acc_v1=round(s1["accuracy"], 4),
            kappa_v1=round(s1["kappa"], 4),
            macro_f1_target4_v1=round(s1["macro_f1_target4"], 4),
            macro_f1_all5_v1=round(s1["macro_f1_all5"], 4),
            wrong_v1=s1["n_wrong"],
            acc_v2=round(s2["accuracy"], 4),
            kappa_v2=round(s2["kappa"], 4),
            macro_f1_target4_v2=round(s2["macro_f1_target4"], 4),
            macro_f1_all5_v2=round(s2["macro_f1_all5"], 4),
            wrong_v2=s2["n_wrong"],
            delta_acc=round(s2["accuracy"] - s1["accuracy"], 4),
            categorizer_name=CATEGORIZER_NAME,
            categorizer_version=CATEGORIZER_VERSION,
            categorizer_sha256=sha,
            primary_anchor_n=1438,
            evaluation_note=(
                "Same gold set used in method development; not external validation"
            ),
        ))
        print(f"{model:10s}  v1 acc={s1['accuracy']:.3f} (wrong={s1['n_wrong']})  "
              f"v2 acc={s2['accuracy']:.3f} (wrong={s2['n_wrong']})  "
              f"Δ={s2['accuracy']-s1['accuracy']:+.3f}")

    out = OUTDIR / "categorizer_comparison.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        w.writeheader()
        w.writerows(summary)
    print(f"\nSaved: {out}")
    print(f"categorizer_sha256={sha}")


if __name__ == "__main__":
    main()
