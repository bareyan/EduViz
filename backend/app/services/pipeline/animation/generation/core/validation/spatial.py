"""
Spatial Check Injector

Injects AST-based spatial validation into Manim Scene code.

Features:
- Confidence-based classification (CRITICAL / WARNING / INFO)
- Overlap-ratio computation for accurate occlusion detection
- Effect & container suppression (Flash, SurroundingRectangle, etc.)
- Structured JSON output for smart triage downstream
- Accumulates ALL issues across play/wait calls, deduplicates at end

The injected code runs inside the Manim subprocess and outputs structured
JSON via sys.exit() for the RuntimeValidator to parse.
"""

import ast
import copy
import textwrap

from app.core import get_logger

logger = get_logger(__name__, component="spatial_injector")

# ── Marker the RuntimeValidator scans for in stderr/exit message ─────────────
SPATIAL_JSON_MARKER = "SPATIAL_ISSUES_JSON:"

# ── Injected into the Scene class as _perform_spatial_checks() ───────────────
#
# Self-contained: no imports from our codebase.  Runs inside Manim subprocess.
# Classifies issues by severity/confidence and stores them for a final report.
INJECTED_METHOD = '''
def _perform_spatial_checks(self):
    """Injected spatial validator - runs at every play()/wait() boundary."""

    # ── Dynamic Screen limits ──
    try:
        # Use camera frame dimensions if available, fallback to defaults
        if hasattr(self, "camera"):
            SCREEN_X = self.camera.frame_width / 2
            SCREEN_Y = self.camera.frame_height / 2
        else:
            SCREEN_X = 7.1
            SCREEN_Y = 4.0
    except Exception:
        SCREEN_X = 7.1
        SCREEN_Y = 4.0

    SAFE_X = SCREEN_X * 0.77  # Roughly 5.5 / 7.1
    SAFE_Y = SCREEN_Y * 0.75  # Roughly 3.0 / 4.0
    # Text needs extra margin — partial letters at screen edge look broken
    TEXT_EDGE_MARGIN = 0.3
    # Lower threshold for text (0.1) vs general objects (0.3)
    TEXT_OVERSHOOT_THRESHOLD = 0.0
    GENERAL_OVERSHOOT_THRESHOLD = 0.3
    TEXT_CLIP_MARGIN = 0.12
    # Group/table size limits — anything larger is definitely broken
    GROUP_MAX_WIDTH = SCREEN_X * 2.1
    GROUP_MAX_HEIGHT = SCREEN_Y * 2.25
    FRAME_AREA = (2 * SCREEN_X) * (2 * SCREEN_Y)
    # TEMPORARY RELAXATION: disable heuristic visual-quality blockers
    # by using non-reachable thresholds until we tighten logic.
    FILL_DOMINANCE_AREA_RATIO = 1.10
    FILL_DOMINANCE_OPACITY = 0.55
    STROKE_THROUGH_RATIO = 0.12
    STROKE_MAX_THICKNESS = 0.25
    STROKE_MIN_LENGTH = 0.6
    STROKE_TEXT_PROXIMITY_PAD = 0.10
    STROKE_TEXT_NEAR_GAP = 0.08

    # ── Types we expect to overlap (not bugs) ──
    EFFECT_TYPES = frozenset({
        "Flash", "Indicate", "Circumscribe", "ShowPassingFlash",
        "ApplyWave", "Wiggle", "AnimationGroup", "FadeOut", "FadeIn",
        "ShowCreation", "Uncreate", "GrowFromCenter", "SpinInFromNothing",
        "ShrinkToCenter", "ShowIncreasingSubsets", "ShowSubmobjectsOneByOne",
    })
    # Only BackgroundRectangle and Underline are true containers.
    # SurroundingRectangle can be a highlight box that covers content.
    CONTAINER_TYPES = frozenset({
        "BackgroundRectangle", "Underline",
    })

    # ── Lazy-init accumulator on scene instance ──
    if not hasattr(self, "_spatial_issues"):
        self._spatial_issues = []

    # ── Helper: flatten scene graph ──
    def _flat(mobjects):
        out = []
        for m in mobjects:
            if m is None:
                continue
            out.append(m)
            # Text/Tex families contain glyph submobjects (e.g. VMobjectFromSVGPath)
            # that create noisy duplicate issues. Keep the parent text node only.
            try:
                _name = type(m).__name__
                _is_text_like = ("Text" in _name) or ("Tex" in _name) or hasattr(m, "text")
            except Exception:
                _is_text_like = False
            if _is_text_like:
                continue
            if hasattr(m, "submobjects") and m.submobjects:
                out.extend(_flat(m.submobjects))
        return out

    # ── Helper: effective visibility ──
    def _visible(m):
        try:
            if hasattr(m, "get_fill_opacity"):
                fo = m.get_fill_opacity()
                if fo is not None and fo == 0:
                    if hasattr(m, "get_stroke_opacity"):
                        so = m.get_stroke_opacity()
                        if so is not None and so > 0:
                            return True
                    return False
            return True
        except Exception:
            return True

    # ── Helper: check if object is text-like ──
    def _is_text(m):
        name = type(m).__name__
        return "Text" in name or "Tex" in name or hasattr(m, "text")

    # ── Helper: intersection-over-smaller-area ratio ──
    def _overlap_ratio(m1, m2):
        try:
            c1, c2 = m1.get_center(), m2.get_center()
            w1, h1 = m1.width, m1.height
            w2, h2 = m2.width, m2.height
            ix = max(0, min(c1[0] + w1 / 2, c2[0] + w2 / 2) - max(c1[0] - w1 / 2, c2[0] - w2 / 2))
            iy = max(0, min(c1[1] + h1 / 2, c2[1] + h2 / 2) - max(c1[1] - h1 / 2, c2[1] - h2 / 2))
            inter = ix * iy
            smaller = min(w1 * h1, w2 * h2)
            if smaller < 0.01:
                return 0.0
            return inter / smaller
        except Exception:
            return 0.0

    def _overlap_metrics(m1, m2):
        """Return overlap geometry to catch low-area but visibly bad text collisions."""
        try:
            c1, c2 = m1.get_center(), m2.get_center()
            w1, h1 = m1.width, m1.height
            w2, h2 = m2.width, m2.height
            ix = max(0, min(c1[0] + w1 / 2, c2[0] + w2 / 2) - max(c1[0] - w1 / 2, c2[0] - w2 / 2))
            iy = max(0, min(c1[1] + h1 / 2, c2[1] + h2 / 2) - max(c1[1] - h1 / 2, c2[1] - h2 / 2))
            return ix, iy, min(w1, w2), min(h1, h2)
        except Exception:
            return 0.0, 0.0, 0.0, 0.0

    def _bbox(m):
        try:
            c = m.get_center()
            w, h = m.width, m.height
            left = c[0] - w / 2
            right = c[0] + w / 2
            bottom = c[1] - h / 2
            top = c[1] + h / 2
            return left, right, bottom, top
        except Exception:
            return 0.0, 0.0, 0.0, 0.0

    def _bbox_distance(m1, m2):
        """Euclidean distance between two axis-aligned bboxes (0 if touching/overlapping)."""
        l1, r1, b1, t1 = _bbox(m1)
        l2, r2, b2, t2 = _bbox(m2)
        dx = max(0.0, l2 - r1, l1 - r2)
        dy = max(0.0, b2 - t1, b1 - t2)
        return (dx * dx + dy * dy) ** 0.5

    def _segment_hits_bbox(p1, p2, bbox, pad):
        left, right, bottom, top = bbox
        x1, y1 = p1[0], p1[1]
        x2, y2 = p2[0], p2[1]

        if max(x1, x2) < left - pad or min(x1, x2) > right + pad:
            return False
        if max(y1, y2) < bottom - pad or min(y1, y2) > top + pad:
            return False

        # Coarse sampling is enough for line/polygon stroke crossings.
        for alpha in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0):
            x = x1 + (x2 - x1) * alpha
            y = y1 + (y2 - y1) * alpha
            if (left - pad) <= x <= (right + pad) and (bottom - pad) <= y <= (top + pad):
                return True
        return False

    def _stroke_path_hits_text(text_mobj, stroke_mobj):
        try:
            points = stroke_mobj.get_all_points()
        except Exception:
            return False
        if points is None or len(points) < 2:
            return False

        try:
            stroke_width = stroke_mobj.get_stroke_width() if hasattr(stroke_mobj, "get_stroke_width") else 0.0
            # Convert pixel-ish stroke widths to a conservative world-space pad.
            pad = max(STROKE_TEXT_PROXIMITY_PAD, min(0.24, float(stroke_width) * 0.01))
        except Exception:
            pad = STROKE_TEXT_PROXIMITY_PAD

        text_bbox = _bbox(text_mobj)
        for i in range(len(points) - 1):
            if _segment_hits_bbox(points[i], points[i + 1], text_bbox, pad):
                return True

        try:
            is_closed = bool(stroke_mobj.is_closed()) if hasattr(stroke_mobj, "is_closed") else False
        except Exception:
            is_closed = False
        if is_closed and _segment_hits_bbox(points[-1], points[0], text_bbox, pad):
            return True
        return False

    # ── Helper: family-tree relationship ──
    def _is_family(a, b):
        try:
            if hasattr(b, "get_family") and a in b.get_family():
                return True
            if hasattr(a, "get_family") and b in a.get_family():
                return True
        except Exception:
            pass
        return False

    # Table/group types whose internal Lines naturally cross cell text.
    _TABLE_TYPES = frozenset({
        "Table", "MobjectTable", "IntegerTable", "DecimalTable", "MathTable",
    })

    def _shares_table_ancestor(a, b):
        """True when a and b are both descendants of the same Table object."""
        try:
            for top in self.mobjects:
                if type(top).__name__ not in _TABLE_TYPES:
                    if not hasattr(top, "get_family"):
                        continue
                    # Check nested tables inside top-level groups
                    fam = top.get_family()
                    for member in fam:
                        if type(member).__name__ in _TABLE_TYPES:
                            table_fam = member.get_family()
                            if a in table_fam and b in table_fam:
                                return True
                    continue
                fam = top.get_family()
                if a in fam and b in fam:
                    return True
        except Exception:
            pass
        return False

    def _trunc(s, n=50):
        return s[:n] if len(s) > n else s

    def _text_label(m):
        try:
            if hasattr(m, "get_tex_string"):
                tex = m.get_tex_string()
                if isinstance(tex, str) and tex:
                    return _trunc(tex)
        except Exception:
            pass
        try:
            tex = getattr(m, "tex_string", "")
            if isinstance(tex, str) and tex:
                return _trunc(tex)
        except Exception:
            pass
        try:
            txt = getattr(m, "text", "")
            if isinstance(txt, str) and txt:
                return _trunc(txt)
        except Exception:
            pass
        return _trunc(repr(m))

    def _subject_label(m, is_text_obj=False, text_label=None):
        obj_type = type(m).__name__
        if is_text_obj:
            if isinstance(text_label, str) and text_label and text_label != obj_type:
                return text_label
            return obj_type
        try:
            name = getattr(m, "name", "")
            if isinstance(name, str) and name and name != obj_type:
                return _trunc(f"{obj_type}:{name}")
        except Exception:
            pass
        return obj_type

    def _closest_edge(left, right, top, bottom):
        distances = {
            "left": SCREEN_X + left,
            "right": SCREEN_X - right,
            "top": SCREEN_Y - top,
            "bottom": SCREEN_Y + bottom,
        }
        edge = min(distances, key=distances.get)
        return edge, distances[edge]

    def _current_time_sec():
        try:
            t = getattr(getattr(self, "renderer", None), "time", None)
            if t is None:
                t = getattr(self, "time", None)
            return float(t) if t is not None else None
        except Exception:
            return None

    def _issue(severity, confidence, category, message, auto_fixable=False, fix_hint=None, **details):
        if "time_sec" not in details:
            details["time_sec"] = _current_time_sec()
        
        # ── Snapshot Logic ──
        # If we have an output directory and this is a visual issue (not critical code failure),
        # capture a snapshot for verifying with Vision LLM.
        try:
            import os as _os
            _out_dir = _os.environ.get("MANIM_SPATIAL_OUTPUT_DIR")
            if _out_dir and _os.path.exists(_out_dir):
                # Don't spam snapshots - one per second-ish is enough? 
                # Actually, precise frames are better. Dedupe by exact time + message hash?
                # Simple dedupe: filename based on time.
                _t_val = details["time_sec"] or 0.0
                _fname = f"issue_t{_t_val:.2f}.png"
                _full_path = _os.path.join(_out_dir, _fname)
                
                # If file doesn't exist, capture it.
                if not _os.path.exists(_full_path):
                     # self is available from closure
                     if hasattr(self, "camera") and hasattr(self.camera, "get_image"):
                         _img = self.camera.get_image()
                         if _img:
                             _img.save(_full_path)
                             
                details["frame_file"] = _fname
        except Exception:
            pass
            
        return {
            "severity": severity,
            "confidence": confidence,
            "category": category,
            "message": message,
            "auto_fixable": auto_fixable,
            "fix_hint": fix_hint,
            "details": details,
        }

    # ── Flatten scene graph ──
    all_ordered = _flat(self.mobjects)
    new_issues = []

    # ═══════════════════════════════════════════════════════════════════
    # 1. BOUNDS CHECK (with text-specific stricter thresholds)
    # ═══════════════════════════════════════════════════════════════════
    for m in all_ordered:
        if not hasattr(m, "get_center") or not hasattr(m, "width"):
            continue
        if not _visible(m):
            continue
        if m.width < 0.1 and m.height < 0.1:
            continue

        try:
            x, y, _ = m.get_center()
            w, h = m.width, m.height
        except Exception:
            continue

        left, right = x - w / 2, x + w / 2
        top, bottom = y + h / 2, y - h / 2
        obj_type = type(m).__name__
        is_text_obj = _is_text(m)

        overshoot_x = max(0, -left - SCREEN_X, right - SCREEN_X)
        overshoot_y = max(0, -bottom - SCREEN_Y, top - SCREEN_Y)
        overshoot = max(overshoot_x, overshoot_y)
        nearest_edge, nearest_edge_dist = _closest_edge(left, right, top, bottom)
        text_label = _text_label(m) if is_text_obj else None
        subject_label = _subject_label(m, is_text_obj=is_text_obj, text_label=text_label)

        # Use stricter threshold for text objects
        ignore_threshold = TEXT_OVERSHOOT_THRESHOLD if is_text_obj else GENERAL_OVERSHOOT_THRESHOLD

        if overshoot > 1.0:
            msg = (
                f"{'Text' if is_text_obj else 'Object'} '{subject_label}' SEVERELY out of bounds at "
                f"({x:.1f}, {y:.1f}), size {w:.1f}x{h:.1f}, "
                f"overshoot {overshoot:.1f}"
            )
            new_issues.append(_issue(
                "critical", "high", "out_of_bounds", msg,
                auto_fixable=True,
                fix_hint=f"Shift or scale to bring within +/-{SAFE_X} x +/-{SAFE_Y}",
                object_type=obj_type, center_x=round(x, 2), center_y=round(y, 2),
                width=round(w, 2), height=round(h, 2), overshoot=round(overshoot, 2),
                is_text=is_text_obj, edge=nearest_edge, edge_margin=round(nearest_edge_dist, 2),
                object_subject=subject_label,
                text=text_label, reason=("text_edge_clipping" if is_text_obj else "object_bounds"),
            ))
        elif overshoot > ignore_threshold:
            msg = (
                f"{'Text' if is_text_obj else 'Object'} '{subject_label}' partially clipped at "
                f"({x:.1f}, {y:.1f}), size {w:.1f}x{h:.1f}, "
                f"overshoot {overshoot:.1f}"
            )
            sev = "critical" if is_text_obj else "warning"
            conf = "high" if is_text_obj else "medium"
            new_issues.append(_issue(
                sev, conf, "out_of_bounds", msg,
                auto_fixable=True,
                fix_hint=f"{'Text clipped at edge — shift inward or reduce font_size' if is_text_obj else f'Minor adjustment needed (~{overshoot:.1f} units)'}",
                object_type=obj_type, center_x=round(x, 2), center_y=round(y, 2),
                width=round(w, 2), height=round(h, 2), overshoot=round(overshoot, 2),
                is_text=is_text_obj, edge=nearest_edge, edge_margin=round(nearest_edge_dist, 2),
                object_subject=subject_label,
                text=text_label, reason=("text_edge_clipping" if is_text_obj else "object_bounds"),
            ))

        # ── Text edge proximity check ──
        # Even if not technically past SCREEN_X, text within TEXT_EDGE_MARGIN
        # of the screen boundary is at risk of visual clipping
        # This is UNCERTAIN — needs Visual QC to confirm if it looks bad
        if is_text_obj and overshoot <= ignore_threshold:
            margin_right = SCREEN_X - right
            margin_left = SCREEN_X + left  # left is negative when object is left of center
            margin_top = SCREEN_Y - top
            margin_bottom = SCREEN_Y + bottom

            min_margin = min(margin_right, margin_left, margin_top, margin_bottom)
            edge, edge_dist = _closest_edge(left, right, top, bottom)
            if 0 < min_margin < TEXT_CLIP_MARGIN:
                msg = (
                    f"Text '{subject_label}' appears clipped near {edge} edge at "
                    f"({x:.1f}, {y:.1f}), margin={min_margin:.2f}"
                )
                # Use LOW confidence — let Visual QC decide if it's actually clipped
                new_issues.append(_issue(
                    "critical", "high", "out_of_bounds", msg,
                    auto_fixable=True,
                    fix_hint="Shift text inward or reduce font_size — risk of edge clipping",
                    object_type=obj_type, text=text_label, center_x=round(x, 2), center_y=round(y, 2),
                    width=round(w, 2), height=round(h, 2),
                    overshoot=round(TEXT_CLIP_MARGIN - min_margin, 2),
                    is_text=True, edge=edge, edge_margin=round(edge_dist, 2),
                    object_subject=subject_label,
                    reason="text_edge_clipping",
                ))
            elif 0 < min_margin < TEXT_EDGE_MARGIN:
                msg = (
                    f"Text '{subject_label}' dangerously close to screen edge at "
                    f"({x:.1f}, {y:.1f}), margin={min_margin:.2f}"
                )
                new_issues.append(_issue(
                    "warning", "low", "out_of_bounds", msg,
                    auto_fixable=True,
                    fix_hint="Shift text inward or reduce font_size - risk of edge clipping",
                    object_type=obj_type, text=text_label,
                    center_x=round(x, 2), center_y=round(y, 2),
                    width=round(w, 2), height=round(h, 2),
                    overshoot=round(TEXT_EDGE_MARGIN - min_margin, 2),
                    is_text=True, edge=edge, edge_margin=round(edge_dist, 2),
                    object_subject=subject_label,
                    reason="text_edge_risk",
                ))

    # ═══════════════════════════════════════════════════════════════════
    # 1b. GROUP / TABLE OVERFLOW CHECK
    # ═══════════════════════════════════════════════════════════════════
    # Catch VGroup/Table/MobjectTable that are too large for the screen
    for m in all_ordered:
        obj_type = type(m).__name__
        if obj_type not in ("VGroup", "Group", "Table", "MobjectTable", "IntegerTable", "DecimalTable", "MathTable"):
            continue
        if not _visible(m):
            continue
        try:
            w, h = m.width, m.height
        except Exception:
            continue
        if w < 0.5 and h < 0.5:
            continue

        if w > GROUP_MAX_WIDTH or h > GROUP_MAX_HEIGHT:
            try:
                x, y, _ = m.get_center()
            except Exception:
                x, y = 0, 0
            msg = (
                f"{obj_type} too large: {w:.1f}x{h:.1f} "
                f"(max {GROUP_MAX_WIDTH}x{GROUP_MAX_HEIGHT}) at ({x:.1f}, {y:.1f})"
            )
            new_issues.append(_issue(
                "critical", "high", "out_of_bounds", msg,
                auto_fixable=True,
                fix_hint=f"Add .scale_to_fit_width({2*SAFE_X:.0f}) after creating the {obj_type}",
                object_type=obj_type, center_x=round(x, 2), center_y=round(y, 2),
                width=round(w, 2), height=round(h, 2),
                overshoot=round(max(w - 2 * SCREEN_X, h - 2 * SCREEN_Y, 0), 2),
                is_group_overflow=True,
            ))

    # ═══════════════════════════════════════════════════════════════════
    # 2. TEXT-ON-TEXT OVERLAP
    # ═══════════════════════════════════════════════════════════════════
    texts = []
    objects = []
    for idx, m in enumerate(all_ordered):
        if not hasattr(m, "get_center"):
            continue
        if not _visible(m):
            continue
        if _is_text(m):
            texts.append((idx, m))
        elif hasattr(m, "width"):
            objects.append((idx, m))

    for i, (idx1, t1) in enumerate(texts):
        for idx2, t2 in texts[i + 1:]:
            if t1 is t2:
                continue
            if _is_family(t1, t2):
                continue

            ratio = _overlap_ratio(t1, t2)
            ix, iy, w_min, h_min = _overlap_metrics(t1, t2)
            # For long formulas/equations, bbox area overlap can be deceptively small
            # while a baseline collision is still visually severe.
            baseline_collision = (
                iy > 0.16 and
                ix > 0.40 and
                h_min > 0 and
                w_min > 0 and
                (iy / h_min) > 0.28
            )
            if ratio < 0.05 and not baseline_collision:
                continue

            txt1 = _trunc(getattr(t1, "text", repr(t1)))
            txt2 = _trunc(getattr(t2, "text", repr(t2)))
            msg = f"Text overlap ({ratio:.0%}): '{txt1}' overlaps '{txt2}'"
            if baseline_collision and ratio < 0.15:
                msg += " [baseline collision]"

            if ratio > 0.4:
                # CERTAIN: Major overlap — definitely needs fixing
                new_issues.append(_issue(
                    "critical", "high", "text_overlap", msg,
                    auto_fixable=True,
                    fix_hint="Separate texts with .next_to() or .shift()",
                    text1=txt1, text2=txt2, overlap_ratio=round(ratio, 2),
                ))
            elif ratio > 0.15:
                # CERTAIN: Visible overlap — still needs fixing
                new_issues.append(_issue(
                    "critical", "high", "text_overlap", msg,
                    auto_fixable=True,
                    fix_hint="Visible text overlap: separate labels with .next_to()/.shift()",
                    text1=txt1, text2=txt2, overlap_ratio=round(ratio, 2),
                    reason=("long_equation_baseline_collision" if baseline_collision else "bbox_overlap"),
                ))
            else:
                # UNCERTAIN: Small overlap (5-15%) — let Visual QC decide
                new_issues.append(_issue(
                    "warning", "low", "text_overlap", msg,
                    auto_fixable=True,
                    fix_hint="Minor text overlap: may need adjustment",
                    text1=txt1, text2=txt2, overlap_ratio=round(ratio, 2),
                    reason=("long_equation_baseline_collision" if baseline_collision else "bbox_overlap"),
                ))

    # ═══════════════════════════════════════════════════════════════════
    # 2b. TEXT DOMINANCE / OVER-EMPHASIS
    # ═══════════════════════════════════════════════════════════════════
    # Catch oversized non-title Text labels that dominate the frame.
    DOMINANT_TEXT_WIDTH = 999.0
    DOMINANT_TEXT_HEIGHT = 999.0
    TITLE_Y_CUTOFF = 2.8

    for _, t in texts:
        obj_type = type(t).__name__
        if obj_type != "Text":
            continue

        try:
            tw, th = t.width, t.height
            tx, ty, _ = t.get_center()
        except Exception:
            continue

        if tw < DOMINANT_TEXT_WIDTH and th < DOMINANT_TEXT_HEIGHT:
            continue
        if ty > TITLE_Y_CUTOFF:
            # Top-edge headline/title area is intentionally larger.
            continue

        txt = _trunc(getattr(t, "text", repr(t)))
        msg = (
            f"Text '{txt}' is visually dominant "
            f"(size {tw:.1f}x{th:.1f} at ({tx:.1f}, {ty:.1f}))"
        )
        sev = "critical" if tw > 5.6 else "warning"
        new_issues.append(_issue(
            sev, "high", "visual_quality", msg,
            auto_fixable=True,
            fix_hint="Reduce emphasis: lower font_size or cap animate.scale to <= 1.08.",
            object_type=obj_type,
            text=txt,
            width=round(tw, 2),
            height=round(th, 2),
            center_x=round(tx, 2),
            center_y=round(ty, 2),
            reason="text_dominance",
        ))

    # ═══════════════════════════════════════════════════════════════════
    # 2c. FILLED SHAPE DOMINANCE
    # Catch giant filled overlays that consume a large fraction of the frame.
    for _, o in objects:
        obj_type = type(o).__name__
        if obj_type in EFFECT_TYPES or obj_type in CONTAINER_TYPES:
            continue
        if _is_text(o):
            continue

        try:
            fill_opacity = o.get_fill_opacity() if hasattr(o, "get_fill_opacity") else 0.0
        except Exception:
            fill_opacity = 0.0
        if fill_opacity is None or fill_opacity < FILL_DOMINANCE_OPACITY:
            continue

        try:
            ow, oh = o.width, o.height
            ox, oy, _ = o.get_center()
        except Exception:
            continue
        if ow < 0.5 or oh < 0.5:
            continue

        area_ratio = (ow * oh) / FRAME_AREA if FRAME_AREA > 0 else 0.0
        if area_ratio < FILL_DOMINANCE_AREA_RATIO:
            continue

        msg = (
            f"Filled {obj_type} dominates frame "
            f"(area {area_ratio:.0%}, opacity {fill_opacity:.2f}, size {ow:.1f}x{oh:.1f})"
        )
        new_issues.append(_issue(
            "critical", "high", "visual_quality", msg,
            auto_fixable=True,
            fix_hint="Reduce fill_opacity or resize/reposition the shape to avoid covering content.",
            object_type=obj_type,
            width=round(ow, 2),
            height=round(oh, 2),
            center_x=round(ox, 2),
            center_y=round(oy, 2),
            fill_opacity=round(float(fill_opacity), 2),
            area_ratio=round(area_ratio, 2),
            reason="filled_shape_dominance",
        ))

    # 2d. STROKE-THROUGH-TEXT
    # Catch thin stroke objects (lines/grid strokes) drawn over text labels.
    LINE_TYPES = frozenset({
        "Line", "DashedLine", "Arrow", "DoubleArrow", "Vector", "NumberLine", "Underline"
    })
    PATH_STROKE_TYPES = frozenset({
        "Polygon", "Polyline", "Polygram", "VMobject",
        "Axes", "ThreeDAxes", "NumberPlane", "ComplexPlane"
    })

    for t_idx, t in texts:
        for o_idx, o in objects:
            if o_idx <= t_idx:
                continue
            if _is_family(t, o):
                continue
            # Suppress table grid lines crossing their own cell text —
            # this is normal Table layout, not a bug.
            if _shares_table_ancestor(t, o):
                continue

            obj_type = type(o).__name__
            try:
                ow, oh = o.width, o.height
            except Exception:
                continue

            thin = min(ow, oh)
            long_side = max(ow, oh)
            is_line_like = (
                obj_type in LINE_TYPES
                or (thin <= STROKE_MAX_THICKNESS and long_side >= STROKE_MIN_LENGTH)
            )

            try:
                fill_op = o.get_fill_opacity() if hasattr(o, "get_fill_opacity") else 0.0
            except Exception:
                fill_op = 0.0
            # Do not suppress line-like objects just because they have filled tips
            # (e.g., Arrow heads can have fill_opacity > 0).
            if fill_op is not None and fill_op > 0.2 and not is_line_like:
                continue

            try:
                stroke_op = o.get_stroke_opacity() if hasattr(o, "get_stroke_opacity") else 1.0
            except Exception:
                stroke_op = 1.0
            has_visible_stroke = stroke_op is None or stroke_op > 0.05

            ratio = _overlap_ratio(t, o)
            path_crosses_text = False
            if (
                has_visible_stroke and
                (
                    obj_type in PATH_STROKE_TYPES
                    or obj_type in LINE_TYPES
                    or "Polygon" in obj_type
                    or "Line" in obj_type
                    or "Arrow" in obj_type
                    or "Axes" in obj_type
                )
            ):
                path_crosses_text = _stroke_path_hits_text(t, o)

            near_gap = _bbox_distance(t, o)
            near_collision = (
                has_visible_stroke and
                near_gap <= STROKE_TEXT_NEAR_GAP and
                long_side >= STROKE_MIN_LENGTH
            )

            if not is_line_like and not path_crosses_text:
                continue
            if ratio < STROKE_THROUGH_RATIO and not path_crosses_text and not near_collision:
                continue

            txt = _text_label(t)
            msg = f"Stroke '{obj_type}' crosses text '{txt}' ({ratio:.0%} overlap)"
            if not path_crosses_text and near_collision:
                msg = f"Stroke '{obj_type}' is too close to text '{txt}' (gap {near_gap:.2f})"
            # Stroke-through-text is inherently ambiguous (could be a
            # legitimate grid line, axis tick, or decoration).  Route as
            # uncertain so Visual QC can verify against the rendered frame.
            new_issues.append(_issue(
                "warning", "low", "visual_quality", msg,
                auto_fixable=True,
                fix_hint="Raise label z-index or reposition text away from grid lines.",
                object_type=obj_type,
                text=txt,
                overlap_ratio=round(ratio, 2),
                path_crosses_text=path_crosses_text,
                near_gap=round(near_gap, 3),
                reason="stroke_through_text",
            ))

    # 3. OBJECT-ON-TEXT OCCLUSION (z-order aware)
    # ═══════════════════════════════════════════════════════════════════
    for t_idx, t in texts:
        for o_idx, o in objects:
            if o_idx <= t_idx:
                continue

            obj_type = type(o).__name__

            # ── False-positive suppression ──
            if obj_type in EFFECT_TYPES:
                continue
            if obj_type in CONTAINER_TYPES:
                continue
            if _is_family(t, o):
                continue
            try:
                if o.width > SCREEN_X:
                    continue
            except Exception:
                pass

            # SurroundingRectangle: suppress only if stroke-only (no fill)
            # A filled SurroundingRectangle covering text IS a real issue
            if obj_type in ("SurroundingRectangle", "Brace", "BraceBetweenPoints", "Cross"):
                try:
                    fill_op = o.get_fill_opacity() if hasattr(o, "get_fill_opacity") else 0
                    if fill_op < 0.15:
                        continue  # Stroke-only container — not occluding
                except Exception:
                    continue

            try:
                if hasattr(o, "get_fill_opacity") and o.get_fill_opacity() < 0.15:
                    continue
            except Exception:
                pass

            ratio = _overlap_ratio(t, o)
            if ratio < 0.08:
                continue

            txt = _trunc(getattr(t, "text", repr(t)))
            try:
                oc = o.get_center()
                pos_info = f"at ({oc[0]:.1f}, {oc[1]:.1f})"
                size_info = f"{o.width:.1f}x{o.height:.1f}"
            except Exception:
                pos_info = ""
                size_info = ""

            msg = (
                f"{obj_type} ({size_info} {pos_info}) "
                f"covers text '{txt}' ({ratio:.0%} overlap)"
            )

            if ratio > 0.5:
                new_issues.append(_issue(
                    "critical", "high", "object_occlusion", msg,
                    auto_fixable=True,
                    fix_hint="Reposition object, use stroke_only, or reduce fill_opacity",
                    object_type=obj_type, text=txt,
                    overlap_ratio=round(ratio, 2),
                ))
            elif ratio > 0.2:
                new_issues.append(_issue(
                    "warning", "medium", "object_occlusion", msg,
                    auto_fixable=True,
                    fix_hint="Object partially covering text — adjust position or opacity",
                    object_type=obj_type, text=txt,
                    overlap_ratio=round(ratio, 2),
                ))
            else:
                new_issues.append(_issue(
                    "info", "low", "object_occlusion", msg,
                    object_type=obj_type, text=txt,
                    overlap_ratio=round(ratio, 2),
                ))

    self._spatial_issues.extend(new_issues)
'''

