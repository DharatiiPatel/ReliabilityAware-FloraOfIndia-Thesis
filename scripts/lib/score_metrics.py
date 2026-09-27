"""Explicit Macro-F1 definitions for gold-set evaluation.

macro_f1_target4
    Unweighted mean F1 across the fixed human target classes
    WHITE, YELLOW, REDTYPE, UNKNOWN.
    A prediction of OTHER against one of these gold labels is an error for
    that true class (F1 for OTHER is not included in the average).

macro_f1_all5
    Unweighted mean F1 across WHITE, YELLOW, REDTYPE, UNKNOWN and OTHER,
    with zero_division=0 (classes with no support contribute F1=0).

Do not dynamically drop classes merely because gold support is zero for
the all-five metric; for target4, OTHER is excluded from the average by
definition because it is not a human target class in this gold set.
"""

from __future__ import annotations

TARGET4 = ["WHITE", "YELLOW", "REDTYPE", "UNKNOWN"]
ALL5 = ["WHITE", "YELLOW", "REDTYPE", "UNKNOWN", "OTHER"]


def _f1(y_true: list[str], y_pred: list[str], c: str) -> float:
    tp = sum(a == c and b == c for a, b in zip(y_true, y_pred))
    fp = sum(a != c and b == c for a, b in zip(y_true, y_pred))
    fn = sum(a == c and b != c for a, b in zip(y_true, y_pred))
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    return 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0


def macro_f1_target4(y_true: list[str], y_pred: list[str]) -> float:
    return sum(_f1(y_true, y_pred, c) for c in TARGET4) / len(TARGET4)


def macro_f1_all5(y_true: list[str], y_pred: list[str]) -> float:
    return sum(_f1(y_true, y_pred, c) for c in ALL5) / len(ALL5)


def per_class_f1(y_true: list[str], y_pred: list[str], classes=None) -> dict:
    classes = classes or ALL5
    out = {}
    for c in classes:
        support = sum(a == c for a in y_true)
        out[c] = {
            "f1": _f1(y_true, y_pred, c),
            "support": support,
        }
    return out
