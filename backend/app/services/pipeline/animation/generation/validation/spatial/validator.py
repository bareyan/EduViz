"""
Main spatial validation logic for Manim code.
"""

import importlib.util
import inspect
import itertools
import linecache
import logging
import os
import sys
import tempfile
from io import StringIO
from typing import Any, Callable, Dict, List, Optional, Tuple

from .constants import (
    CONTRAST_RATIO_MIN,
    MAX_FONT_SIZE,
    MAX_TEXT_CHARS,
    OCCLUSION_MIN_AREA,
    OVERLAP_MARGIN,
    PLOT_TYPES,
    RECOMMENDED_FONT_SIZE,
    TEXT_TYPES,
)
from .models import SpatialIssue, SpatialValidationResult
from .geometry import get_overlap_metrics, get_z_index, get_boundary_violation
from .color import get_contrast_ratio, get_text_color, _color_to_rgb
from .utils import (
    get_atomic_mobjects,
    get_user_code_context,
    is_overlapping,
    is_visible,
)
from .events import LintEvent, SceneTracker

LOGGER = logging.getLogger(__name__)


class SpatialValidator:
    """
    Validates spatial layout of Manim objects by executing the code.
    """

    def __init__(self, linter_path: Optional[str] = None) -> None:
        self.trackers: Dict[Any, SceneTracker] = {}
        self._manim_classes: Optional[Dict[str, type]] = None
        self._manim_config: Optional[Any] = None
        self._Scene_class: Optional[type] = None
        self._ThreeDScene_class: Optional[type] = None
        self._linter_path = linter_path or os.path.abspath(__file__)

    def _load_manim(self) -> None:
        """Lazy load Manim classes."""
        if self._manim_classes is not None:
            return

        from manim import (
            config, Scene, ThreeDScene,
            Text, MathTex, Tex, Code, ImageMobject,
            VMobject, NumberPlane, Axes, Arrow, Line,
            DashedLine, Brace, Vector, ComplexPlane,
            Circle, Square, Rectangle
        )

        self._manim_config = config
        self._Scene_class = Scene
        self._ThreeDScene_class = ThreeDScene

        self._manim_classes = {
            'Text': Text,
            'MathTex': MathTex,
            'Tex': Tex,
            'Code': Code,
            'ImageMobject': ImageMobject,
            'VMobject': VMobject,
            'NumberPlane': NumberPlane,
            'Axes': Axes,
            'Arrow': Arrow,
            'Line': Line,
            'DashedLine': DashedLine,
            'Brace': Brace,
            'Vector': Vector,
            'ComplexPlane': ComplexPlane,
            'Circle': Circle,
            'Square': Square,
            'Rectangle': Rectangle,
        }

    def _check_scene_state(self, scene: Any) -> None:
        """Analyze current scene state for spatial issues."""
        if scene not in self.trackers:
            self.trackers[scene] = SceneTracker()
        tracker = self.trackers[scene]

        if self._manim_classes is None or self._manim_config is None:
            raise RuntimeError("Manim not initialized; call _load_manim() first.")

        current_time = scene.renderer.time
        fname, curr_line = get_user_code_context(self._linter_path)

        atoms = []
        for m in scene.mobjects:
            atoms.extend(get_atomic_mobjects(m, self._manim_classes))

        active_overlap_ids = set()
        active_occlusion_ids = set()
        active_contrast_ids = set()

        bg_color = _color_to_rgb(getattr(self._manim_config, "background_color", None))

        for m1, m2 in itertools.combinations(atoms, 2):
            if is_overlapping(m1, m2, OVERLAP_MARGIN):
                pair_id = f"OVLP_{id(m1)}_{id(m2)}"
                active_overlap_ids.add(pair_id)

                if pair_id not in tracker.active_events:
                    evt = LintEvent(m1, m2, "overlap", current_time, fname, curr_line)
                    tracker.active_events[pair_id] = evt

                tracker.active_events[pair_id].update(current_time, m1, m2)

                # Occlusion check
                area, _, _ = get_overlap_metrics(m1, m2)
                if area >= OCCLUSION_MIN_AREA:
                    self._detect_occlusions(m1, m2, area, tracker, current_time, fname, curr_line, active_occlusion_ids)

        # Contrast checks
        self._detect_low_contrast(atoms, bg_color, tracker, current_time, fname, curr_line, active_contrast_ids)

        # Quality heuristics (font size, length)
        active_quality_ids = set()
        self._detect_quality_heuristics(atoms, tracker, current_time, fname, curr_line, active_quality_ids)

        # Boundary checks
        active_boundary_ids = set()
        for m in atoms:
            result = get_boundary_violation(m, self._manim_config)
            if result and result[0] > 0:
                b_id = f"BND_{id(m)}"
                active_boundary_ids.add(b_id)
                if b_id not in tracker.active_events:
                    tracker.active_events[b_id] = LintEvent(m, None, "boundary", current_time, fname, curr_line)
                tracker.active_events[b_id].update(current_time, m, manim_config=self._manim_config)

        # Cleanup
        all_current = active_overlap_ids | active_boundary_ids | active_occlusion_ids | active_contrast_ids | active_quality_ids
        for eid in list(tracker.active_events.keys()):
            if eid not in all_current:
                event = tracker.active_events.pop(eid)
                event.finish(curr_line, is_scene_end=False)
                tracker.history.append(event)

    def _detect_occlusions(self, m1, m2, area, tracker, current_time, fname, curr_line, active_ids):
        z1, z2 = get_z_index(m1), get_z_index(m2)
        m1_t, m2_t = m1.__class__.__name__, m2.__class__.__name__

        for target, anchor, tz, az in [(m1, m2, z1, z2), (m2, m1, z2, z1)]:
            if target.__class__.__name__ in TEXT_TYPES and tz < az:
                oid = f"OCC_{id(target)}_{id(anchor)}"
                active_ids.add(oid)
                if oid not in tracker.active_events:
                    tracker.active_events[oid] = LintEvent(target, anchor, "occlusion", current_time, fname, curr_line)
                tracker.active_events[oid].update(current_time, target, anchor, z_info=f"z_index {tz:.2f} behind {az:.2f}")

    def _detect_low_contrast(self, atoms, bg_color, tracker, current_time, fname, curr_line, active_ids):
        for m in atoms:
            if m.__class__.__name__ not in TEXT_TYPES: continue
            if not is_visible(m, self._manim_classes["VMobject"], self._manim_classes["ImageMobject"]): continue
            
            fg = _color_to_rgb(get_text_color(m))
            ratio = get_contrast_ratio(fg, bg_color)
            if ratio is not None and ratio < CONTRAST_RATIO_MIN:
                cid = f"CTR_{id(m)}"
                active_ids.add(cid)
                if cid not in tracker.active_events:
                    tracker.active_events[cid] = LintEvent(m, None, "contrast", current_time, fname, curr_line)
                tracker.active_events[cid].update(current_time, m, z_info=f"Contrast ratio {ratio:.2f} < {CONTRAST_RATIO_MIN:.2f}")

    def _detect_quality_heuristics(self, atoms, tracker, current_time, fname, curr_line, active_ids):
        """Checks for oversized fonts or overly long text blocks."""
        for m in atoms:
            m_type = m.__class__.__name__
            if m_type not in TEXT_TYPES: continue
            
            # Font Size Check
            fs = getattr(m, "font_size", 48)
            if fs > MAX_FONT_SIZE:
                q_id = f"FNT_{id(m)}"
                active_ids.add(q_id)
                if q_id not in tracker.active_events:
                    tracker.active_events[q_id] = LintEvent(m, None, "font_size", current_time, fname, curr_line)
                tracker.active_events[q_id].update(current_time, m)

            # Text Length Check
            text_val = ""
            if "Text" in m_type:
                text_val = getattr(m, "text", "")
            elif "Tex" in m_type:
                # Tex stores parts in tex_string or sub-mobjects
                text_val = getattr(m, "tex_string", "")
            
            if len(text_val) > MAX_TEXT_CHARS:
                l_id = f"LEN_{id(m)}"
                active_ids.add(l_id)
                if l_id not in tracker.active_events:
                    tracker.active_events[l_id] = LintEvent(m, None, "length", current_time, fname, curr_line)
                tracker.active_events[l_id].update(current_time, m)

    def _create_patched_methods(self) -> Tuple[Callable, Callable, Callable, Callable]:
        if self._Scene_class is None: raise RuntimeError("Call _load_manim() first.")
        v = self
        orig_p, orig_w = self._Scene_class.play, self._Scene_class.wait
        def p_p(s, *a, **k): orig_p(s, *a, **k); v._check_scene_state(s)
        def p_w(s, *a, **k): orig_w(s, *a, **k); v._check_scene_state(s)
        return orig_p, orig_w, p_p, p_w

    def validate(self, code: str) -> SpatialValidationResult:
        """Execute Manim code and collect spatial issues."""
        try:
            self._load_manim()
        except ImportError as e:
            return SpatialValidationResult(valid=True, raw_report=f"Manim unavailable: {e}")

        self.trackers.clear()
        self._apply_fast_config()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_filename = f.name

        try:
            return self._run_validation(temp_filename, code)
        finally:
            self._cleanup_temp(temp_filename)

    def _apply_fast_config(self):
        self._manim_config.update({
            "write_to_movie": False, "save_last_frame": False,
            "preview": False, "verbosity": "CRITICAL",
            "renderer": "cairo", "frame_rate": 1, "quality": "low_quality"
        })

    def _run_validation(self, temp_filename, code) -> SpatialValidationResult:
        orig_p, orig_w, pat_p, pat_w = self._create_patched_methods()
        self._Scene_class.play, self._Scene_class.wait = pat_p, pat_w
        
        errors, warnings, raw = [], [], []
        module_name = os.path.basename(temp_filename).replace(".py", "")
        
        try:
            spec = importlib.util.spec_from_file_location(module_name, temp_filename)
            if not spec or not spec.loader: raise ImportError("Invalid spec")
            user_module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = user_module
            spec.loader.exec_module(user_module)

            scenes = [obj for _, obj in inspect.getmembers(user_module) 
                     if inspect.isclass(obj) and issubclass(obj, self._Scene_class) 
                     and obj.__module__ == module_name]

            for SCls in scenes:
                self._manim_config.renderer = "opengl" if issubclass(SCls, self._ThreeDScene_class) else "cairo"
                scene = SCls()
                scene.render()
                
                if scene in self.trackers:
                    _, last = get_user_code_context(self._linter_path)
                    self.trackers[scene].close_all(last)
                    report = self.trackers[scene].generate_report_string(SCls.__name__)
                    if report: raw.append(report)
                    self._collect_issues(scene, code, errors, warnings)
        except Exception as e:
            errors.append(SpatialIssue(0, "error", f"Validation crashed: {e}", ""))
        finally:
            self._Scene_class.play, self._Scene_class.wait = orig_p, orig_w
            if module_name in sys.modules: del sys.modules[module_name]
            
        return SpatialValidationResult(valid=not errors, errors=errors, warnings=warnings, raw_report="\n".join(raw))

    def _collect_issues(self, scene, code, errors, warnings):
        for ev in self.trackers[scene].history:
            snippet = self._get_code_snippet(code, ev.start_line)
            if ev.event_type == "overlap":
                m1_t, m2_t = ev.m1_type in TEXT_TYPES, ev.m2_type in TEXT_TYPES
                m1_p, m2_p = ev.m1_type in PLOT_TYPES, ev.m2_type in PLOT_TYPES
                
                if m1_t and m2_t:
                    errors.append(SpatialIssue(ev.start_line, "error", f"{ev.m1_name} overlaps {ev.m2_name} (text/text) - {ev.details}", snippet))
                elif (m1_p and m2_t) or (m2_p and m1_t):
                    warnings.append(SpatialIssue(ev.start_line, "info", f"[MINOR] {ev.m1_name} overlaps {ev.m2_name} - {ev.details}", snippet))
                else:
                    warnings.append(SpatialIssue(ev.start_line, "warning", f"{ev.m1_name} overlaps {ev.m2_name} - {ev.details}", snippet))
            elif ev.event_type == "occlusion":
                warnings.append(SpatialIssue(ev.start_line, "warning", f"{ev.m1_name} occluded by {ev.m2_name} - {ev.details}", snippet))
            elif ev.event_type == "contrast":
                warnings.append(SpatialIssue(ev.start_line, "warning", f"{ev.m1_name} low contrast - {ev.details}", snippet))
            elif ev.event_type == "boundary":
                msg = f"{ev.m1_name} out of bounds" + (" (PERSISTS)" if ev.persists_to_end else "") + f" - {ev.details}"
                errors.append(SpatialIssue(ev.start_line, "error", msg, snippet))
            elif ev.event_type == "font_size":
                warnings.append(SpatialIssue(ev.start_line, "warning", f"{ev.m1_name} font size too large - {ev.details}", snippet))
            elif ev.event_type == "length":
                warnings.append(SpatialIssue(ev.start_line, "warning", f"{ev.m1_name} text too long - {ev.details}", snippet))

    def _cleanup_temp(self, path):
        try: os.unlink(path)
        except Exception as e: LOGGER.debug("Cleanup failed: %s", e)
        linecache.clearcache()

    def _get_code_snippet(self, code: str, ln: int) -> str:
        lines = code.split('\n')
        return lines[ln - 1].strip() if 0 < ln <= len(lines) else ""
