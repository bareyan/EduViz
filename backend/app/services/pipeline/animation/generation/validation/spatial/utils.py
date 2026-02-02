"""
Shared utilities for spatial validation.
"""

import inspect
import logging
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

LOGGER = logging.getLogger(__name__)


def get_user_code_context(linter_path: str) -> Tuple[str, int]:
    """Capture user file context for actionable diagnostics."""
    stack = inspect.stack(context=0)
    linter_path = os.path.normcase(os.path.abspath(linter_path))
    for frame_info in stack:
        filename = os.path.normcase(os.path.abspath(frame_info.filename))
        if filename == linter_path:
            continue
        if "site-packages" in filename or "lib/python" in filename:
            continue
        # Also skip THIS file
        if filename == os.path.normcase(os.path.abspath(__file__)):
            continue
        return frame_info.filename, frame_info.lineno
    return "unknown", 0


def is_visible(mobj: Any, VMobject_class: type, ImageMobject_class: type) -> bool:
    """Skip invisible objects to reduce false positives."""
    if isinstance(mobj, VMobject_class):
        if hasattr(mobj, "get_fill_opacity") and hasattr(mobj, "get_stroke_opacity"):
            if mobj.get_fill_opacity() == 0 and mobj.get_stroke_opacity() == 0:
                return False
        else:
            LOGGER.debug("VMobject missing opacity methods: %s", type(mobj).__name__)
    elif isinstance(mobj, ImageMobject_class):
        if hasattr(mobj, "opacity") and mobj.opacity == 0:
            return False
    return True


def get_atomic_mobjects(mobject: Any, manim_classes: Dict[str, type]) -> List[Any]:
    """Flatten objects to the atomic level to avoid duplicate checks."""
    check_types = (
        manim_classes['Text'],
        manim_classes['MathTex'],
        manim_classes['Tex'],
        manim_classes['Code'],
        manim_classes['ImageMobject']
    )
    ignore_types = (
        manim_classes['NumberPlane'],
        manim_classes['Axes'],
        manim_classes['Arrow'],
        manim_classes['Line'],
        manim_classes['DashedLine'],
        manim_classes['Brace'],
        manim_classes['Vector'],
        manim_classes['ComplexPlane'],
        manim_classes['Circle'],
        manim_classes['Square'],
        manim_classes['Rectangle']
    )

    if isinstance(mobject, ignore_types):
        return []
    if not is_visible(mobject, manim_classes['VMobject'], manim_classes['ImageMobject']):
        return []

    if isinstance(mobject, check_types):
        return [mobject]

    if hasattr(mobject, "submobjects") and mobject.submobjects:
        sub_atoms = []
        for sub in mobject.submobjects:
            sub_atoms.extend(get_atomic_mobjects(sub, manim_classes))
        if not sub_atoms and isinstance(mobject, manim_classes['VMobject']) and mobject.has_points():
            return [mobject]
        return sub_atoms

    if isinstance(mobject, manim_classes['VMobject']) and mobject.has_points():
        return [mobject]
    return []


def is_overlapping(m1: Any, m2: Any, overlap_margin: float) -> bool:
    """Use bounding boxes to catch visible overlaps fast."""
    try:
        w1, h1 = m1.width, m1.height
        w2, h2 = m2.width, m2.height
        if w1 < 0.01 or h1 < 0.01 or w2 < 0.01 or h2 < 0.01:
            return False

        c1, c2 = m1.get_center(), m2.get_center()

        if (abs(c1[0] - c2[0]) * 2 < (w1 + w2 - overlap_margin)) and \
           (abs(c1[1] - c2[1]) * 2 < (h1 + h2 - overlap_margin)):
            return True
        return False
    except Exception as exc:
        LOGGER.debug("Failed overlap check: %s", exc)
        return False
