"""
Geometric utilities for calculating overlaps and boundary violations.
"""

import logging
from typing import Any, Optional, Sequence, Tuple
import numpy as np

from .constants import SAFETY_MARGIN

LOGGER = logging.getLogger(__name__)


def get_loc_desc(center: Optional[Sequence[float]]) -> str:
    """Summarize location for human-readable diagnostics."""
    if center is None:
        return "Unknown"
    v_loc = "Center"
    if center[1] > 1.5:
        v_loc = "Top"
    elif center[1] < -1.5:
        v_loc = "Bottom"

    h_loc = ""
    if center[0] > 2:
        h_loc = "Right"
    elif center[0] < -2:
        h_loc = "Left"

    desc = f"{v_loc} {h_loc}".strip()
    return desc if desc else "Center"


def get_overlap_metrics(m1: Any, m2: Any) -> Tuple[float, Optional[np.ndarray], str]:
    """Compute overlap area to quantify potential collisions."""
    try:
        w1, h1 = m1.width, m1.height
        w2, h2 = m2.width, m2.height
        c1, c2 = m1.get_center(), m2.get_center()

        # Edges
        l1, r1 = c1[0] - w1 / 2, c1[0] + w1 / 2
        b1, t1 = c1[1] - h1 / 2, c1[1] + h1 / 2
        l2, r2 = c2[0] - w2 / 2, c2[0] + w2 / 2
        b2, t2 = c2[1] - h2 / 2, c2[1] + h2 / 2

        # Intersection
        inter_l = max(l1, l2)
        inter_r = min(r1, r2)
        inter_b = max(b1, b2)
        inter_t = min(t1, t2)

        inter_w = inter_r - inter_l
        inter_h = inter_t - inter_b

        if inter_w <= 0 or inter_h <= 0:
            return 0.0, np.array([0, 0, 0]), "None"

        area = inter_w * inter_h
        center = np.array([inter_l + inter_w / 2, inter_b + inter_h / 2, 0])

        return area, center, get_loc_desc(center)
    except Exception as exc:
        LOGGER.debug("Failed overlap metrics: %s", exc)
        return 0.0, None, "Error"


def get_boundary_violation(mobj: Any, manim_config: Any) -> Optional[Tuple[float, str]]:
    """Identify boundary violations to avoid clipping."""
    try:
        w, h = mobj.width, mobj.height
        if w == 0 or h == 0:
            return None

        c = mobj.get_center()
        half_w = manim_config.frame_width / 2
        half_h = manim_config.frame_height / 2

        # Object edges
        left = c[0] - w / 2
        right = c[0] + w / 2
        top = c[1] + h / 2
        bottom = c[1] - h / 2

        safe_x = half_w - SAFETY_MARGIN
        safe_y = half_h - SAFETY_MARGIN

        violations = []
        max_dist = 0.0

        if right > safe_x:
            diff = right - safe_x
            violations.append(f"Right (+{diff:.2f})")
            max_dist = max(max_dist, diff)
        if left < -safe_x:
            diff = (-safe_x) - left
            violations.append(f"Left (+{diff:.2f})")
            max_dist = max(max_dist, diff)
        if top > safe_y:
            diff = top - safe_y
            violations.append(f"Top (+{diff:.2f})")
            max_dist = max(max_dist, diff)
        if bottom < -safe_y:
            diff = (-safe_y) - bottom
            violations.append(f"Bottom (+{diff:.2f})")
            max_dist = max(max_dist, diff)

        if violations:
            return max_dist, ", ".join(violations)
        return None
    except Exception as exc:
        LOGGER.debug("Failed boundary check: %s", exc)
        return None


def get_z_index(mobj: Any) -> float:
    """Normalize z-index access to keep occlusion checks stable."""
    try:
        return float(getattr(mobj, "z_index", 0.0))
    except Exception as exc:
        LOGGER.debug("Failed z-index read: %s", exc)
        return 0.0
