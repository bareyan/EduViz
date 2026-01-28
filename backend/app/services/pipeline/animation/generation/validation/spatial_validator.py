"""
Spatial layout validation for Manim code

Validates that objects don't overlap and stay within screen bounds.
Uses runtime analysis by executing Manim code in a controlled environment.
"""

import sys
import os
import inspect
import importlib.util
import itertools
import linecache
import tempfile
from io import StringIO
from typing import List, Dict, Optional
from dataclasses import dataclass, field

# Manim imports will be done dynamically during validation
# to avoid import issues when manim is not available

# ==========================================
# CONFIGURATION
# ==========================================
SAFETY_MARGIN = 0.2  # How close to the edge is "too close"?
OVERLAP_MARGIN = 0.05  # Overlap buffer


@dataclass
class SpatialIssue:
    """A spatial layout issue"""
    line_number: int
    severity: str  # "error" or "warning"
    message: str
    code_snippet: str


@dataclass
class SpatialValidationResult:
    """Result of spatial validation"""
    valid: bool
    errors: List[SpatialIssue] = field(default_factory=list)
    warnings: List[SpatialIssue] = field(default_factory=list)
    raw_report: str = ""  # Full text report from linter

    @property
    def has_issues(self) -> bool:
        """Check if there are any errors or warnings"""
        return len(self.errors) > 0 or len(self.warnings) > 0


# ==========================================
# GEOMETRY & CHECKS
# ==========================================

def get_overlap_metrics(m1, m2):
    """Returns (area, center, desc) using .width/.height properties."""
    import numpy as np
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
    except:
        return 0.0, None, "Error"


def get_boundary_violation(mobj, manim_config):
    """
    Checks if mobject is out of frame or in safety margin.
    Returns: (severity_score, description) or None
    """
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
    except:
        return None


def get_loc_desc(center):
    """Get location description from center coordinates."""
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


# ==========================================
# TRACKING SYSTEM
# ==========================================

class LintEvent:
    """Represents a single spatial issue event."""

    def __init__(self, m1, m2, event_type, start_time, filename, start_line, total_duration=None):
        self.event_type = event_type  # "overlap" or "boundary"

        # Object Names
        self.m1_name = self._clean_name(m1)
        self.m2_name = self._clean_name(m2) if m2 else None
        
        # Object types for categorization
        self.m1_type = m1.__class__.__name__ if m1 else None
        self.m2_type = m2.__class__.__name__ if m2 else None

        # Time
        self.start_time = start_time
        self.end_time = start_time
        self.total_duration = total_duration  # Total scene duration for end-of-video detection

        # Context
        self.filename = filename
        self.start_line = start_line
        self.end_line = start_line
        
        # Whether the issue persists until the end of the video
        self.persists_to_end = False

        # Metrics
        self.max_severity = 0.0  # Area for overlap, Distance for boundary
        self.details = "Unknown"

    def _clean_name(self, m):
        if not m:
            return ""
        obj_type = m.__class__.__name__
        content = getattr(m, "tex_string", getattr(m, "text", ""))
        if content:
            content = content.replace("\n", " ").strip()[:30]
            return f'{obj_type}("{content}")'
        return obj_type

    def update(self, current_time, m1, m2=None, manim_config=None):
        self.end_time = current_time

        if self.event_type == "overlap":
            area, _, desc = get_overlap_metrics(m1, m2)
            if area > self.max_severity:
                self.max_severity = area
                self.details = f"{desc} [Max Area: {area:.2f}]"

        elif self.event_type == "boundary" and manim_config:
            result = get_boundary_violation(m1, manim_config)
            if result:
                dist, desc = result
                if dist > self.max_severity:
                    self.max_severity = dist
                    self.details = desc

    def finish(self, end_line, is_scene_end=False):
        self.end_line = end_line
        self.persists_to_end = is_scene_end

    def duration(self):
        return self.end_time - self.start_time


