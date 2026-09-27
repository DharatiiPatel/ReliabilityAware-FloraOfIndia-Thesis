#!/usr/bin/env python3
"""Reliability figures. Forest is skipped until reliability_mcmc_effects.csv exists."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/mplconfig")
Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)

import matplotlib as mpl  # noqa: E402

mpl.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

import sys  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "lib"))
from figure_style import INK, MUTED, apply as apply_style  # noqa: E402

apply_style()

ROOT = (
    Path(os.environ["THESIS_ROOT"]).expanduser().resolve()
    if os.environ.get("THESIS_ROOT")
    else Path(__file__).resolve().parents[1]
)
REL = ROOT / "Processed Data" / "experiments" / "reliability"
FIG = ROOT / "Results" / "figures" / "reliability"
TAB = ROOT / "Results" / "tables" / "reliability"
FIG.mkdir(parents=True, exist_ok=True)
TAB.mkdir(parents=True, exist_ok=True)

def _save(fig, stem: str, dpi: int = 400) -> None:
    fig.savefig(FIG / f"{stem}.png", dpi=dpi, bbox_inches="tight")
    fig.savefig(FIG / f"{stem}.pdf", bbox_inches="tight")
    plt.close(fig)

def fig_pipeline() -> None:
    """Main reliability path vs parallel lexical validator diagnostic."""
    fig, ax = plt.subplots(figsize=(11.2, 3.6))
    ax.set_xlim(0, 11)
    ax.set_ylim(0.2, 3.4)
    ax.axis("off")

    main = [
        (0.2, 1.85, 1.7, 1.0, "Three LLM\noutputs"),
        (2.15, 1.85, 1.7, 1.0, "V2\ncategorisation"),
        (4.1, 1.85, 2.0, 1.0, "Common-known\nthree-LLM cohort"),
        (6.35, 1.85, 1.7, 1.0, "Exact\nagreement"),
        (8.3, 1.85, 1.8, 1.0, "High-confidence\ncohort"),
        (10.25, 1.85, 0.55, 1.0, "Ecology\nmodels"),
    ]
    for x, y, w, h, t in main:
        ax.add_patch(FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.03,rounding_size=0.08",
            facecolor="#eef4f5", edgecolor="#1f6f78", linewidth=1.2,
        ))
        ax.text(x + w / 2, y + h / 2, t, ha="center", va="center",
                fontsize=7.8, color=INK)
    for i in range(len(main) - 1):
        x0 = main[i][0] + main[i][2]
        x1 = main[i + 1][0]
        ax.annotate("", xy=(x1 - 0.02, 2.35), xytext=(x0 + 0.02, 2.35),
                    arrowprops=dict(arrowstyle="->", color="#1f6f78", lw=1.3))

    # Parallel diagnostic branch (not an upstream filter for high confidence)
    ax.add_patch(FancyBboxPatch(
        (2.15, 0.35), 3.6, 0.95, boxstyle="round,pad=0.03,rounding_size=0.08",
        facecolor="#f7f3ee", edgecolor="#8a6a4a", linewidth=1.1, linestyle="--",
    ))
    ax.text(3.95, 0.82,
            "Source-text validator\n(lexical diagnostic / audit only;\n"
            "does not define high confidence)",
            ha="center", va="center", fontsize=7.4, color=INK)
    # connector from V2 / predictions down to validator
    ax.annotate("", xy=(3.0, 1.30), xytext=(3.0, 1.85),
                arrowprops=dict(arrowstyle="->", color="#8a6a4a", lw=1.1,
                                linestyle="--"))
    ax.set_title("Reliability protocol", fontsize=12,
                 color=INK, loc="left", pad=6)
    fig.tight_layout()
    _save(fig, "fig15_reliability_pipeline")

def fig_agreement(summary: dict, rows: list[dict]) -> None:
    n = summary["primary_ecology_n"]
    vals = [
        ("Ecology species", n),
        ("Three-LLM coverage", summary["three_llm_coverage_n"]),
        ("Known colour, all 3 LLMs", summary["common_known_support_n"]),
        ("High confidence", summary["high_confidence_n"]),
        ("Disagreement", summary["disagreement_n"]),
    ]
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    y = range(len(vals))[::-1]
    ax.barh(list(y), [v[1] for v in vals], color="#1f6f78", height=0.62)
    ax.set_yticks(list(y))
    ax.set_yticklabels([v[0] for v in vals], fontsize=9)
    ax.set_xlabel("Number of species")
    for yi, (_, v) in zip(y, vals):
        ax.text(v + max(8, n * 0.01), yi, str(v), va="center", fontsize=8, color=INK)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_title("Three-LLM overlap and confidence", fontsize=12, loc="left")
    fig.tight_layout()
    _save(fig, "fig16_agreement_counts")

    # compact table
    tab_path = TAB / "agreement_validation_table.csv"
    with tab_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["quantity", "n", "note"])
        w.writerow(["primary_ecology", n, "published 7B ecology set"])
        w.writerow(["three_llm_coverage", summary["three_llm_coverage_n"],
                    "72B and Llama exist (not fascicle-only increment)"])
        w.writerow(["common_known_support", summary["common_known_support_n"],
                    "all three LLMs give WHITE/YELLOW/REDTYPE; 7B label used"])
        w.writerow(["high_confidence", summary["high_confidence_n"],
                    "7B, 72B, Llama identical known class"])
        w.writerow(["disagreement", summary["disagreement_n"],
                    "descriptive only; not a third ecology model"])
        w.writerow(["unsupported_known_colour",
                    summary.get("unsupported_known_colour_n", 0),
                    "7B known class, no floral-window colour evidence"])
        w.writerow(["wrong_context_evidence", summary.get("wrong_context_n", 0),
                    "colour near fruit/leaf/indument, not floral term"])
        w.writerow(["agreement_rate_on_coverage_known",
                    summary.get("agreement_rate_on_coverage_known", ""),
                    "among coverage rows where 7B is known"])


def fig_forest(effects_path: Path) -> None:
    with effects_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    # order
    want = [
        ("WHITE", "PC2"), ("YELLOW", "PC2"), ("REDTYPE", "PC3"),
        ("WHITE", "alt_scaled"), ("YELLOW", "alt_scaled"), ("REDTYPE", "alt_scaled"),
    ]
    labels = []
    fig, ax = plt.subplots(figsize=(7.4, 5.2))
    y = 0
    yticks = []
    yticklabels = []
    for color, effect in want:
        for subset, col, marker in (
            ("common_known", "#2e4a7d", "o"),
            ("high_confidence", "#1f6f78", "s"),
        ):
            hit = [r for r in rows if r["color"] == color and r["effect"] == effect
                   and r["subset"] == subset]
            if not hit:
                continue
            r = hit[0]
            mean, lo, hi = float(r["mean"]), float(r["lower"]), float(r["upper"])
            ax.plot([lo, hi], [y, y], color=col, lw=1.6)
            ax.scatter([mean], [y], color=col, marker=marker, s=28, zorder=3)
            yticks.append(y)
            lab = (
                f"{color} ~ {effect.replace('alt_scaled', 'elevation')}  "
                f"({subset.replace('_', ' ')}, n={r['n']})"
            )
            yticklabels.append(lab)
            y -= 1
        y -= 0.35
    ax.axvline(0, color="#bbbbbb", lw=1)
    ax.set_yticks(yticks)
    ax.set_yticklabels(yticklabels, fontsize=7.5)
    ax.set_xlabel("Posterior mean (95% CI)")
    ax.set_title("Common support versus high-confidence labels", loc="left", fontsize=12)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    _save(fig, "fig17_reliability_forest")


def fig_traces(draws_path: Path, convergence_path: Path) -> None:
    """Appendix convergence panel: focal effect traces for all 3 chains, 12 models.

    Mirrors what the primary analysis already publishes (fig4_convergence,
    figS_traceplots) so the reliability chapter's convergence is visible, not just
    tabulated.
    """
    with draws_path.open(encoding="utf-8-sig") as f:
        draws = list(csv.DictReader(f))
    with convergence_path.open(encoding="utf-8-sig") as f:
        cvg = {(r["subset"], r["color"], r["effect"]): r for r in csv.DictReader(f)}

    order = [("WHITE", "PC2"), ("YELLOW", "PC2"), ("REDTYPE", "PC3"),
             ("WHITE", "alt_scaled"), ("YELLOW", "alt_scaled"), ("REDTYPE", "alt_scaled")]
    subsets = [("common_known", "#2e4a7d"), ("high_confidence", "#1f6f78")]
    # one shade per chain, keyed off the subset's base colour
    chain_styles = ["-", "-", "-"]
    chain_alpha = [0.9, 0.6, 0.38]

    fig, axes = plt.subplots(len(order), len(subsets), figsize=(11.0, 12.4),
                             sharex=True)
    for row, (colour, effect) in enumerate(order):
        for col, (subset, base) in enumerate(subsets):
            ax = axes[row][col]
            sel = [d for d in draws if d["subset"] == subset
                   and d["color"] == colour and d["effect"] == effect]
            for ci in ("1", "2", "3"):
                pts = [(int(d["iter"]), float(d["value"])) for d in sel if d["chain"] == ci]
                pts.sort()
                ax.plot([p[0] for p in pts], [p[1] for p in pts],
                        chain_styles[int(ci) - 1], color=base,
                        alpha=chain_alpha[int(ci) - 1], lw=0.5)
            ax.axhline(0, color="#cc4444", lw=0.8, ls="--", alpha=0.7)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.tick_params(labelsize=7)

            r = cvg.get((subset, colour, effect))
            if r:
                ax.set_title(
                    f"{colour} ~ {effect.replace('alt_scaled', 'elevation')}"
                    f"   ({subset.replace('_', ' ')}, n={r['n']})",
                    fontsize=8.5, loc="left", color=INK, pad=3)
                ax.text(0.985, 0.04,
                        f"MPSRF {float(r['mpsrf']):.5f}   ESS {float(r['eff_samp']):,.0f}",
                        transform=ax.transAxes, ha="right", va="bottom",
                        fontsize=6.8, color=MUTED)
            if col == 0:
                ax.set_ylabel("posterior draw", fontsize=7.5)
    for ax in axes[-1]:
        ax.set_xlabel("stored iteration (thinned for display)", fontsize=8)

    fig.suptitle("MCMC convergence, reliability models",
                 fontsize=12, x=0.008, ha="left", y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.985))
    _save(fig, "fig18_reliability_convergence", dpi=200)


def main() -> None:
    summary = json.loads((REL / "summary.json").read_text())
    with (REL / "species_reliability.csv").open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    fig_pipeline()
    fig_agreement(summary, rows)
    effects = REL / "reliability_mcmc_effects.csv"
    if effects.exists():
        fig_forest(effects)
        print("wrote forest from", effects)
    else:
        print("SKIP forest: run Rscript scripts/25_Reliability_Ecology.R")

    draws = REL / "reliability_chain_draws.csv"
    convergence = REL / "reliability_convergence.csv"
    if draws.exists() and convergence.exists():
        fig_traces(draws, convergence)
        print("wrote convergence panel from", draws.name)
    else:
        print("SKIP convergence panel: run Rscript scripts/28_Export_Reliability_Draws.R")
    print("figures ->", FIG)


if __name__ == "__main__":
    main()
