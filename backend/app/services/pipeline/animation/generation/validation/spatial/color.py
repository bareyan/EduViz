"""
Color and contrast utilities for spatial validation.
"""

import logging
from typing import Any, Optional, Sequence, Tuple

LOGGER = logging.getLogger(__name__)


def _color_to_rgb(color: Any) -> Optional[Tuple[float, float, float]]:
    """Normalize color inputs for consistent contrast evaluation."""
    if color is None:
        return None
    if isinstance(color, (tuple, list)) and len(color) >= 3:
        return (float(color[0]), float(color[1]), float(color[2]))
    if hasattr(color, "get_rgb"):
        return tuple(color.get_rgb())
    if hasattr(color, "to_rgb"):
        return tuple(color.to_rgb())
    if hasattr(color, "rgb"):
        return tuple(color.rgb)
    return None


def _relative_luminance(rgb: Sequence[float]) -> float:
    """Compute relative luminance for WCAG contrast comparisons."""
    def channel(c: float) -> float:
        c = max(0.0, min(1.0, c))
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def get_contrast_ratio(
    fg_rgb: Optional[Sequence[float]],
    bg_rgb: Optional[Sequence[float]],
) -> Optional[float]:
    """Compute contrast ratio to flag unreadable text."""
    if fg_rgb is None or bg_rgb is None:
        return None
    l1 = _relative_luminance(fg_rgb)
    l2 = _relative_luminance(bg_rgb)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def get_text_color(mobj: Any) -> Optional[Any]:
    """Extract text color so contrast checks can run."""
    if hasattr(mobj, "get_color"):
        try:
            return mobj.get_color()
        except Exception as exc:
            LOGGER.debug("Failed get_color on %s: %s", type(mobj).__name__, exc)
    if hasattr(mobj, "get_fill_color"):
        try:
            return mobj.get_fill_color()
        except Exception as exc:
            LOGGER.debug("Failed get_fill_color on %s: %s", type(mobj).__name__, exc)
    return None
