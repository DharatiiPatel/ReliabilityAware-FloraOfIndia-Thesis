import os
#!/usr/bin/env python3
"""
Score one or more models' flower-colour predictions against the human gold set.

For each model prediction file (id -> flower_color_free_text), we:
  1. categorise the predicted free text using the SAME rule as the pipeline
     (scripts/03_04_Categorize_and_Prepare.py) so the comparison is fair,
  2. group fine categories into the analysis classes (WHITE / YELLOW / REDTYPE /
     UNKNOWN / OTHER), matching how the gold labels are grouped,
  3. compute accuracy, per-class precision/recall/F1, macro-F1, and Cohen's kappa
     against the gold labels,
  4. print a side-by-side comparison and write a summary CSV.

Gold source: Processed Data/experiments/gold_set_template.csv
  (columns: species_id, gold_category, gold_free_text, ...)

Usage
-----
  python 12_Score_Models_vs_Gold.py \
      --pred "qwen7b=Processed Data/experiments/benchmark/gold_pred_qwen7b.csv" \
      --pred "qwen72b=Processed Data/experiments/benchmark/gold_pred_qwen72b.csv" \
      --pred "baseline=Processed Data/experiments/benchmark/gold_pred_baseline.csv"

Each --pred is  NAME=PATH . The prediction file must have columns
'species_id' and 'flower_color_free_text'.
"""

import argparse
import csv
import sys
from pathlib import Path

BASE = (
    Path(os.environ["THESIS_ROOT"]).expanduser().resolve()
    if os.environ.get("THESIS_ROOT")
    else Path(__file__).resolve().parents[1]
)
sys.path.insert(0, str(BASE / "scripts"))
from lib.score_metrics import (  # noqa: E402
    ALL5, TARGET4, macro_f1_all5, macro_f1_target4, per_class_f1,
)

GOLD = BASE / "Processed Data" / "experiments" / "gold_set_labeled.csv"

csv.field_size_limit(sys.maxsize)

# analysis classes (order fixed for stable confusion-matrix layout)
CLASSES = ALL5


def categorize_color(text: str) -> str:
    """IDENTICAL to the pipeline's categorize_color()."""
    if not text or text.strip() == "":
        return "UNKNOWN"
    t = text.lower()
    if "white" in t or "whitish" in t:
        return "WHITE"
    if "yellow" in t or "golden" in t or "pale yellow" in t or "bright yellow" in t:
        return "YELLOW"
    if "pink" in t or "pinkish" in t:
        return "PINK"
    if "red" in t:
        return "RED"
    if "purple" in t or "purplish" in t or "violet" in t or "blue" in t:
        return "PURPLE/BLUE"
    if "greenish" in t:
        return "GREENISH"
    if "no flower colour" in t:
        return "UNKNOWN"
    return "OTHER"


def to_class(fine: str) -> str:
    """Group fine categories -> analysis classes (matches pipeline REDTYPE grouping)."""
    f = (fine or "").strip().upper().replace(" ", "")
    if f in ("WHITE",):
        return "WHITE"
    if f in ("YELLOW",):
        return "YELLOW"
    if f in ("RED", "PINK", "PURPLE/BLUE", "PURPLEBLUE", "REDTYPE"):
        return "REDTYPE"
    if f in ("UNKNOWN", "NONE", "NA", "N/A", ""):
        return "UNKNOWN"
    return "OTHER"


