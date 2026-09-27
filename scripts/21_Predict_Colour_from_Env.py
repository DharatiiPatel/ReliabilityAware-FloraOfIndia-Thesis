#!/usr/bin/env python3
"""
Predict flower colour from environment; headline numbers use genus-grouped CV.

A random split leaks genus identity. StratifiedGroupKFold keeps a genus in one
fold. The ungrouped split is also reported to quantify that leakage.

Reads  : Processed Data/experiments/expansion/step05b_outputs/species_color_environment_final_expanded.csv
Writes : Processed Data/experiments/prediction/
"""

from __future__ import annotations

import os

import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

BASE = (
    Path(os.environ["THESIS_ROOT"]).expanduser().resolve()
    if os.environ.get("THESIS_ROOT")
    else Path(__file__).resolve().parents[1]
)
ENV = (BASE / "Processed Data/experiments/expansion/step05b_outputs"
       / "species_color_environment_final_expanded.csv")
OUT = BASE / "Processed Data/experiments/prediction"

PCS = [f"PC{i}" for i in range(1, 11)]
CLASSES = ["WHITE", "YELLOW", "REDTYPE"]
SEED = 42
N_SPLITS = 5

def load():
    df = pd.read_csv(ENV)
    df["genus"] = df["query_name"].str.split().str[0]
    df = df.dropna(subset=PCS + ["color_group"])
    df = df[df["color_group"].isin(CLASSES)].reset_index(drop=True)
    return df

class GenusPrior:
    """Predict a genus's most common training colour; fall back to majority."""

    def fit(self, genera, y):
        self.majority_ = Counter(y).most_common(1)[0][0]
        table = {}
        for g, label in zip(genera, y):
            table.setdefault(g, Counter())[label] += 1
        self.map_ = {g: c.most_common(1)[0][0] for g, c in table.items()}
        return self

    def predict(self, genera):
        return np.array([self.map_.get(g, self.majority_) for g in genera])

def cv_evaluate(df, grouped: bool):
    """Run cross-validation and return per-model out-of-fold predictions."""
    X = df[PCS].to_numpy()
    y = df["color_group"].to_numpy()
    genera = df["genus"].to_numpy()

    if grouped:
        splitter = StratifiedGroupKFold(
            n_splits=N_SPLITS, shuffle=True, random_state=SEED)
        splits = splitter.split(X, y, groups=genera)
    else:
        splitter = StratifiedKFold(
            n_splits=N_SPLITS, shuffle=True, random_state=SEED)
        splits = splitter.split(X, y)

    models = {
        "majority": lambda: DummyClassifier(strategy="most_frequent"),
        "logreg": lambda: make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=5000, C=1.0, random_state=SEED),
        ),
        "random_forest": lambda: RandomForestClassifier(
            n_estimators=500, min_samples_leaf=3,
            random_state=SEED, n_jobs=-1,
        ),
    }

    oof = {name: np.empty(len(y), dtype=object) for name in models}
    oof["genus_prior"] = np.empty(len(y), dtype=object)

    for train_idx, test_idx in splits:
        for name, factory in models.items():
            clf = factory().fit(X[train_idx], y[train_idx])
            oof[name][test_idx] = clf.predict(X[test_idx])
        gp = GenusPrior().fit(genera[train_idx], y[train_idx])
        oof["genus_prior"][test_idx] = gp.predict(genera[test_idx])

    return y, oof

def score(y_true, y_pred):
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "balanced_accuracy": balanced_accuracy_score(y_true, y_pred),
        "macro_f1_3class": f1_score(y_true, y_pred, average="macro", zero_division=0),
        **{
            f"f1_{c}": f1_score(y_true, y_pred, labels=[c],
                                average="macro", zero_division=0)
            for c in CLASSES
        },
    }

def bootstrap_ci(y_true, y_pred, n_boot=2000, seed=SEED):
    """Species-level percentile CI for macro-F1 (legacy; can leak genus structure)."""
    rng = np.random.default_rng(seed)
    n = len(y_true)
    stats = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        if len(set(y_true[idx])) < 2:
            continue
        stats.append(f1_score(y_true[idx], y_pred[idx],
                              average="macro", zero_division=0))
    return float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5))


