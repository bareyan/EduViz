"""
Event tracking system for spatial validation during rendering.
"""

import linecache
from io import StringIO
from typing import Any, Dict, List, Optional

from .constants import PLOT_TYPES, TEXT_TYPES
from .geometry import get_overlap_metrics, get_boundary_violation


class LintEvent:
    """Represents a single spatial issue event."""

    def __init__(
        self,
        m1: Any,
        m2: Optional[Any],
        event_type: str,
        start_time: float,
        filename: str,
        start_line: int,
        total_duration: Optional[float] = None,
    ) -> None:
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
        self.total_duration = total_duration

        # Context
        self.filename = filename
        self.start_line = start_line
        self.end_line = start_line
        
        self.persists_to_end = False

        # Metrics
        self.max_severity = 0.0
        self.details = "Unknown"

    def _clean_name(self, m: Optional[Any]) -> str:
        if not m:
            return ""
        obj_type = m.__class__.__name__
        content = getattr(m, "tex_string", getattr(m, "text", ""))
        if content:
            content = content.replace("\n", " ").strip()[:30]
            return f'{obj_type}("{content}")'
        return obj_type

    def update(
        self,
        current_time: float,
        m1: Any,
        m2: Optional[Any] = None,
        manim_config: Optional[Any] = None,
        z_info: Optional[str] = None,
    ) -> None:
        self.end_time = current_time

        if self.event_type == "overlap":
            area, _, desc = get_overlap_metrics(m1, m2)
            if area > self.max_severity:
                self.max_severity = area
                self.details = f"{desc} [Max Area: {area:.2f}]"

        elif self.event_type == "occlusion":
            area, _, desc = get_overlap_metrics(m1, m2)
            if area > self.max_severity:
                self.max_severity = area
                z_detail = f" ({z_info})" if z_info else ""
                self.details = f"{desc} [Max Area: {area:.2f}]{z_detail}"

        elif self.event_type == "contrast":
            if z_info:
                self.details = z_info

        elif self.event_type == "boundary" and manim_config:
            result = get_boundary_violation(m1, manim_config)
            if result:
                dist, desc = result
                if dist > self.max_severity:
                    self.max_severity = dist
                    self.details = desc

    def finish(self, end_line: int, is_scene_end: bool = False) -> None:
        self.end_line = end_line
        self.persists_to_end = is_scene_end

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


class SceneTracker:
    """Tracks spatial issues during scene rendering."""

    def __init__(self) -> None:
        self.active_events: Dict[str, LintEvent] = {}
        self.history: List[LintEvent] = []

    def close_all(self, final_line: int, is_scene_end: bool = True) -> None:
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
            dur = ev.duration
            if ev.persists_to_end:
                time_str = f"{ev.start_time:.2f}s -> END OF VIDEO"
                dur_str = "(Persists to end of video)"
            else:
                time_str = f"{ev.start_time:.2f}s -> {ev.end_time:.2f}s"
                dur_str = "(Instant)" if dur < 0.05 else f"(Duration: {dur:.2f}s)"

            output.write(f"\n{i}. [{time_str}] {dur_str}\n")

            # Type Specific Message
            if ev.event_type == "overlap":
                m1_is_plot = ev.m1_type in PLOT_TYPES
                m2_is_plot = ev.m2_type in PLOT_TYPES
                m1_is_text = ev.m1_type in TEXT_TYPES
                m2_is_text = ev.m2_type in TEXT_TYPES

                if m1_is_text and m2_is_text:
                    output.write(f"   [OVERLAP - TEXT/TEXT] '{ev.m1_name}' intersects '{ev.m2_name}'\n")
                elif (m1_is_plot and m2_is_text) or (m1_is_text and m2_is_plot):
                    output.write(f"   [OVERLAP - PLOT/TEXT] '{ev.m1_name}' intersects '{ev.m2_name}'\n")
                    output.write(f"   Note: Plot and text overlap - consider repositioning for better readability\n")
                else:
                    output.write(f"   [OVERLAP] '{ev.m1_name}' intersects '{ev.m2_name}'\n")
            elif ev.event_type == "occlusion":
                output.write(f"   [OCCLUSION] '{ev.m1_name}' may be hidden behind '{ev.m2_name}'\n")
            elif ev.event_type == "contrast":
                output.write(f"   [LOW CONTRAST] '{ev.m1_name}' may be hard to read against background\n")
            elif ev.event_type == "font_size":
                output.write(f"   [LARGE FONT] '{ev.m1_name}' has excessive font size\n")
            elif ev.event_type == "length":
                output.write(f"   [LONG TEXT] '{ev.m1_name}' content is very long for a single line\n")
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
