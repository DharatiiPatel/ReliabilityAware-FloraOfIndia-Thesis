#!/usr/bin/env python3
"""Score zero-shot vs RAG predictions under categoriser V1 and V2."""
import os

import csv
import importlib.util
from pathlib import Path

BASE = (
    Path(os.environ["THESIS_ROOT"]).expanduser().resolve()
    if os.environ.get("THESIS_ROOT")
    else Path(__file__).resolve().parents[1]
)
EXP = BASE / "Processed Data" / "experiments"
GOLD = EXP / "gold_set_labeled.csv"
OUT = EXP / "categorizer_evaluation" / "intervention_scores.csv"

spec = importlib.util.spec_from_file_location(
    "c2", BASE / "scripts/14_Categorize_v2.py")
c2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c2)

PRED = {
    "qwen7b_zeroshot": EXP / "benchmark/gold_pred_qwen7b_full.csv",
    "qwen7b_rag": EXP / "categorizer_evaluation/gold_pred_qwen7b_rag.csv",
    "qwen72b_zeroshot": EXP / "benchmark/gold_pred_qwen72b.csv",
    "llama70b_zeroshot": EXP / "benchmark/gold_pred_llama70b.csv",
    "baseline": EXP / "benchmark/gold_pred_baseline.csv",
}


def score(pred_map, gold, cat_fn):
    import sys
    sys.path.insert(0, str(BASE / "scripts"))
    from lib.score_metrics import macro_f1_all5, macro_f1_target4

    ids = [s for s in gold if s in pred_map]
    yt = [gold[s] for s in ids]
    yp = []
    n_uncertain = 0
    for s in ids:
        free = (pred_map[s] or "").strip()
        if free.lower() == "uncertain" or not free:
            n_uncertain += 1
            yp.append("UNKNOWN")
        else:
            yp.append(c2.to_class(cat_fn(free)))
    n = len(ids)
    acc = sum(a == b for a, b in zip(yt, yp)) / n if n else 0
    return n, acc, n_uncertain, macro_f1_target4(yt, yp), macro_f1_all5(yt, yp)


def main():
    with open(GOLD, encoding="utf-8-sig") as f:
        gold = {r["species_id"]: c2.to_class(r["gold_category"])
                for r in csv.DictReader(f)
                if (r.get("gold_category") or "").strip()}

    rows = []
    print(f"{'model':20s} {'cat':4s} {'n':>4s} {'acc':>7s} {'F1_t4':>7s} {'F1_a5':>7s} {'unc':>5s}")
    for name, path in PRED.items():
        if not path.exists():
            print(f"{name:20s}  MISSING {path}")
            continue
        with open(path, encoding="utf-8-sig") as f:
            pred = {r["species_id"]: r.get("flower_color_free_text", "")
                    for r in csv.DictReader(f)}
        for tag, fn in [("v1", c2.categorize_v1), ("v2", c2.categorize_v2)]:
            n, acc, unc, m4, m5 = score(pred, gold, fn)
            rows.append(dict(
                model=name, categoriser=tag, n=n,
                accuracy=round(acc, 4),
                macro_f1_target4=round(m4, 4),
                macro_f1_all5=round(m5, 4),
                n_uncertain=unc,
                categorizer_name=getattr(c2, "CATEGORIZER_NAME", "V2"),
                categorizer_version=getattr(c2, "CATEGORIZER_VERSION", 2),
                categorizer_sha256=c2.module_sha256(),
            ))
            print(f"{name:20s} {tag:4s} {n:4d} {acc:7.3f} {m4:7.3f} {m5:7.3f} {unc:5d}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nSaved {OUT}")


if __name__ == "__main__":
    main()