class SceneTracker:
    """Tracks spatial issues during scene rendering."""

    def __init__(self):
        self.active_events: Dict[str, LintEvent] = {}
        self.history: List[LintEvent] = []

    def close_all(self, final_line, is_scene_end=True):
        for eid, event in list(self.active_events.items()):
            event.finish(final_line, is_scene_end=is_scene_end)
            self.history.append(event)
        self.active_events.clear()

    def generate_report_string(self, scene_name: str) -> Optional[str]:
        """Generates a formatted string log."""
        if not self.history:
            return None

        output = StringIO()

        # Header
        output.write(f"\n{'=' * 60}\n")
        output.write(f" SCENE: {scene_name} ({len(self.history)} issues)\n")
        output.write(f"{'=' * 60}\n")

        self.history.sort(key=lambda x: x.start_time)

        for i, ev in enumerate(self.history, 1):
            dur = ev.duration()
            if ev.persists_to_end:
                time_str = f"{ev.start_time:.2f}s -> END OF VIDEO"
                dur_str = "(Persists to end of video)"
            else:
                time_str = f"{ev.start_time:.2f}s -> {ev.end_time:.2f}s"
                dur_str = "(Instant)" if dur < 0.05 else f"(Duration: {dur:.2f}s)"

            output.write(f"\n{i}. [{time_str}] {dur_str}\n")

            # Type Specific Message
            if ev.event_type == "overlap":
                # Determine if this is a plot/text overlap (less harsh) or text/text overlap
                plot_types = {'Axes', 'NumberPlane', 'BarChart', 'Graph', 'Plot', 'FunctionGraph', 'ParametricFunction'}
                text_types = {'Text', 'MathTex', 'Tex', 'Paragraph', 'MarkupText', 'Title', 'BulletedList'}
                
                m1_is_plot = ev.m1_type in plot_types
                m2_is_plot = ev.m2_type in plot_types
                m1_is_text = ev.m1_type in text_types
                m2_is_text = ev.m2_type in text_types
                
                if (m1_is_plot and m2_is_text) or (m1_is_text and m2_is_plot):
                    output.write(f"   [OVERLAP - PLOT/TEXT] '{ev.m1_name}' intersects '{ev.m2_name}'\n")
                    output.write(f"   Note: Plot and text overlap - consider repositioning for better readability\n")
                else:
                    output.write(f"   [OVERLAP] '{ev.m1_name}' intersects '{ev.m2_name}'\n")
            else:
                if ev.persists_to_end:
                    output.write(f"   [OUT OF FRAME - PERSISTS TO END] '{ev.m1_name}' is out of frame bounds\n")
                else:
                    output.write(f"   [OUT OF FRAME] '{ev.m1_name}' is too close to edge\n")

            output.write(f"   Details:  {ev.details}\n")

            # Location
            if ev.start_line == ev.end_line:
                output.write(f"   Location: Line {ev.start_line}\n")
            else:
                output.write(f"   Location: Lines {ev.start_line} - {ev.end_line}\n")

            # Code Block
            output.write("   Code Trace:\n")
            if ev.filename and ev.filename != "unknown":
                for ln in range(ev.start_line, ev.end_line + 1):
                    line = linecache.getline(ev.filename, ln)
                    if line.strip():
                        output.write(f"      {ln:4d} | {line.rstrip()}\n")
            else:
                output.write("      <Source unavailable>\n")

        return output.getvalue()


# ==========================================
# UTILS & HELPERS
# ==========================================

def get_user_code_context(linter_path: str):
    """Get the filename and line number from user code."""
    stack = inspect.stack(context=0)
    for frame_info in stack:
        filename = os.path.abspath(frame_info.filename)
        if filename == linter_path:
            continue
        if "site-packages" in filename:
            continue
        if "lib/python" in filename:
            continue
        return filename, frame_info.lineno
    return "unknown", 0


def is_visible(mobj, VMobject_class, ImageMobject_class):
    """Check if a mobject is visible."""
    if isinstance(mobj, VMobject_class):
        try:
            if mobj.get_fill_opacity() == 0 and mobj.get_stroke_opacity() == 0:
                return False
        except:
            pass
    elif isinstance(mobj, ImageMobject_class):
        if hasattr(mobj, "opacity") and mobj.opacity == 0:
            return False
    return True


def get_atomic_mobjects(mobject, manim_classes: dict):
    """Get atomic mobjects that should be checked for overlaps."""
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