def load_gold():
    with open(GOLD, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    gold = {}
    for r in rows:
        sid = r["species_id"]
        gc = (r.get("gold_category") or "").strip()
        if not gc:
            continue  # unlabelled row -> excluded from scoring
        gold[sid] = to_class(gc)
    return gold


def load_pred(path: Path):
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    pred = {}
    for r in rows:
        sid = r.get("species_id", "")
        pred[sid] = to_class(categorize_color(r.get("flower_color_free_text", "")))
    return pred


def score(gold: dict, pred: dict):
    ids = [sid for sid in gold if sid in pred]
    y_true = [gold[sid] for sid in ids]
    y_pred = [pred[sid] for sid in ids]
    n = len(ids)

    correct = sum(1 for a, b in zip(y_true, y_pred) if a == b)
    acc = correct / n if n else 0.0

    # per-class precision/recall/F1 (all five analysis classes)
    per = {}
    for c in CLASSES:
        tp = sum(1 for a, b in zip(y_true, y_pred) if a == c and b == c)
        fp = sum(1 for a, b in zip(y_true, y_pred) if a != c and b == c)
        fn = sum(1 for a, b in zip(y_true, y_pred) if a == c and b != c)
        support = sum(1 for a in y_true if a == c)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        per[c] = dict(precision=prec, recall=rec, f1=f1, support=support)

    m4 = macro_f1_target4(y_true, y_pred)
    m5 = macro_f1_all5(y_true, y_pred)

    # Cohen's kappa
    po = acc
    labels = set(y_true) | set(y_pred)
    pe = 0.0
    for c in labels:
        p_true = sum(1 for a in y_true if a == c) / n if n else 0
        p_pred = sum(1 for b in y_pred if b == c) / n if n else 0
        pe += p_true * p_pred
    kappa = (po - pe) / (1 - pe) if (1 - pe) else 0.0

    # confusion matrix (rows = gold, cols = pred)
    cm = {g: {p: 0 for p in CLASSES} for g in CLASSES}
    for a, b in zip(y_true, y_pred):
        cm[a][b] += 1

    return dict(
        n=n, accuracy=acc, kappa=kappa,
        macro_f1_target4=m4, macro_f1_all5=m5,
        per=per, cm=cm, present=TARGET4,
    )


def print_report(name, res):
    print("\n" + "=" * 66)
    print(f"MODEL: {name}   (n={res['n']} scored gold rows)")
    print("=" * 66)
    print(f"  Accuracy          : {res['accuracy']:.3f}")
    print(f"  Macro-F1 target4  : {res['macro_f1_target4']:.3f}  "
          f"(WHITE/YELLOW/REDTYPE/UNKNOWN; primary)")
    print(f"  Macro-F1 all5     : {res['macro_f1_all5']:.3f}  "
          f"(+OTHER with zero_division=0; supplementary)")
    print(f"  Cohen's k         : {res['kappa']:.3f}")
    print(f"  {'class':10s} {'prec':>6s} {'rec':>6s} {'f1':>6s} {'support':>8s}")
    for c in CLASSES:
        p = res["per"][c]
        print(f"  {c:10s} {p['precision']:6.3f} {p['recall']:6.3f} "
              f"{p['f1']:6.3f} {p['support']:8d}")
    print("  Confusion matrix (rows=gold, cols=pred):")
    present = [c for c in CLASSES if (res["per"][c]["support"] > 0 or
               any(res["cm"][g][c] for g in CLASSES))]
    header = "    " + "gold\\pred".ljust(10) + "".join(f"{c[:7]:>8s}" for c in present)
    print(header)
    for g in present:
        row = "    " + g.ljust(10) + "".join(f"{res['cm'][g][c]:8d}" for c in present)
        print(row)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", action="append", required=True,
                    help="NAME=PATH (repeatable)")
    ap.add_argument("--out", default="Processed Data/experiments/benchmark/benchmark_summary.csv")
    args = ap.parse_args()

    gold = load_gold()
    print(f"Loaded gold labels: {len(gold)} labelled rows "
          f"(unlabelled rows excluded).")

    summary_rows = []
    for spec in args.pred:
        if "=" not in spec:
            raise ValueError(f"--pred must be NAME=PATH, got {spec!r}")
        name, path = spec.split("=", 1)
        p = Path(path) if Path(path).is_absolute() else BASE / path
        if not p.exists():
            print(f"  WARNING: prediction file not found, skipping: {p}")
            continue
        pred = load_pred(p)
        res = score(gold, pred)
        print_report(name, res)
        summary_rows.append(dict(
            model=name, n=res["n"], accuracy=round(res["accuracy"], 4),
            macro_f1_target4=round(res["macro_f1_target4"], 4),
            macro_f1_all5=round(res["macro_f1_all5"], 4),
            kappa=round(res["kappa"], 4),
            **{f"f1_{c}": round(res["per"][c]["f1"], 4) for c in CLASSES},
        ))

    if summary_rows:
        out_path = Path(args.out) if Path(args.out).is_absolute() else BASE / args.out
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
            w.writeheader()
            w.writerows(summary_rows)
        print("\n" + "=" * 66)
        print("SIDE-BY-SIDE SUMMARY")
        print("=" * 66)
        print(f"  {'model':14s} {'n':>4s} {'acc':>6s} {'F1_t4':>8s} {'F1_a5':>8s} {'kappa':>7s}")
        for r in summary_rows:
            print(f"  {r['model']:14s} {r['n']:4d} {r['accuracy']:6.3f} "
                  f"{r['macro_f1_target4']:8.3f} {r['macro_f1_all5']:8.3f} "
                  f"{r['kappa']:7.3f}")
        print(f"\nSaved summary: {out_path}")
        print("Primary Macro-F1 = macro_f1_target4 "
              "(WHITE/YELLOW/REDTYPE/UNKNOWN).")


if __name__ == "__main__":
    main()
