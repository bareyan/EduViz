"""
Issue reporting and fix suggestion logic for spatial validation.
Translates raw events into actionable SpatialIssue objects.
"""

from typing import Any, List, Optional
from .models import SpatialIssue
from .constants import TEXT_TYPES


class IssueReporter:
    """
    Analyzes LintEvents and generates SpatialIssue objects with severity and suggested fixes.
    """

    def __init__(self, code: str):
        self.code = code
        self.lines = code.split('\n')

    def collect_issues(
        self, 
        events: List[Any], 
        errors: List[SpatialIssue], 
        warnings: List[SpatialIssue], 
        info: List[SpatialIssue]
    ) -> None:
        """Iterates through events and populates issue lists."""
        for ev in events:
            snippet = self._get_code_snippet(ev.start_line)
            frame_id = getattr(ev, 'frame_id', None)
            
            if ev.event_type == "overlap":
                self._handle_overlap_event(ev, snippet, errors, info, frame_id)
            elif ev.event_type == "occlusion":
                info.append(SpatialIssue(
                    ev.start_line, "info",
                    f"{ev.m1_name} occluded by {ev.m2_name} - {ev.details}",
                    snippet, suggested_fix="Consider .set_z_index(1) to bring to front",
                    frame_id=frame_id
                ))
            elif ev.event_type == "boundary":
                fix = self._get_boundary_fix(ev.details)
                msg = f"{ev.m1_name} out of bounds" + (" (PERSISTS)" if ev.persists_to_end else "") + f" - {ev.details}"
                errors.append(SpatialIssue(ev.start_line, "error", msg, snippet, suggested_fix=fix, frame_id=frame_id))
            elif ev.event_type == "font_size":
                warnings.append(SpatialIssue(
                    ev.start_line, "warning",
                    f"{ev.m1_name} font size too large - {ev.details}",
                    snippet, suggested_fix="Reduce with font_size=36 or .scale(0.7)",
                    frame_id=frame_id
                ))
            elif ev.event_type == "length":
                warnings.append(SpatialIssue(
                    ev.start_line, "warning",
                    f"{ev.m1_name} text too long - {ev.details}",
                    snippet, suggested_fix="Shorten text or split into multiple Text objects",
                    frame_id=frame_id
                ))

    def _handle_overlap_event(self, ev: Any, snippet: str, errors: List[SpatialIssue], info: List[SpatialIssue], frame_id: Optional[str]) -> None:
        """Determines if an overlap is an error (collision) or info (intentional label)."""
        if ev.m1_type in TEXT_TYPES and ev.m2_type in TEXT_TYPES:
            fix = "Separate with .shift(UP * 0.5) or use .next_to() positioning"
            errors.append(SpatialIssue(
                ev.start_line, "error",
                f"{ev.m1_name} overlaps {ev.m2_name} (text/text) - {ev.details}",
                snippet, suggested_fix=fix, frame_id=frame_id
            ))
        else:
            shape_types = ('Circle', 'Square', 'Rectangle')
            is_text_shape = (ev.m1_type in TEXT_TYPES and ev.m2_type in shape_types) or \
                             (ev.m2_type in TEXT_TYPES and ev.m1_type in shape_types)
            
            if is_text_shape:
                self._handle_text_shape_overlap(ev, snippet, errors, info, frame_id)
            else:
                info.append(SpatialIssue(
                    ev.start_line, "info",
                    f"{ev.m1_name} overlaps {ev.m2_name} - {ev.details}",
                    snippet, suggested_fix="Consider using .shift() or .move_to() to separate objects", frame_id=frame_id
                ))

    def _handle_text_shape_overlap(self, ev: Any, snippet: str, errors: List[SpatialIssue], info: List[SpatialIssue], frame_id: Optional[str]) -> None:
        """Special handling for text on shapes (potential labels)."""
        containment_ratio = 0.0
        if "[Containment: " in ev.details:
            try:
                con_str = ev.details.split("[Containment: ")[1].split("]")[0]
                containment_ratio = float(con_str.rstrip('%')) / 100.0
            except (IndexError, ValueError):
                pass
        
        if containment_ratio > 0.9:
            info.append(SpatialIssue(
                ev.start_line, "info",
                f"{ev.m1_name} overlaps {ev.m2_name} (label, {containment_ratio:.0%} contained) - {ev.details}",
                snippet, suggested_fix="If unintentional, use .shift() to reposition", frame_id=frame_id
            ))
        else:
            errors.append(SpatialIssue(
                ev.start_line, "error",
                f"{ev.m1_name} overlaps {ev.m2_name} (crosses boundary, {containment_ratio:.0%} contained) - {ev.details}",
                snippet, suggested_fix="Reposition text outside shape with .shift() or .next_to()", frame_id=frame_id
            ))

    def _get_boundary_fix(self, details: str) -> str:
        """Provides direction-specific fix suggestions for boundary violations."""
        if "Right" in details: return "Shift left: .shift(LEFT * 1) or .scale(0.8)"
        if "Left" in details: return "Shift right: .shift(RIGHT * 1) or .scale(0.8)"
        if "Top" in details or "Up" in details: return "Shift down: .shift(DOWN * 0.5) or .scale(0.8)"
        if "Bottom" in details or "Down" in details: return "Shift up: .shift(UP * 0.5) or .scale(0.8)"
        return "Reposition with .move_to(ORIGIN) or .scale(0.7)"

    def _get_code_snippet(self, ln: int) -> str:
        """Extracts a single line of code from the source."""
        return self.lines[ln - 1].strip() if 1 <= ln <= len(self.lines) else ""