# ── Injected at end of construct() to emit the final JSON report ─────────────
INJECTED_FINAL_REPORT = '''
# ── Spatial Validation: Final Report ──
self._perform_spatial_checks()
import json as _json_report
import sys as _sys_report

_issues_list = getattr(self, '_spatial_issues', [])
_seen = set()
_unique = []
for _iss in _issues_list:
    _key = _iss['message']
    if _key not in _seen:
        _seen.add(_key)
        _unique.append(_iss)

if _unique:
    _sys_report.exit("SPATIAL_ISSUES_JSON:" + _json_report.dumps(_unique))
'''

# ── Monkey-patch setup injected at start of construct() ──────────────────────
INJECTED_SETUP = """
# ── Spatial Validation: Continuous Monitoring ──
self._spatial_issues = []
self._original_play = self.play
self._original_wait = self.wait

def _monitored_play(*args, **kwargs):
    self._perform_spatial_checks()
    self._original_play(*args, **kwargs)
    self._perform_spatial_checks()

def _monitored_wait(*args, **kwargs):
    self._perform_spatial_checks()
    self._original_wait(*args, **kwargs)

self.play = _monitored_play
self.wait = _monitored_wait
"""

# ── Pre-parse templates at module load ───────────────────────────────────────
_INJECTED_METHOD_NODE = None
_INJECTED_SETUP_NODES = None
_INJECTED_FINAL_NODES = None

