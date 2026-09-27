#!/usr/bin/env python3
"""
Publication-quality figures for the method-depth chapters.

Design rules followed here:
  * no bar charts - estimates are shown with uncertainty (dot plots, forests)
  * titles are short; captions live in the thesis, not on the figure
  * no annotation is drawn inside the data area unless it has reserved space
  * vector (PDF) + raster (PNG at 400 dpi) output for both LaTeX and Word

Outputs -> Processed Data/experiments/figures/
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/mplconfig")
Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)

import matplotlib as mpl  # noqa: E402

mpl.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

import sys  # noqa: E402

BASE = (
    Path(os.environ["THESIS_ROOT"]).expanduser().resolve()
    if os.environ.get("THESIS_ROOT")
    else Path(__file__).resolve().parents[1]
)
sys.path.insert(0, str(BASE / "scripts" / "lib"))
from figure_style import (  # noqa: E402
    CLASS_COLOR, GRID, INK, MUTED, apply as apply_style,
)

apply_style()

EXP = BASE / "Processed Data" / "experiments"
OUT = EXP / "figures"
OUT.mkdir(parents=True, exist_ok=True)
PUBLISH = BASE / "Results" / "figures" / "methods"

import importlib.util  # noqa: E402


def _load_module(name: str, filename: str):
    # 12_Score_Models_vs_Gold.py / 14_Categorize_v2.py have leading digits, so
    # they cannot be imported as normal modules - load by path instead.
    spec = importlib.util.spec_from_file_location(
        name, BASE / "scripts" / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_smg = _load_module("smg", "12_Score_Models_vs_Gold.py")
CLASSES, load_gold, load_pred = _smg.CLASSES, _smg.load_gold, _smg.load_pred

c2 = _load_module("c2", "14_Categorize_v2.py")


# --------------------------------------------------------------------------
# Shared style (see scripts/lib/figure_style.py)
# --------------------------------------------------------------------------

# All ten environmental PCs are modelled, so fig12/fig13 show all ten. Truncating
# to PC1-PC5 hid two of the five significant effects (WHITE x PC9, REDTYPE x PC7).
ALL_PCS = [f"PC{i}" for i in range(1, 11)]

MODEL_ORDER = ["baseline", "qwen7b", "qwen72b", "llama70b"]
# Equal three-LLM common cohort for fig12/fig13 (n=1,149; no baseline).
LS_MODEL_ORDER = ["qwen7b", "qwen72b", "llama70b"]
MODEL_LABELS = {
    "baseline": "Keyword baseline",
    "qwen7b": "Qwen2.5-7B",
    "qwen72b": "Qwen2.5-72B",
    "llama70b": "Llama-3.3-70B",
}
MODEL_COLOR = {
    "baseline": "#9a9a9a",
    "qwen7b": "#1f6f78",
    "qwen72b": "#2e4a7d",
    "llama70b": "#b4622d",
}
PRED_FILES = {
    "baseline": EXP / "benchmark" / "gold_pred_baseline.csv",
    "qwen7b": EXP / "benchmark" / "gold_pred_qwen7b_full.csv",
    "qwen72b": EXP / "benchmark" / "gold_pred_qwen72b.csv",
    "llama70b": EXP / "benchmark" / "gold_pred_llama70b.csv",
}

CMAP_SEQ = LinearSegmentedColormap.from_list(
    "thesis_seq", ["#fbfcfc", "#dceaec", "#a8ccd1", "#5f9fa8", "#256d78", "#0e3d47"]
)
CMAP_DIV = LinearSegmentedColormap.from_list(
    "thesis_div", ["#8c3b1b", "#c9865c", "#ece9e4", "#6ba39b", "#14524a"]
)


def save(fig, name: str):
    """Save PDF + PNG. Captions belong in the thesis, not on the figure."""
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"{name}.{ext}", bbox_inches="tight",
                    facecolor="white", pad_inches=0.20)
        PUBLISH.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(OUT / f"{name}.{ext}", PUBLISH / f"{name}.{ext}")
    plt.close(fig)
    print(f"  {name}.pdf / .png")


def bh_qvalues(pvals):
    """Benjamini-Hochberg q-values, order preserved."""
    p = np.asarray(pvals, dtype=float)
    n = len(p)
    order = np.argsort(p)
    ranked = p[order] * n / np.arange(1, n + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.minimum(ranked, 1.0)
    return out


def despread(values, min_gap):
    """Nudge label positions apart while preserving order (label de-collision)."""
    order = np.argsort(values)
    out = np.array(values, dtype=float)
    for k in range(1, len(order)):
        i, j = order[k - 1], order[k]
        if out[j] - out[i] < min_gap:
            out[j] = out[i] + min_gap
    return out


def panel_tag(ax, letter, dx=-0.14, dy=1.06):
    ax.text(dx, dy, letter, transform=ax.transAxes, fontsize=11,
            fontweight="bold", va="top", ha="left", color=INK)


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------

def aligned(gold: dict, pred: dict):
    ids = [s for s in gold if s in pred]
    return ids, np.array([gold[s] for s in ids]), np.array([pred[s] for s in ids])


def accuracy(yt, yp):
    return float((yt == yp).mean())


def kappa(yt, yp):
    n = len(yt)
    po = (yt == yp).mean()
    pe = 0.0
    for c in set(yt) | set(yp):
        pe += (yt == c).mean() * (yp == c).mean()
    return float((po - pe) / (1 - pe)) if pe < 1 else 0.0


BOOT_N = 4000


def boot_ci(yt, yp, fn, n_boot=BOOT_N, seed=7):
    rng = np.random.default_rng(seed)
    n = len(yt)
    vals = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, n, n)
        vals[b] = fn(yt[idx], yp[idx])
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def per_class_f1(yt, yp, classes):
    out = {}
    for c in classes:
        tp = int(((yt == c) & (yp == c)).sum())
        fp = int(((yt != c) & (yp == c)).sum())
        fn = int(((yt == c) & (yp != c)).sum())
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        out[c] = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return out


def model_predictions():
    gold = load_gold()
    data = {}
    for m in MODEL_ORDER:
        ids, yt, yp = aligned(gold, load_pred(PRED_FILES[m]))
        data[m] = dict(ids=ids, yt=yt, yp=yp)
    return gold, data


# --------------------------------------------------------------------------
# Figure 1 - benchmark dot plot with bootstrap intervals + per-class F1
# --------------------------------------------------------------------------

def fig1_benchmark(gold, data):
    fig = plt.figure(figsize=(9.6, 4.3), constrained_layout=True)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.28, 1.0], wspace=0.06)
    axL = fig.add_subplot(gs[0, 0])
    axR = fig.add_subplot(gs[0, 1])

    ys = np.arange(len(MODEL_ORDER))[::-1]
    off = 0.17

    for y, m in zip(ys, MODEL_ORDER):
        yt, yp = data[m]["yt"], data[m]["yp"]
        acc, kap = accuracy(yt, yp), kappa(yt, yp)
        acc_lo, acc_hi = boot_ci(yt, yp, accuracy)
        kap_lo, kap_hi = boot_ci(yt, yp, kappa)
        col = MODEL_COLOR[m]

        axL.plot([acc_lo, acc_hi], [y + off] * 2, color=col, lw=2.2,
                 solid_capstyle="round", alpha=0.55, zorder=2)
        axL.scatter([acc], [y + off], s=64, color=col, zorder=3,
                    edgecolor="white", linewidth=1.0)
        axL.plot([kap_lo, kap_hi], [y - off] * 2, color=col, lw=2.2,
                 solid_capstyle="round", alpha=0.30, zorder=2)
        axL.scatter([kap], [y - off], s=64, facecolor="white", zorder=3,
                    edgecolor=col, linewidth=1.6)

        axL.text(acc_hi + 0.012, y + off, f"{acc:.3f}", va="center",
                 ha="left", fontsize=7.5, color=col)
        axL.text(kap_hi + 0.012, y - off, f"{kap:.3f}", va="center",
                 ha="left", fontsize=7.5, color=MUTED)

    axL.set_yticks(ys)
    axL.set_yticklabels([MODEL_LABELS[m] for m in MODEL_ORDER])
    axL.set_xlim(0.58, 1.03)
    axL.set_ylim(-0.62, len(MODEL_ORDER) - 0.38)
    axL.set_xlabel("Score against human gold labels (95% bootstrap interval)")
    axL.set_title("Agreement with the gold set", loc="left")
    axL.xaxis.grid(True, color=GRID, lw=0.6)
    axL.set_axisbelow(True)
    axL.spines["left"].set_visible(False)
    axL.tick_params(axis="y", length=0)

    axL.legend(handles=[
        Line2D([], [], marker="o", ls="", color="#3f3f3f", ms=7,
               markeredgecolor="white", label="Accuracy"),
        Line2D([], [], marker="o", ls="", mfc="white", mec="#3f3f3f",
               mew=1.6, ms=7, label="Cohen's \u03ba"),
    ], loc="lower left", frameon=False, ncol=2, handletextpad=0.4,
        columnspacing=1.4, bbox_to_anchor=(0.0, -0.02))

    # ---- right: per-class F1 heatmap ----
    show = ["WHITE", "YELLOW", "REDTYPE", "UNKNOWN"]
    mat = np.array([[per_class_f1(data[m]["yt"], data[m]["yp"], show)[c]
                     for c in show] for m in MODEL_ORDER])
    im = axR.imshow(mat, cmap=CMAP_SEQ, vmin=0.65, vmax=1.0, aspect="auto")
    axR.set_xticks(range(len(show)))
    axR.set_xticklabels(show, fontsize=8)
    axR.set_yticks(range(len(MODEL_ORDER)))
    axR.set_yticklabels([MODEL_LABELS[m] for m in MODEL_ORDER], fontsize=8)
    axR.set_title("Per-class F$_1$", loc="left")
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            v = mat[i, j]
            axR.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=8,
                     color="white" if v > 0.88 else INK)
    for s in axR.spines.values():
        s.set_visible(False)
    axR.tick_params(length=0)
    cb = fig.colorbar(im, ax=axR, fraction=0.045, pad=0.03)
    cb.set_label("F$_1$", fontsize=8)
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=7, length=2)

    fig.suptitle(f"Multi-model benchmark on the gold set (n = {len(gold)})",
                 fontsize=12, fontweight="bold", x=0.008, ha="left")
    save(fig, "fig7_benchmark")


# --------------------------------------------------------------------------
# Figure 2 - row-normalised confusion small multiples
# --------------------------------------------------------------------------

def fig2_confusion(data):
    rows = ["WHITE", "YELLOW", "REDTYPE", "UNKNOWN"]
    cols = CLASSES  # includes OTHER as a prediction-only sink

    fig, axes = plt.subplots(1, 4, figsize=(12.2, 3.5), constrained_layout=True,
                             sharey=True)
    im = None
    for ax, m in zip(axes, MODEL_ORDER):
        yt, yp = data[m]["yt"], data[m]["yp"]
        counts = np.array([[int(((yt == g) & (yp == p)).sum()) for p in cols]
                           for g in rows], dtype=float)
        support = counts.sum(axis=1, keepdims=True)
        frac = np.divide(counts, support, out=np.zeros_like(counts),
                         where=support > 0)
        im = ax.imshow(frac, cmap=CMAP_SEQ, vmin=0, vmax=1, aspect="auto")

        for i in range(len(rows)):
            for j in range(len(cols)):
                if counts[i, j] == 0:
                    continue
                ax.text(j, i, f"{int(counts[i, j])}", ha="center", va="center",
                        fontsize=8.5,
                        color="white" if frac[i, j] > 0.55 else INK)

        ax.set_xticks(range(len(cols)))
        ax.set_xticklabels(cols, rotation=42, ha="right", fontsize=7.5)
        ax.set_xlabel("predicted")
        ax.set_title(f"{MODEL_LABELS[m]}\naccuracy {accuracy(yt, yp):.3f}",
                     loc="left", fontsize=9)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.tick_params(length=0)
        ax.set_xticks(np.arange(-0.5, len(cols), 1), minor=True)
        ax.set_yticks(np.arange(-0.5, len(rows), 1), minor=True)
        ax.grid(which="minor", color="white", lw=1.4)

    axes[0].set_yticks(range(len(rows)))
    axes[0].set_yticklabels(rows, fontsize=8)
    axes[0].set_ylabel("gold class")

    cb = fig.colorbar(im, ax=axes, fraction=0.018, pad=0.012)
    cb.set_label("share of gold class", fontsize=8)
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=7, length=2)

    fig.suptitle("Confusion structure against gold labels",
                 fontsize=12, fontweight="bold", x=0.005, ha="left")
    save(fig, "fig8_confusion")


# --------------------------------------------------------------------------
# Figure 3 - alluvial flow, gold -> prediction
# --------------------------------------------------------------------------

def _ribbon(ax, x0, x1, y0b, y0t, y1b, y1t, color, alpha):
    t = np.linspace(0, 1, 160)
    s = 0.5 * (1 - np.cos(np.pi * t))
    x = x0 + (x1 - x0) * t
    top = y0t + (y1t - y0t) * s
    bot = y0b + (y1b - y0b) * s
    ax.fill_between(x, bot, top, color=color, alpha=alpha, lw=0, zorder=1)


def _alluvial(ax, yt, yp, title):
    rows = ["WHITE", "YELLOW", "REDTYPE", "UNKNOWN"]
    cols = [c for c in CLASSES if (yp == c).sum() > 0]
    n = len(yt)
    gap = max(n * 0.030, 1.4)

    left_h = {g: int((yt == g).sum()) for g in rows}
    right_h = {p: int((yp == p).sum()) for p in cols}

    def stack(order, heights):
        pos, y = {}, 0.0
        for k in order:
            pos[k] = (y, y + heights[k])
            y += heights[k] + gap
        return pos, y - gap

    lpos, ltot = stack(rows, left_h)
    rpos, rtot = stack(cols, right_h)
    shift = (ltot - rtot) / 2.0
    rpos = {k: (a + shift, b + shift) for k, (a, b) in rpos.items()}

    x0, x1, bw = 0.0, 1.0, 0.055
    lcur = {g: lpos[g][0] for g in rows}
    rcur = {p: rpos[p][0] for p in cols}

    for g in rows:
        for p in cols:
            c = int(((yt == g) & (yp == p)).sum())
            if c == 0:
                continue
            correct = g == p
            _ribbon(ax, x0 + bw, x1 - bw,
                    lcur[g], lcur[g] + c, rcur[p], rcur[p] + c,
                    CLASS_COLOR[g] if correct else "#b8503f",
                    0.42 if correct else 0.62)
            lcur[g] += c
            rcur[p] += c

    for g in rows:
        a, b = lpos[g]
        ax.fill_between([x0 - bw, x0 + bw], a, b, color=CLASS_COLOR[g],
                        lw=0, zorder=3)
        ax.text(x0 - bw - 0.035, (a + b) / 2, f"{g}  {left_h[g]}", ha="right",
                va="center", fontsize=8, color=INK)
    for p in cols:
        a, b = rpos[p]
        ax.fill_between([x1 - bw, x1 + bw], a, b, color=CLASS_COLOR[p],
                        lw=0, zorder=3)
        ax.text(x1 + bw + 0.035, (a + b) / 2, f"{right_h[p]}  {p}", ha="left",
                va="center", fontsize=8, color=INK)

    n_err = int((yt != yp).sum())
    ax.set_title(f"{title}  ({n_err} misrouted of {n})", loc="left")
    ax.set_xlim(-0.52, 1.52)
    ax.set_ylim(-gap, max(ltot, rtot + shift) + gap)
    ax.axis("off")


def fig3_flow(data):
    fig, axes = plt.subplots(1, 2, figsize=(11.4, 5.0), constrained_layout=True)
    _alluvial(axes[0], data["baseline"]["yt"], data["baseline"]["yp"],
              "Keyword baseline")
    _alluvial(axes[1], data["qwen7b"]["yt"], data["qwen7b"]["yp"],
              "Qwen2.5-7B")
    for ax in axes:
        ax.text(0.5, -0.005, "gold to predicted", transform=ax.transAxes,
                ha="center", va="top", fontsize=8, color=MUTED)

    fig.legend(handles=[
        Patch(facecolor="#9aa8a4", alpha=0.5,
              label="correctly routed (shaded by gold class)"),
        Patch(facecolor="#b8503f", alpha=0.62, label="misrouted"),
    ], loc="lower center", ncol=2, frameon=False, bbox_to_anchor=(0.5, -0.055))

    fig.suptitle("Label flow from gold class to prediction",
                 fontsize=12, fontweight="bold", x=0.005, ha="left")
    save(fig, "fig9_label_flow")


# --------------------------------------------------------------------------
# Figure 4 - error taxonomy bubble matrix
# --------------------------------------------------------------------------

def fig4_taxonomy():
    err = pd.read_csv(EXP / "categorizer_evaluation" / "gold_disagreements_by_error_class.csv")
    nice = {
        "CATEGORY_PRIORITY": "Category priority",
        "MULTI_COLOUR": "Multi-colour description",
        "JUNK_NON_SPECIES": "Junk / non-species row",
        "FALSE_NEGATIVE": "Missed colour (FN)",
        "FALSE_POSITIVE": "Invented colour (FP)",
        "CONTAMINATION": "Cross-organ contamination",
        "INDUMENT_TEXTURE": "Indument / texture confusion",
    }
    err["label"] = err["error_class"].map(nice).fillna(err["error_class"])
    tab = (err.groupby(["model", "label"]).size().unstack(fill_value=0)
           .reindex(MODEL_ORDER).fillna(0))
    order = tab.sum().sort_values(ascending=True).index.tolist()
    tab = tab[order]

    fig = plt.figure(figsize=(9.8, 4.6), constrained_layout=True)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.0, 0.30], wspace=0.04)
    ax = fig.add_subplot(gs[0, 0])
    axm = fig.add_subplot(gs[0, 1], sharey=ax)

    xs = np.arange(len(MODEL_ORDER))
    ys = np.arange(len(order))
    for j, cls in enumerate(order):
        for i, m in enumerate(MODEL_ORDER):
            v = int(tab.loc[m, cls])
            if v == 0:
                ax.scatter(i, j, s=16, marker="x", color="#d5d5d5", zorder=2)
                continue
            ax.scatter(i, j, s=190 + 240 * v / tab.values.max(),
                       color=MODEL_COLOR[m], alpha=0.85, zorder=3,
                       edgecolor="white", linewidth=1.0)
            ax.text(i, j, str(v), ha="center", va="center", fontsize=8,
                    color="white", fontweight="bold", zorder=4)

    ax.set_xticks(xs)
    ax.set_xticklabels([MODEL_LABELS[m] for m in MODEL_ORDER], fontsize=8.5)
    ax.set_yticks(ys)
    ax.set_yticklabels(order, fontsize=8.5)
    ax.set_xlim(-0.6, len(MODEL_ORDER) - 0.4)
    ax.set_ylim(-0.7, len(order) - 0.3)
    ax.grid(True, color=GRID, lw=0.6, ls=":")
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.tick_params(length=0)

    # marginal: total per error class as a lollipop (not a bar)
    totals = tab.sum().values
    axm.hlines(ys, 0, totals, color="#c8ccc9", lw=1.2, zorder=1)
    axm.scatter(totals, ys, s=42, color="#3c4a4f", zorder=2)
    for j, t in enumerate(totals):
        axm.text(t + totals.max() * 0.06, j, str(int(t)), va="center",
                 fontsize=7.5, color=MUTED)
    axm.set_xlim(0, totals.max() * 1.42)
    axm.set_xlabel("all models")
    axm.set_title("total", loc="left", fontsize=9)
    axm.tick_params(labelleft=False, length=0)
    axm.spines["left"].set_visible(False)
    axm.xaxis.grid(True, color=GRID, lw=0.6)
    axm.set_axisbelow(True)

    fig.suptitle("Error taxonomy of disagreements with gold",
                 fontsize=12, fontweight="bold", x=0.005, ha="left")
    save(fig, "fig10_error_taxonomy")


# --------------------------------------------------------------------------
# Figure 5 - intervention slopegraph + item-level repair grid
# --------------------------------------------------------------------------

def _short(sid: str) -> str:
    s = re.sub(r"^\s*\d+[a-z]?\.\s*", "", str(sid))
    toks = re.findall(r"[A-Za-z][A-Za-z'\-]+", s)
    if not toks:
        return "(blank)"
    lab = toks[0][:12]
    if len(toks) > 1 and toks[1].islower():
        lab += " " + toks[1][:11]
    return lab


def fig5_interventions():
    vcmp = pd.read_csv(EXP / "categorizer_evaluation" / "categorizer_comparison.csv")
    vcmp["model"] = pd.Categorical(vcmp["model"], MODEL_ORDER, ordered=True)
    vcmp = vcmp.sort_values("model")

    fig = plt.figure(figsize=(12.4, 5.0), constrained_layout=True)
    gs = fig.add_gridspec(1, 2, width_ratios=[0.72, 1.55], wspace=0.05)
    axS = fig.add_subplot(gs[0, 0])
    axG = fig.add_subplot(gs[0, 1])

    # ---- A: slopegraph v1 -> v2 ----
    models = list(vcmp["model"])
    v1 = vcmp["acc_v1"].to_numpy(dtype=float)
    v2 = vcmp["acc_v2"].to_numpy(dtype=float)
    ylo, yhi = 0.735, 0.965
    gap = (yhi - ylo) * 0.055
    lab1 = despread(v1, gap)
    lab2 = despread(v2, gap)

    for k, m in enumerate(models):
        col = MODEL_COLOR[m]
        axS.plot([0, 1], [v1[k], v2[k]], color=col, lw=2.0,
                 solid_capstyle="round", zorder=2)
        axS.scatter([0, 1], [v1[k], v2[k]], s=46, color=col,
                    zorder=3, edgecolor="white", linewidth=1.0)
        # leader lines only where the label had to be nudged
        if abs(lab1[k] - v1[k]) > 1e-9:
            axS.plot([-0.055, -0.015], [lab1[k], v1[k]], color=col, lw=0.6,
                     alpha=0.6, zorder=1)
        if abs(lab2[k] - v2[k]) > 1e-9:
            axS.plot([1.015, 1.055], [v2[k], lab2[k]], color=col, lw=0.6,
                     alpha=0.6, zorder=1)
        axS.text(-0.075, lab1[k], f"{v1[k]:.3f}", ha="right",
                 va="center", fontsize=8, color=col)
        axS.text(1.075, lab2[k],
                 f"{v2[k]:.3f}  (+{v2[k] - v1[k]:.3f})   {MODEL_LABELS[m]}",
                 ha="left", va="center", fontsize=8, color=col)

    axS.set_xlim(-0.62, 2.30)
    axS.set_ylim(ylo, yhi)
    axS.set_xticks([0, 1])
    axS.set_xticklabels(["categoriser v1", "categoriser v2"], fontsize=8.5)
    axS.set_ylabel("Accuracy on gold set")
    axS.set_title("Accuracy under categoriser v1 and v2", loc="left", fontsize=9.5)
    axS.yaxis.grid(True, color=GRID, lw=0.6)
    axS.set_axisbelow(True)
    axS.spines["bottom"].set_visible(False)
    axS.tick_params(axis="x", length=0)
    panel_tag(axS, "A", dx=-0.20)

    # ---- B: item-level repair grid for the Qwen-7B ladder ----
    gold = load_gold()
    configs = [
        ("Zero-shot, v1", EXP / "benchmark/gold_pred_qwen7b_full.csv", c2.categorize_v1),
        ("Zero-shot, v2", EXP / "benchmark/gold_pred_qwen7b_full.csv", c2.categorize_v2),
        ("RAG, v1", EXP / "categorizer_evaluation/gold_pred_qwen7b_rag.csv", c2.categorize_v1),
        ("RAG, v2", EXP / "categorizer_evaluation/gold_pred_qwen7b_rag.csv", c2.categorize_v2),
    ]
    raw = {}
    for _, path, _fn in configs:
        if path not in raw:
            # keep_default_na=False so an empty species_id stays "" and still
            # matches the gold key, reproducing the published accuracies
            df = pd.read_csv(path, keep_default_na=False)
            raw[path] = dict(zip(df["species_id"], df["flower_color_free_text"]))

    ids = sorted(gold)
    n_scored = len(ids)
    correct = np.zeros((len(configs), n_scored), dtype=bool)
    abstain = np.zeros((len(configs), n_scored), dtype=bool)
    for r, (_, path, fn) in enumerate(configs):
        pm = raw[path]
        for cidx, sid in enumerate(ids):
            free = (pm.get(sid) or "").strip()
            # scoring convention: an explicit abstention is read as UNKNOWN
            if free.lower() == "uncertain":
                abstain[r, cidx] = True
                pred = "UNKNOWN"
            else:
                pred = c2.to_class(fn(free))
            correct[r, cidx] = pred == gold[sid]

    flagged = [i for i in range(n_scored)
               if (~correct[:, i]).any() or abstain[:, i].any()]
    order = sorted(flagged, key=lambda i: (-int((~correct[:, i]).sum()),
                                           tuple((~correct[:, i]).astype(int))))
    labels = [_short(ids[i]) for i in order]
    k = len(order)

    C_OK, C_BAD = "#2f7f78", "#b8503f"
    for r in range(len(configs)):
        for cidx, i in enumerate(order):
            axG.add_patch(plt.Rectangle(
                (cidx + 0.08, r + 0.10), 0.84, 0.80,
                facecolor=C_OK if correct[r, i] else C_BAD,
                edgecolor="white", lw=0.8, zorder=2))
            if abstain[r, i]:
                axG.add_patch(plt.Rectangle(
                    (cidx + 0.08, r + 0.10), 0.84, 0.80, facecolor="none",
                    edgecolor="white", lw=0.0, hatch="////", zorder=3))

    axG.set_ylim(len(configs), 0)
    axG.set_xticks(np.arange(k) + 0.5)
    axG.set_xticklabels(labels, rotation=90, fontsize=6.6)
    axG.set_yticks(np.arange(len(configs)) + 0.5)
    axG.set_yticklabels([c[0] for c in configs], fontsize=8.5)
    axG.tick_params(length=0)
    for s in axG.spines.values():
        s.set_visible(False)

    axG.set_xlim(0, k)
    ax2 = axG.twinx()
    ax2.set_ylim(axG.get_ylim())
    ax2.set_yticks(np.arange(len(configs)) + 0.5)
    ax2.set_yticklabels([f"{correct[r].sum() / n_scored:.3f}"
                         for r in range(len(configs))],
                        fontsize=9, fontweight="bold")
    ax2.set_ylabel(f"accuracy on all {n_scored} items", fontsize=8,
                   color=MUTED, labelpad=8)
    ax2.tick_params(length=0)
    for s in ax2.spines.values():
        s.set_visible(False)

    axG.set_title(f"Qwen2.5-7B: {k} items still failed or abstained",
                  loc="left", fontsize=9.5)
    axG.legend(handles=[
        Patch(facecolor=C_OK, label="correct"),
        Patch(facecolor=C_BAD, label="incorrect"),
        Patch(facecolor="#8d8d8d", hatch="////", edgecolor="white",
              label="model abstained"),
    ], loc="upper left", bbox_to_anchor=(0.0, -0.36), ncol=3, frameon=False)
    panel_tag(axG, "B", dx=-0.075)

    fig.suptitle("Categoriser mapping and retrieval interventions",
                 fontsize=12, fontweight="bold",
                 x=0.005, ha="left")
    save(fig, "fig11_interventions")


# --------------------------------------------------------------------------
# Figure 12 - forest across label sources
# --------------------------------------------------------------------------

def fig6_forest():
    fx = pd.read_csv(EXP / "label_sensitivity" / "results" /
                     "label_sensitivity_effects.csv")
    present = sorted(fx.variant.unique().tolist())
    if present != sorted(LS_MODEL_ORDER):
        raise SystemExit(
            "fig12 expects equal-cohort variants "
            f"{LS_MODEL_ORDER}, found {present}"
        )
    if set(fx.n.unique().tolist()) != {1149}:
        raise SystemExit(f"fig12 expects n=1149, found {sorted(fx.n.unique())}")
    pcs = ALL_PCS
    colours = ["WHITE", "YELLOW", "REDTYPE"]

    fig, axes = plt.subplots(1, 3, figsize=(12.0, 7.9), sharex=True,
                             sharey=True, constrained_layout=True)
    offs = np.linspace(0.22, -0.22, len(LS_MODEL_ORDER))

    for ax, colour in zip(axes, colours):
        for i, pc in enumerate(pcs):
            if i % 2 == 0:
                ax.axhspan(i - 0.5, i + 0.5, color="#f4f5f5", zorder=0)
            for k, m in enumerate(LS_MODEL_ORDER):
                r = fx[(fx.variant == m) & (fx.color == colour) &
                       (fx.variable == pc)]
                if r.empty:
                    continue
                r = r.iloc[0]
                y = i + offs[k]
                sig = bool(r.significant)
                col = MODEL_COLOR[m]
                ax.plot([r.lower95, r.upper95], [y, y], color=col,
                        lw=1.8, alpha=1.0 if sig else 0.40,
                        solid_capstyle="round", zorder=2)
                ax.scatter([r.post_mean], [y], s=34, zorder=3,
                           color=col if sig else "white",
                           edgecolor=col, linewidth=1.3,
                           alpha=1.0 if sig else 0.75)

        ax.axvline(0, color="#4a4a4a", lw=0.9, ls=(0, (4, 3)), zorder=1)
        ax.set_title(colour, loc="left")
        ax.set_yticks(range(len(pcs)))
        ax.set_yticklabels(pcs)
        ax.set_ylim(len(pcs) - 0.5, -0.5)
        # data-driven so the wide PC6-PC10 intervals are never clipped
        pcrows = fx[fx.variable.isin(pcs)]
        span = max(abs(pcrows.lower95.min()), abs(pcrows.upper95.max())) * 1.06
        ax.set_xlim(-span, span)
        ax.set_xlabel("posterior mean (95% credible interval)")
        ax.xaxis.grid(True, color=GRID, lw=0.6)
        ax.set_axisbelow(True)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)

    handles = [Line2D([], [], marker="o", ls="-", color=MODEL_COLOR[m],
                      ms=6, lw=1.8, label=MODEL_LABELS[m])
               for m in LS_MODEL_ORDER]
    handles += [Line2D([], [], marker="o", ls="none", mfc="white",
                       mec="#4a4a4a", mew=1.3, ms=6,
                       label="credible interval spans 0")]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False,
               bbox_to_anchor=(0.5, -0.075))

    fig.suptitle("Ecological associations across LLM label sources (n=1,149)",
                 fontsize=12, fontweight="bold", x=0.005, ha="left")
    save(fig, "fig12_label_sources")


# --------------------------------------------------------------------------
# Figure 13 - concordance of coefficients across equal-cohort LLM labels
# --------------------------------------------------------------------------

def fig7_concordance():
    fx = pd.read_csv(EXP / "label_sensitivity" / "results" /
                     "label_sensitivity_effects.csv")
    present = sorted(fx.variant.unique().tolist())
    if present != sorted(LS_MODEL_ORDER):
        raise SystemExit(
            "fig13 expects equal-cohort variants "
            f"{LS_MODEL_ORDER}, found {present}"
        )
    if set(fx.n.unique().tolist()) != {1149}:
        raise SystemExit(f"fig13 expects n=1149, found {sorted(fx.n.unique())}")
    pcs = ALL_PCS
    colours = ["WHITE", "YELLOW", "REDTYPE"]
    marker = {"WHITE": "o", "YELLOW": "s", "REDTYPE": "^"}

    ref_name = LS_MODEL_ORDER[0]
    ref = fx[fx.variant == ref_name].set_index(["color", "variable"])
    others = LS_MODEL_ORDER[1:]

    fig, ax = plt.subplots(figsize=(6.8, 6.4), constrained_layout=True)

    # data-driven so no point falls outside the square
    lim = float(fx[fx.variable.isin(pcs)].post_mean.abs().max()) * 1.12
    band = 0.02
    ax.fill_between([-lim, lim], [-lim - band, lim - band],
                    [-lim + band, lim + band], color="#eef1f1", zorder=0,
                    label="_nolegend_")
    ax.plot([-lim, lim], [-lim, lim], color="#8a8a8a", lw=1.0,
            ls=(0, (5, 4)), zorder=1)
    ax.axhline(0, color="#cfcfcf", lw=0.8, zorder=0)
    ax.axvline(0, color="#cfcfcf", lw=0.8, zorder=0)

    stats, sig_x, sig_y = [], [], []
    for m in others:
        sub = fx[fx.variant == m].set_index(["color", "variable"])
        xs, ys = [], []
        for colour in colours:
            for pc in pcs:
                if (colour, pc) not in ref.index or (colour, pc) not in sub.index:
                    continue
                rr, ss = ref.loc[(colour, pc)], sub.loc[(colour, pc)]
                x, y = float(rr["post_mean"]), float(ss["post_mean"])
                xs.append(x)
                ys.append(y)
                both_sig = bool(rr["significant"]) and bool(ss["significant"])
                if both_sig:
                    sig_x.append(x)
                    sig_y.append(y)
                ax.scatter(x, y, s=52 if both_sig else 34, marker=marker[colour],
                           color=MODEL_COLOR[m] if both_sig else "white",
                           edgecolor=MODEL_COLOR[m],
                           linewidth=1.0, alpha=0.95 if both_sig else 0.75,
                           zorder=4 if both_sig else 3)
        stats.append((m, float(np.corrcoef(xs, ys)[0, 1]),
                      float(np.max(np.abs(np.array(ys) - np.array(xs))))))

    n_sig = len(sig_x)
    max_sig_dev = (float(np.max(np.abs(np.array(sig_y) - np.array(sig_x))))
                   if n_sig else float("nan"))

    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_aspect("equal")
    ax.set_xlabel(f"fixed effect under {MODEL_LABELS[ref_name]} labels")
    ax.set_ylabel("fixed effect under other LLM labels")
    ax.grid(True, color="#efefef", lw=0.5)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(True)
        ax.spines[side].set_color(GRID)

    txt = (f"equal cohort n=1,149; {len(colours) * len(pcs)} effects per model\n"
           + "\n".join(f"   {MODEL_LABELS[m]}:  r = {r:.2f},  max |\u0394| = {d:.3f}"
                       for m, r, d in stats)
           + (f"\nsignificant under both ({n_sig} points): max |\u0394| = "
              f"{max_sig_dev:.3f}" if n_sig else
              "\nsignificant under both: none"))
    ax.text(0.030, 0.970, txt, transform=ax.transAxes, va="top", ha="left",
            fontsize=7.4, color=INK, linespacing=1.5,
            bbox=dict(boxstyle="round,pad=0.45", facecolor="white",
                      edgecolor=GRID, linewidth=0.7))

    # Annotate the two robust PC2 associations near the Qwen-7B reference means.
    w = float(ref.loc[("WHITE", "PC2"), "post_mean"])
    y = float(ref.loc[("YELLOW", "PC2"), "post_mean"])
    ax.annotate("WHITE x PC2", xy=(w, w), xytext=(w + 0.02, w - 0.04),
                fontsize=7.5, color=MUTED, ha="left",
                arrowprops=dict(arrowstyle="-", color="#b0b0b0", lw=0.7))
    ax.annotate("YELLOW x PC2", xy=(y, y), xytext=(y - 0.06, y - 0.04),
                fontsize=7.5, color=MUTED, ha="left",
                arrowprops=dict(arrowstyle="-", color="#b0b0b0", lw=0.7))

    handles = [Line2D([], [], marker=marker[c], ls="none", color="#4a4a4a",
                      ms=6, label=c) for c in colours]
    handles += [Line2D([], [], marker="o", ls="none", color=MODEL_COLOR[m],
                       ms=6, label=MODEL_LABELS[m]) for m in others]
    handles += [
        Line2D([], [], marker="o", ls="none", mfc="#4a4a4a", mec="#4a4a4a",
               ms=6, label="significant under both"),
        Line2D([], [], marker="o", ls="none", mfc="white", mec="#4a4a4a",
               ms=6, label="not significant"),
    ]
    ax.legend(handles=handles, loc="lower right", frameon=False, ncol=2,
              fontsize=7.3, handletextpad=0.4, columnspacing=0.9,
              labelspacing=0.35)

    fig.suptitle("Coefficient concordance across LLM label sources",
                 fontsize=12, fontweight="bold", x=0.005, ha="left")
    save(fig, "fig13_label_concordance")


# --------------------------------------------------------------------------

def main():
    print(f"Writing figures to {OUT}")
    gold, data = model_predictions()
    fig1_benchmark(gold, data)
    fig2_confusion(data)
    fig3_flow(data)
    fig4_taxonomy()
    fig5_interventions()
    fig6_forest()
    fig7_concordance()
    print("Done.")


if __name__ == "__main__":
    main()