def is_overlapping(m1, m2):
    """Check if two mobjects are overlapping."""
    try:
        w1, h1 = m1.width, m1.height
        w2, h2 = m2.width, m2.height
        if w1 < 0.01 or h1 < 0.01 or w2 < 0.01 or h2 < 0.01:
            return False

        c1, c2 = m1.get_center(), m2.get_center()

        if (abs(c1[0] - c2[0]) * 2 < (w1 + w2 - OVERLAP_MARGIN)) and \
           (abs(c1[1] - c2[1]) * 2 < (h1 + h2 - OVERLAP_MARGIN)):
            return True
        return False
    except:
        return False


# ==========================================
# MAIN SPATIAL VALIDATOR CLASS
# ==========================================

class SpatialValidator:
    """
    Validates spatial layout of Manim objects by executing the code.

    Checks:
    - Objects overlapping with each other
    - Objects positioned outside screen bounds or in safety margin
    """

    def __init__(self):
        self.trackers: Dict = {}
        self._manim_classes: Optional[dict] = None
        self._manim_config = None
        self._Scene_class = None
        self._ThreeDScene_class = None
        self._linter_path = os.path.abspath(__file__)

    def _load_manim(self):
        """Lazy load manim to avoid import issues."""
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

    def _check_scene_state(self, scene):
        """Check current scene state for spatial issues."""
        if scene not in self.trackers:
            self.trackers[scene] = SceneTracker()
        tracker = self.trackers[scene]

        current_time = scene.renderer.time
        fname, curr_line = get_user_code_context(self._linter_path)

        # Gather atoms
        atoms = []
        for m in scene.mobjects:
            atoms.extend(get_atomic_mobjects(m, self._manim_classes))

        # --- 1. Detect Overlaps ---
        active_overlap_ids = set()

        for m1, m2 in itertools.combinations(atoms, 2):
            if is_overlapping(m1, m2):
                pair_id = f"OVLP_{id(m1)}_{id(m2)}"
                active_overlap_ids.add(pair_id)

                # Create or Update
                if pair_id not in tracker.active_events:
                    evt = LintEvent(m1, m2, "overlap", current_time, fname, curr_line)
                    tracker.active_events[pair_id] = evt

                tracker.active_events[pair_id].update(current_time, m1, m2)

        # --- 2. Detect Out of Bounds ---
        active_boundary_ids = set()

        for m in atoms:
            result = get_boundary_violation(m, self._manim_config)
            if result:
                score, _ = result
                if score > 0:
                    b_id = f"BND_{id(m)}"
                    active_boundary_ids.add(b_id)

                    if b_id not in tracker.active_events:
                        evt = LintEvent(m, None, "boundary", current_time, fname, curr_line)
                        tracker.active_events[b_id] = evt

                    tracker.active_events[b_id].update(current_time, m, manim_config=self._manim_config)

        # --- 3. Close Finished Events ---
        all_current_ids = active_overlap_ids.union(active_boundary_ids)
        active_keys = list(tracker.active_events.keys())

        for eid in active_keys:
            if eid not in all_current_ids:
                # Event ended mid-scene
                event = tracker.active_events.pop(eid)
                event.finish(curr_line, is_scene_end=False)
                tracker.history.append(event)

    def _create_patched_methods(self):
        """Create patched play and wait methods."""
        validator = self
        original_play = self._Scene_class.play
        original_wait = self._Scene_class.wait

        def patched_play(scene_self, *args, **kwargs):
            original_play(scene_self, *args, **kwargs)
            validator._check_scene_state(scene_self)

        def patched_wait(scene_self, *args, **kwargs):
            original_wait(scene_self, *args, **kwargs)
            validator._check_scene_state(scene_self)

        return original_play, original_wait, patched_play, patched_wait

    def validate(self, code: str) -> SpatialValidationResult:
        """
        Validate spatial layout of Manim code by executing it.

        Args:
            code: Manim Python code to validate

        Returns:
            SpatialValidationResult with spatial issues
        """
        errors: List[SpatialIssue] = []
        warnings: List[SpatialIssue] = []
        raw_report = ""

        try:
            self._load_manim()
        except ImportError as e:
            # Manim not available, return empty result
            return SpatialValidationResult(
                valid=True,
                errors=[],
                warnings=[],
                raw_report=f"Manim not available: {e}"
            )

        # Reset trackers
        self.trackers.clear()

        # Configure manim for fast validation
        self._manim_config.write_to_movie = False
        self._manim_config.save_last_frame = False
        self._manim_config.preview = False
        self._manim_config.verbosity = "CRITICAL"
        self._manim_config.renderer = "cairo"
        self._manim_config.frame_rate = 1  # Optimization: 1 FPS avoids calculating intermediate frames
        self._manim_config.quality = "low_quality" # Optimization: Use low resolution


        # Create temporary file for the code
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_filename = f.name

        module_name = None
        try:
            # Patch Scene methods
            original_play, original_wait, patched_play, patched_wait = self._create_patched_methods()
            self._Scene_class.play = patched_play
            self._Scene_class.wait = patched_wait

            try:
                # Dynamic Import
                module_name = os.path.basename(temp_filename).replace(".py", "")
                spec = importlib.util.spec_from_file_location(module_name, temp_filename)
                user_module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = user_module

                try:
                    spec.loader.exec_module(user_module)
                except Exception as e:
                    return SpatialValidationResult(
                        valid=False,
                        errors=[SpatialIssue(
                            line_number=0,
                            severity="error",
                            message=f"Could not load module: {e}",
                            code_snippet=""
                        )],
                        warnings=[],
                        raw_report=f"CRITICAL ERROR: Could not load module.\n{e}"
                    )

                # Find Scenes
                scenes_to_run = []
                for name, obj in inspect.getmembers(user_module):
                    if inspect.isclass(obj) and issubclass(obj, self._Scene_class):
                        if obj.__module__ == module_name:
                            scenes_to_run.append(obj)

                if not scenes_to_run:
                    return SpatialValidationResult(
                        valid=True,
                        errors=[],
                        warnings=[],
                        raw_report="No local Scene classes found."
                    )

                # Run Scenes
                full_report_buffer = StringIO()

                for SceneClass in scenes_to_run:
                    try:
                        if issubclass(SceneClass, self._ThreeDScene_class):
                            self._manim_config.renderer = "opengl"
                        else:
                            self._manim_config.renderer = "cairo"

                        scene = SceneClass()
                        scene.render()

                        # Close pending events (these persist to end of video)
                        if scene in self.trackers:
                            _, last_line = get_user_code_context(self._linter_path)
                            self.trackers[scene].close_all(last_line, is_scene_end=True)

                            report = self.trackers[scene].generate_report_string(SceneClass.__name__)
                            if report:
                                full_report_buffer.write(report)

                                # Convert events to SpatialIssue objects
                                plot_types = {'Axes', 'NumberPlane', 'BarChart', 'Graph', 'Plot', 'FunctionGraph', 'ParametricFunction'}
                                text_types = {'Text', 'MathTex', 'Tex', 'Paragraph', 'MarkupText', 'Title', 'BulletedList'}
                                
                                for event in self.trackers[scene].history:
                                    if event.event_type == "overlap":
                                        # Determine if this is a plot/text overlap (less harsh)
                                        m1_is_plot = event.m1_type in plot_types
                                        m2_is_plot = event.m2_type in plot_types
                                        m1_is_text = event.m1_type in text_types
                                        m2_is_text = event.m2_type in text_types
                                        
                                        is_plot_text_overlap = (m1_is_plot and m2_is_text) or (m1_is_text and m2_is_plot)
                                        
                                        if is_plot_text_overlap:
                                            msg = f"[MINOR] '{event.m1_name}' overlaps with '{event.m2_name}' - consider repositioning for better readability - {event.details}"
                                            severity = "info"  # Less harsh for plot/text overlaps
                                        else:
                                            msg = f"'{event.m1_name}' overlaps with '{event.m2_name}' - {event.details}"
                                            severity = "warning"
                                        
                                        warnings.append(SpatialIssue(
                                            line_number=event.start_line,
                                            severity=severity,
                                            message=msg,
                                            code_snippet=self._get_code_snippet(code, event.start_line)
                                        ))
                                    else:  # boundary
                                        if event.persists_to_end:
                                            msg = f"'{event.m1_name}' is out of frame bounds and PERSISTS UNTIL END OF VIDEO - {event.details}"
                                        else:
                                            msg = f"'{event.m1_name}' is out of frame bounds - {event.details}"
                                        errors.append(SpatialIssue(
                                            line_number=event.start_line,
                                            severity="error",
                                            message=msg,
                                            code_snippet=self._get_code_snippet(code, event.start_line)
                                        ))
                            else:
                                full_report_buffer.write(f"\n[OK] {SceneClass.__name__} - Clean\n")

                    except Exception as e:
                        full_report_buffer.write(f"\n[CRASH] {SceneClass.__name__}: {e}\n")
                        errors.append(SpatialIssue(
                            line_number=0,
                            severity="error",
                            message=f"Scene {SceneClass.__name__} crashed: {e}",
                            code_snippet=""
                        ))

                raw_report = full_report_buffer.getvalue()

            finally:
                # Restore original methods
                self._Scene_class.play = original_play
                self._Scene_class.wait = original_wait

                # Clean up module
                if module_name and module_name in sys.modules:
                    del sys.modules[module_name]

        finally:
            # Clean up temp file
            try:
                os.unlink(temp_filename)
            except:
                pass

            # Clear linecache for temp file
            linecache.clearcache()

        return SpatialValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            raw_report=raw_report
        )

    def _get_code_snippet(self, code: str, line_number: int) -> str:
        """Get code snippet for a given line number."""
        if line_number <= 0:
            return ""
        lines = code.split('\n')
        if line_number <= len(lines):
            return lines[line_number - 1].strip()
        return ""