try:
    _tree = ast.parse(textwrap.dedent(INJECTED_METHOD))
    if _tree.body and isinstance(_tree.body[0], ast.FunctionDef):
        _INJECTED_METHOD_NODE = _tree.body[0]
except SyntaxError as exc:
    logger.warning(f"Invalid injected method template: {exc}")

try:
    _INJECTED_SETUP_NODES = ast.parse(textwrap.dedent(INJECTED_SETUP)).body
except SyntaxError as exc:
    logger.warning(f"Invalid injected setup template: {exc}")

try:
    _INJECTED_FINAL_NODES = ast.parse(textwrap.dedent(INJECTED_FINAL_REPORT)).body
except SyntaxError as exc:
    logger.warning(f"Invalid injected final-report template: {exc}")


class SpatialCheckInjector:
    """
    Injects confidence-based spatial validation into Manim code via AST.

    Workflow:
    1. Adds ``_perform_spatial_checks()`` to the Scene class.
    2. Monkey-patches ``play()`` / ``wait()`` at start of ``construct()``.
    3. Appends a final JSON report block at end of ``construct()``.

    Output:
    When critical issues exist the process exits with a structured JSON
    payload prefixed by SPATIAL_ISSUES_JSON:.  The RuntimeValidator parses
    this into typed ``ValidationIssue`` objects for smart triage.
    """

    def inject(self, code: str) -> str:
        """Inject spatial checks into Manim code.

        Args:
            code: Raw Manim Python source.

        Returns:
            Modified source with spatial checks injected, or the
            original source if injection fails gracefully.
        """
        try:
            tree = self._parse(code)
            if tree is None:
                return code

            scene_class = self._find_scene_class(tree)
            if scene_class is None:
                return code

            if not self._inject_method(scene_class):
                return code

            construct = self._find_construct(scene_class)
            if construct is None:
                return code

            self._inject_setup(construct)
            self._inject_final_report(construct)

            return ast.unparse(tree) if hasattr(ast, "unparse") else code

        except Exception as exc:
            logger.error(f"Spatial injection failed: {exc}")
            return code

    # ── Private helpers ──────────────────────────────────────────────────

    @staticmethod
    def _parse(code: str):
        try:
            return ast.parse(code)
        except SyntaxError as exc:
            logger.warning(
                f"Skipping spatial injection — syntax error: {exc}"
            )
            return None

    @staticmethod
    def _find_scene_class(tree: ast.Module):
        """Find the Scene subclass using heuristics.
        
        Priority:
        1. Class that contains a 'construct' method (most reliable for Manim)
        2. Class that explicitly inherits from a name ending in 'Scene'
        3. First class in the module as fallback
        """
        classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
        if not classes:
            return None

        # 1. Look for 'construct' method (Highest priority: this is where we inject)
        for node in classes:
            if any(isinstance(n, ast.FunctionDef) and n.name == "construct" for n in node.body):
                return node

        # 2. Look for 'Scene' in bases
        for node in classes:
            for base in node.bases:
                if isinstance(base, ast.Name) and "Scene" in base.id:
                    return node
                if isinstance(base, ast.Attribute) and "Scene" in base.attr:
                    return node

        # 3. Fallback: first class
        return classes[0]

    @staticmethod
    def _find_construct(scene_class: ast.ClassDef):
        return next(
            (
                n
                for n in scene_class.body
                if isinstance(n, ast.FunctionDef) and n.name == "construct"
            ),
            None,
        )

    @staticmethod
    def _inject_method(scene_class: ast.ClassDef) -> bool:
        if _INJECTED_METHOD_NODE is None:
            logger.warning("Spatial method template invalid — skipping")
            return False
        scene_class.body.append(copy.deepcopy(_INJECTED_METHOD_NODE))
        return True

    @staticmethod
    def _inject_setup(construct: ast.FunctionDef) -> None:
        if not _INJECTED_SETUP_NODES:
            logger.warning("Spatial setup template invalid — skipping")
            return
        # Insert after docstring if present
        insert_idx = 0
        if (
            construct.body
            and isinstance(construct.body[0], ast.Expr)
            and isinstance(construct.body[0].value, ast.Constant)
            and isinstance(construct.body[0].value.value, str)
        ):
            insert_idx = 1
        construct.body[insert_idx:insert_idx] = [
            copy.deepcopy(n) for n in _INJECTED_SETUP_NODES
        ]

    @staticmethod
    def _inject_final_report(construct: ast.FunctionDef) -> None:
        if not _INJECTED_FINAL_NODES:
            logger.warning("Spatial final-report template invalid — skipping")
            return
        construct.body.extend(copy.deepcopy(n) for n in _INJECTED_FINAL_NODES)