def genus_cluster_bootstrap_ci(y_true, y_pred, genera, n_boot=2000, seed=SEED):
    """Percentile CI resampling whole genera (appropriate for genus-grouped CV)."""
    rng = np.random.default_rng(seed)
    genera = np.asarray(genera)
    uniq = np.unique(genera)
    stats = []
    for _ in range(n_boot):
        drawn = rng.choice(uniq, size=len(uniq), replace=True)
        mask = np.isin(genera, drawn)
        # multiplicity: include each drawn genus once per draw count
        parts_y, parts_p = [], []
        for g in drawn:
            m = genera == g
            parts_y.append(y_true[m])
            parts_p.append(y_pred[m])
        yt = np.concatenate(parts_y)
        yp = np.concatenate(parts_p)
        if len(set(yt)) < 2:
            continue
        stats.append(f1_score(yt, yp, average="macro", zero_division=0))
    if len(stats) < 50:
        return float("nan"), float("nan")
    return float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5))

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    df = load()
    print(f"Species: {len(df)}   genera: {df['genus'].nunique()}")
    print("Class balance:", dict(Counter(df["color_group"])))
    print()

    rows = []
    stored = {}
    old_cis = {}
    for grouped in (True, False):
        label = "genus-grouped" if grouped else "ungrouped (leaky)"
        y, oof = cv_evaluate(df, grouped=grouped)
        stored[grouped] = (y, oof)
        genera = df["genus"].to_numpy()
        print(f"--- {label} {N_SPLITS}-fold CV ---")
        for name, pred in oof.items():
            s = score(y, pred)
            if grouped:
                lo, hi = genus_cluster_bootstrap_ci(y, pred, genera)
                lo_sp, hi_sp = bootstrap_ci(y, pred)
                old_cis[(label, name)] = (lo_sp, hi_sp)
                s.update(bootstrap="genus_cluster",
                         macro_f1_3class_lo_species_boot=lo_sp,
                         macro_f1_3class_hi_species_boot=hi_sp)
            else:
                lo, hi = bootstrap_ci(y, pred)
                s.update(bootstrap="species")
            s.update(model=name, cv=label,
                     macro_f1_3class_lo=lo, macro_f1_3class_hi=hi)
            rows.append(s)
            print(f"  {name:14s} acc={s['accuracy']:.4f}  "
                  f"balacc={s['balanced_accuracy']:.4f}  "
                  f"macroF1_3={s['macro_f1_3class']:.4f} [{lo:.3f}, {hi:.3f}] "
                  f"boot={s.get('bootstrap')}")
        print()

    if old_cis:
        print("Genus-cluster vs species bootstrap (grouped CV) CI comparison:")
        for (label, name), (lo_sp, hi_sp) in old_cis.items():
            row = next(r for r in rows if r["cv"] == label and r["model"] == name)
            print(f"  {name:14s} species[{lo_sp:.3f},{hi_sp:.3f}]  "
                  f"genus[{row['macro_f1_3class_lo']:.3f},{row['macro_f1_3class_hi']:.3f}]")

    summary = pd.DataFrame(rows)
    keep = ["cv", "model", "accuracy", "balanced_accuracy", "macro_f1_3class",
            "macro_f1_3class_lo", "macro_f1_3class_hi", "bootstrap"]
    if "macro_f1_3class_lo_species_boot" in summary.columns:
        keep += ["macro_f1_3class_lo_species_boot", "macro_f1_3class_hi_species_boot"]
    keep += [f"f1_{c}" for c in CLASSES]
    summary = summary[keep].round(4)
    summary.to_csv(OUT / "prediction_cv_summary.csv", index=False)

    y, oof = stored[True]
    best = max(("logreg", "random_forest"),
               key=lambda m: f1_score(y, oof[m], average="macro",
                                      zero_division=0))
    print(f"Best environment model under grouped CV: {best}\n")
    print(classification_report(y, oof[best], zero_division=0))

    cm = confusion_matrix(y, oof[best], labels=CLASSES)
    pd.DataFrame(cm, index=CLASSES, columns=CLASSES).to_csv(
        OUT / "prediction_confusion_grouped.csv")

    pd.DataFrame({
        "query_name": df["query_name"],
        "genus": df["genus"],
        "true": y,
        **{f"pred_{m}": oof[m] for m in oof},
    }).to_csv(OUT / "prediction_oof_predictions.csv", index=False)

    # Permutation importance for the *same* model selected by grouped CV.
    # Importance = mean drop in held-out macro-F1 after permuting each PC
    # within each genus-grouped fold (not a full-data logistic refit).
    X = df[PCS].to_numpy()
    genera = df["genus"].to_numpy()
    model_factories = {
        "logreg": lambda: make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=5000, C=1.0, random_state=SEED),
        ),
        "random_forest": lambda: RandomForestClassifier(
            n_estimators=500, min_samples_leaf=3,
            random_state=SEED, n_jobs=-1,
        ),
    }
    if best not in model_factories:
        raise SystemExit(f"no importance factory for best model {best!r}")

    splitter = StratifiedGroupKFold(
        n_splits=N_SPLITS, shuffle=True, random_state=SEED)
    # folds x features
    fold_drops = np.zeros((N_SPLITS, len(PCS)), dtype=float)
    n_repeats = 20
    for fold_i, (train_idx, test_idx) in enumerate(
            splitter.split(X, y, groups=genera)):
        clf = model_factories[best]().fit(X[train_idx], y[train_idx])
        base = f1_score(
            y[test_idx], clf.predict(X[test_idx]),
            average="macro", zero_division=0)
        rng = np.random.default_rng(SEED + fold_i)
        X_test = X[test_idx].copy()
        for j in range(len(PCS)):
            drops = []
            for rep in range(n_repeats):
                Xp = X_test.copy()
                Xp[:, j] = rng.permutation(Xp[:, j])
                pred = clf.predict(Xp)
                drops.append(
                    base - f1_score(
                        y[test_idx], pred, average="macro", zero_division=0))
            fold_drops[fold_i, j] = float(np.mean(drops))

    pi = (pd.DataFrame({
        "variable": PCS,
        "importance_mean": fold_drops.mean(axis=0),
        "importance_std": fold_drops.std(axis=0, ddof=1),
        "importance_fold_min": fold_drops.min(axis=0),
        "importance_fold_max": fold_drops.max(axis=0),
    }).sort_values("importance_mean", ascending=False).round(5))
    pi.to_csv(OUT / "prediction_permutation_importance.csv", index=False)
    print(f"\nPermutation importance (held-out macro-F1 drop, "
          f"genus-grouped CV, model={best}):")
    print(pi.to_string(index=False))

    meta = {
        "n_species": int(len(df)),
        "n_genera": int(df["genus"].nunique()),
        "class_balance": {k: int(v) for k, v in Counter(df["color_group"]).items()},
        "n_splits": N_SPLITS,
        "seed": SEED,
        "features": PCS,
        "best_env_model_grouped": best,
        "best_model_selection": (
            "max macro-F1 under 5-fold StratifiedGroupKFold "
            "among logreg and random_forest; same CV used for selection "
            "and performance estimation (not nested CV)"
        ),
        "bootstrap_grouped_cv": "genus_cluster",
        "bootstrap_ungrouped_cv": "species",
        "genus_prior_interpretation": (
            "Ungrouped genus-prior lift indicates random-split genus leakage / "
            "within-genus information leakage, not proof that biological "
            "relatedness predicts colour outside that leakage."
        ),
        "importance_model": best,
        "importance_method": (
            "permutation; mean decrease in held-out macro-F1 within each "
            "genus-grouped fold of the selected model; aggregated across folds"
        ),
        "importance_n_repeats_per_fold": n_repeats,
        "importance_aggregation": "mean and sd of per-fold mean drops",
    }
    (OUT / "prediction_run_metadata.json").write_text(json.dumps(meta, indent=2))
    print(f"\nSaved to {OUT}")

if __name__ == "__main__":
    main()