def format_spatial_issues(result: SpatialValidationResult) -> str:
    """
    Format spatial validation issues for display.

    Args:
        result: Validation result

    Returns:
        Formatted string with all issues
    """
    # If we have a raw report from the linter, use it
    if result.raw_report and result.has_issues:
        return result.raw_report

    if not result.has_issues:
        return "No spatial layout issues found"

    output = []

    if result.errors:
        output.append("ERRORS:")
        for error in result.errors:
            output.append(f"  Line {error.line_number}: {error.message}")
            if error.code_snippet:
                output.append(f"    Code: {error.code_snippet}")

    if result.warnings:
        # Separate minor (info) warnings from regular warnings
        minor_warnings = [w for w in result.warnings if w.severity == "info"]
        regular_warnings = [w for w in result.warnings if w.severity == "warning"]
        
        if regular_warnings:
            output.append("\nWARNINGS:")
            for warning in regular_warnings:
                output.append(f"  Line {warning.line_number}: {warning.message}")
                if warning.code_snippet:
                    output.append(f"    Code: {warning.code_snippet}")
        
        if minor_warnings:
            output.append("\nNOTES (minor issues):")
            for warning in minor_warnings:
                output.append(f"  Line {warning.line_number}: {warning.message}")
                if warning.code_snippet:
                    output.append(f"    Code: {warning.code_snippet}")

    return "\n".join(output)


# ==========================================
# STANDALONE ENTRY POINT
# ==========================================

def lint_manim_file(filename: str) -> str:
    """
    Runs the linter on the specified file.

    Args:
        filename: Path to the Manim Python file to lint

    Returns:
        A string containing the full report.
    """
    with open(filename, 'r') as f:
        code = f.read()

    validator = SpatialValidator()
    result = validator.validate(code)

    return result.raw_report


def lint_manim_code(code: str) -> str:
    """
    Runs the linter on the provided code string.

    Args:
        code: Manim Python code to lint

    Returns:
        A string containing the full report.
    """
    validator = SpatialValidator()
    result = validator.validate(code)

    return result.raw_report


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python spatial_validator.py <your_scene_file.py>")
    else:
        # Run and print the result
        log_output = lint_manim_file(sys.argv[1])
        print(log_output)

        # Exit code based on content
        if "issues)" in log_output or "[CRASH]" in log_output:
            sys.exit(1)
        sys.exit(0)
