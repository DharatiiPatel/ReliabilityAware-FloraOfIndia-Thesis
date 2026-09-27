#!/usr/bin/env python3
"""Shared matplotlib style for thesis figures (methods + reliability).

Matches scripts/lib/figure_style.R so R and Python figures use the same
typeface, ink colours, and title treatment.
"""

from __future__ import annotations

import matplotlib as mpl

INK = "#1b1b1b"
MUTED = "#6e6e6e"
GRID = "#e3e3e3"

CLASS_COLOR = {
    "WHITE": "#b9b3a4",
    "YELLOW": "#d8a634",
    "REDTYPE": "#a63f34",
    "RED": "#a63f34",
    "PINK": "#c98da8",
    "PURPLE/BLUE": "#6b7fa8",
    "UNKNOWN": "#7c8ba1",
    "OTHER": "#5f7355",
}


def apply() -> None:
    mpl.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "axes.titlesize": 10,
        "axes.titleweight": "bold",
        "axes.labelsize": 9,
        "axes.edgecolor": "#4a4a4a",
        "axes.linewidth": 0.7,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.color": INK,
        "ytick.color": INK,
        "xtick.major.width": 0.7,
        "ytick.major.width": 0.7,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 8,
        "figure.dpi": 130,
        "savefig.dpi": 400,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "axes.titlelocation": "left",
        "figure.titlesize": 12,
        "figure.titleweight": "bold",
        "text.color": INK,
        "axes.labelcolor": INK,
        "axes.unicode_minus": False,
    })
