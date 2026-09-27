#!/usr/bin/env python3
"""Exact Flora of India volume-number matching (ISS-09).

Replaces substring checks like ``"Vol. 1" in title`` which falsely match
Vol. 10–13 / Vol. 20–23.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional, Set

_VOL_NUM = re.compile(
    r"(?i)\bvol(?:ume)?\.?\s*([0-9]+)\b"
)


def parse_volume_number(title: str) -> Optional[int]:
    """Return the first volume number in a title, or None."""
    if not title:
        return None
    m = _VOL_NUM.search(title)
    if not m:
        return None
    return int(m.group(1))


def title_matches_target_volumes(title: str, target_numbers: Iterable[int]) -> bool:
    """True iff the title's volume number is in the target set."""
    n = parse_volume_number(title)
    if n is None:
        return False
    return n in set(int(x) for x in target_numbers)


# Canonical targets used by the Flora of India scrape
TARGET_VOLUME_NUMBERS: Set[int] = {1, 2, 3, 4, 5, 12, 13, 23}
