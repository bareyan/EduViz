"""
Spatial Check Injector

Injects AST-based spatial validation into Manim Scene code.

Key improvements over v1:
- Confidence-based classification (CRITICAL / WARNING / INFO)
- Overlap-ratio computation instead of binary AABB
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
    import json as _json

    # ── Screen limits ──
    SCREEN_X = 7.1
    SCREEN_Y = 4.0
    SAFE_X = 5.5
    SAFE_Y = 3.0

    # ── Types we expect to overlap (not bugs) ──
    EFFECT_TYPES = frozenset({
        "Flash", "Indicate", "Circumscribe", "ShowPassingFlash",
        "ApplyWave", "Wiggle", "AnimationGroup", "FadeOut", "FadeIn",
        "ShowCreation", "Uncreate", "GrowFromCenter", "SpinInFromNothing",
        "ShrinkToCenter", "ShowIncreasingSubsets", "ShowSubmobjectsOneByOne",
    })
    CONTAINER_TYPES = frozenset({
        "SurroundingRectangle", "BackgroundRectangle",
        "Underline", "Brace", "BraceBetweenPoints", "Cross",
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

    def _trunc(s, n=50):
        return s[:n] if len(s) > n else s

    def _issue(severity, confidence, category, message, auto_fixable=False, fix_hint=None, **details):
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
    # 1. BOUNDS CHECK
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

        overshoot_x = max(0, -left - SCREEN_X, right - SCREEN_X)
        overshoot_y = max(0, -bottom - SCREEN_Y, top - SCREEN_Y)
        overshoot = max(overshoot_x, overshoot_y)

        if overshoot <= 0:
            continue

        obj_type = type(m).__name__
        msg = (
            f"Object '{obj_type}' out of bounds at "
            f"({x:.1f}, {y:.1f}), size {w:.1f}x{h:.1f}, "
            f"overshoot {overshoot:.1f}"
        )

        if overshoot > 1.0:
            new_issues.append(_issue(
                "critical", "high", "out_of_bounds", msg,
                auto_fixable=True,
                fix_hint=f"Shift or scale to bring within +/-{SAFE_X} x +/-{SAFE_Y}",
                object_type=obj_type, center_x=round(x, 2), center_y=round(y, 2),
                width=round(w, 2), height=round(h, 2), overshoot=round(overshoot, 2),
            ))
        elif overshoot > 0.3:
            new_issues.append(_issue(
                "warning", "medium", "out_of_bounds", msg,
                auto_fixable=True,
                fix_hint=f"Minor adjustment needed (~{overshoot:.1f} units)",
                object_type=obj_type, center_x=round(x, 2), center_y=round(y, 2),
                overshoot=round(overshoot, 2),
            ))
        # overshoot <= 0.3 -> sub-pixel, ignore

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
        is_text = "Text" in type(m).__name__ or hasattr(m, "text")
        if is_text:
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
            if ratio < 0.05:
                continue

            txt1 = _trunc(getattr(t1, "text", repr(t1)))
            txt2 = _trunc(getattr(t2, "text", repr(t2)))
            msg = f"Text overlap ({ratio:.0%}): '{txt1}' overlaps '{txt2}'"

            if ratio > 0.4:
                new_issues.append(_issue(
                    "critical", "high", "text_overlap", msg,
                    auto_fixable=True,
                    fix_hint="Separate texts with .next_to() or .shift()",
                    text1=txt1, text2=txt2, overlap_ratio=round(ratio, 2),
                ))
            elif ratio > 0.15:
                new_issues.append(_issue(
                    "warning", "medium", "text_overlap", msg,
                    text1=txt1, text2=txt2, overlap_ratio=round(ratio, 2),
                ))
            # < 0.15 -> marginal, skip

    # ═══════════════════════════════════════════════════════════════════
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
            try:
                if hasattr(o, "get_fill_opacity") and o.get_fill_opacity() < 0.15:
                    continue
            except Exception:
                pass

            ratio = _overlap_ratio(t, o)
            if ratio < 0.1:
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

            if ratio > 0.6:
                new_issues.append(_issue(
                    "warning", "medium", "object_occlusion", msg,
                    fix_hint="Reposition object or add transparency",
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
if hasattr(self, '_spatial_issues') and self._spatial_issues:
    import json as _json_report
    import sys as _sys_report

    _seen = set()
    _unique = []
    for _iss in self._spatial_issues:
        _key = _iss['message']
        if _key not in _seen:
            _seen.add(_key)
            _unique.append(_iss)

    _has_critical = any(_i['severity'] == 'critical' for _i in _unique)

    if _has_critical:
        _sys_report.exit("SPATIAL_ISSUES_JSON:" + _json_report.dumps(_unique))
    else:
        for _i in _unique:
            print(
                "SPATIAL_WARNING: " + _i['message'],
                file=_sys_report.stderr,
            )
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
        """Find the Scene subclass (or first class as fallback)."""
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                is_scene = any(
                    isinstance(base, ast.Name) and base.id == "Scene"
                    for base in node.bases
                )
                if is_scene:
                    return node

        # Fallback: first class (e.g. ThreeDScene, MovingCameraScene)
        return next(
            (n for n in tree.body if isinstance(n, ast.ClassDef)), None
        )

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
