"""
Main spatial validation logic for Manim code.
"""

import itertools
import linecache
import logging
import os
import tempfile
import traceback
import time
from typing import Any, Dict, List, Optional

from .constants import (
    MAX_FONT_SIZE,
    MAX_TEXT_CHARS,
    OCCLUSION_MIN_AREA,
    OVERLAP_MARGIN,
    TEXT_TYPES,
)
from .models import SpatialIssue, SpatialValidationResult, FrameCapture
from .geometry import get_overlap_metrics, get_z_index, get_boundary_violation
from .utils import (
    get_atomic_mobjects,
    get_user_code_context,
    is_overlapping,
    is_connector_type_name,
)
from .events import LintEvent, SceneTracker
from .engine import ManimEngine
from .reporters import IssueReporter

LOGGER = logging.getLogger(__name__)


class SpatialValidator:
    """
    Orchestrates spatial validation of Manim objects by executing code through ManimEngine.
    Separates environment management (engine.py) and issue reporting (reporters.py).
    """

    def __init__(self, linter_path: Optional[str] = None) -> None:
        self.linter_path = linter_path or os.path.abspath(__file__)
        self.engine = ManimEngine(self.linter_path)
        self.trackers: Dict[Any, SceneTracker] = {}
        self.frame_captures: Dict[float, FrameCapture] = {}  # timestamp -> FrameCapture (dedup)

    def validate(self, code: str) -> SpatialValidationResult:
        """Entry point for spatial validation."""
        start_total = time.perf_counter()
        start_engine = time.perf_counter()
        try:
            self.engine.initialize()
        except ImportError as e:
            return SpatialValidationResult(valid=True, raw_report=f"Manim unavailable: {e}")
        engine_initialize_ms = (time.perf_counter() - start_engine) * 1000.0

        self.trackers.clear()
        self.frame_captures.clear()
        self.engine.apply_fast_config()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(code)
            temp_filename = f.name
            
        try:
            result, timings = self._run_validation_cycle(temp_filename, code)
            total_duration_ms = (time.perf_counter() - start_total) * 1000.0
            LOGGER.info(
                "Spatial validation timings",
                extra={
                    "engine_initialize_ms": round(engine_initialize_ms, 2),
                    "run_scenes_ms": round(timings.get("run_scenes_ms", 0.0), 2),
                    "issue_collection_ms": round(timings.get("issue_collection_ms", 0.0), 2),
                    "frame_capture_count": timings.get("frame_capture_count", 0),
                    "spatial_total_ms": round(total_duration_ms, 2),
                },
            )
            return result
        finally:
            self._cleanup_temp(temp_filename)

    def _run_validation_cycle(self, temp_filename: str, code: str) -> tuple[SpatialValidationResult, Dict[str, Any]]:
        """Runs the validation engine and collects issues using IssueReporter."""
        errors, warnings, info, reports = [], [], [], []
        reporter = IssueReporter(code)
        run_scenes_ms = 0.0
        issue_collection_ms = 0.0
        
        with self.engine.patched_runtime(on_play_callback=self._check_scene_state):
            try:
                start_run = time.perf_counter()
                scenes = self.engine.run_scenes(temp_filename)
                run_scenes_ms = (time.perf_counter() - start_run) * 1000.0
                start_collect = time.perf_counter()
                for scene in scenes:
                    if scene in self.trackers:
                        _, last_line = get_user_code_context(self.linter_path)
                        
                        # Collect issues from tracker history + active events
                        tracker = self.trackers[scene]
                        all_events = tracker.history + list(tracker.active_events.values())
                        reporter.collect_issues(all_events, errors, warnings, info)
                        
                        tracker.close_all(last_line)
                        report_str = tracker.generate_report_string(scene.__class__.__name__)
                        if report_str:
                            reports.append(report_str)
                issue_collection_ms = (time.perf_counter() - start_collect) * 1000.0
            except Exception as e:
                tb = traceback.format_exc()
                errors.append(SpatialIssue(0, "error", f"Validation crashed: {e}\n{tb}", ""))

        result = SpatialValidationResult(
            valid=not errors,
            errors=errors,
            warnings=warnings,
            info=info,
            raw_report="\n".join(reports),
            frame_captures=list(self.frame_captures.values())
        )
        timings = {
            "run_scenes_ms": run_scenes_ms,
            "issue_collection_ms": issue_collection_ms,
            "frame_capture_count": len(self.frame_captures),
        }
        return result, timings

    def _check_scene_state(self, scene: Any) -> None:
        """Detection logic: Analyzes current scene state for spatial issues."""
        if scene not in self.trackers:
            self.trackers[scene] = SceneTracker()
            self.trackers[scene]._scene = scene  # Store for frame capture
        tracker = self.trackers[scene]

        current_time = scene.renderer.time
        _, triggering_line = get_user_code_context(self.linter_path)

        atoms = []
        for m in scene.mobjects:
            atoms.extend(get_atomic_mobjects(m, self.engine.mobject_classes))

        active_ids = set()

        # 1. Overlaps & Occlusions
        for m1, m2 in itertools.combinations(atoms, 2):
            if is_connector_type_name(m1.__class__.__name__) or is_connector_type_name(m2.__class__.__name__):
                continue
            if is_overlapping(m1, m2, OVERLAP_MARGIN):
                pair_id = f"OVLP_{id(m1)}_{id(m2)}"
                active_ids.add(pair_id)

                if pair_id not in tracker.active_events:
                    line = self._get_line(m1, triggering_line)
                    event = LintEvent(m1, m2, "overlap", current_time, "user_code", line)
                    # Capture frame for new event (deduplicated by timestamp)
                    frame_id = self._capture_frame_if_needed(scene, current_time, pair_id)
                    event.frame_id = frame_id
                    tracker.active_events[pair_id] = event
                tracker.active_events[pair_id].update(current_time, m1, m2)

                area, _, _ = get_overlap_metrics(m1, m2)
                if area >= OCCLUSION_MIN_AREA:
                    self._detect_occlusions(m1, m2, tracker, current_time, triggering_line, active_ids)

        # 2. Quality heuristics (fonts, text length)
        self._detect_quality_heuristics(atoms, tracker, current_time, triggering_line, active_ids)

        # 3. Boundary checks
        for m in atoms:
            if get_boundary_violation(m, self.engine.config):
                b_id = f"BND_{id(m)}"
                active_ids.add(b_id)
                if b_id not in tracker.active_events:
                    line = self._get_line(m, triggering_line)
                    event = LintEvent(m, None, "boundary", current_time, "user_code", line)
                    frame_id = self._capture_frame_if_needed(scene, current_time, b_id)
                    event.frame_id = frame_id
                    tracker.active_events[b_id] = event
                tracker.active_events[b_id].update(current_time, m, manim_config=self.engine.config)

        # Cleanup finished events
        for eid in list(tracker.active_events.keys()):
            if eid not in active_ids:
                event = tracker.active_events.pop(eid)
                event.finish(triggering_line, is_scene_end=False)
                tracker.history.append(event)

    def _get_line(self, mobj: Any, fallback: int) -> int:
        """DRY helper to get creation line for a mobject."""
        return self.engine.creation_lines.get(id(mobj), fallback)

    def _detect_occlusions(self, m1: Any, m2: Any, tracker: SceneTracker, current_time: float, line: int, active_ids: set) -> None:
        """Identifies text objects occluded by other objects."""
        z1, z2 = get_z_index(m1), get_z_index(m2)
        for target, anchor, tz, az in [(m1, m2, z1, z2), (m2, m1, z2, z1)]:
            if target.__class__.__name__ in TEXT_TYPES and tz < az:
                oid = f"OCC_{id(target)}_{id(anchor)}"
                active_ids.add(oid)
                if oid not in tracker.active_events:
                    t_line = self._get_line(target, line)
                    event = LintEvent(target, anchor, "occlusion", current_time, "user_code", t_line)
                    frame_id = self._capture_frame_if_needed(tracker._scene if hasattr(tracker, '_scene') else None, current_time, oid)
                    event.frame_id = frame_id
                    tracker.active_events[oid] = event
                tracker.active_events[oid].update(current_time, target, anchor, z_info=f"z_index {tz:.2f} behind {az:.2f}")

    def _detect_quality_heuristics(self, atoms: List[Any], tracker: SceneTracker, current_time: float, line: int, active_ids: set) -> None:
        """Identifies excessive font sizes or text lengths."""
        for m in atoms:
            m_type = m.__class__.__name__
            if m_type not in TEXT_TYPES: continue
            
            # Font size
            if getattr(m, "font_size", 48) > MAX_FONT_SIZE:
                q_id = f"FNT_{id(m)}"
                active_ids.add(q_id)
                if q_id not in tracker.active_events:
                    m_line = self._get_line(m, line)
                    event = LintEvent(m, None, "font_size", current_time, "user_code", m_line)
                    frame_id = self._capture_frame_if_needed(tracker._scene if hasattr(tracker, '_scene') else None, current_time, q_id)
                    event.frame_id = frame_id
                    tracker.active_events[q_id] = event
                tracker.active_events[q_id].update(current_time, m)
                
            # Text length
            text_val = getattr(m, "text", getattr(m, "tex_string", ""))
            if len(text_val) > MAX_TEXT_CHARS:
                l_id = f"LEN_{id(m)}"
                active_ids.add(l_id)
                if l_id not in tracker.active_events:
                    m_line = self._get_line(m, line)
                    event = LintEvent(m, None, "length", current_time, "user_code", m_line)
                    frame_id = self._capture_frame_if_needed(tracker._scene if hasattr(tracker, '_scene') else None, current_time, l_id)
                    event.frame_id = frame_id
                    tracker.active_events[l_id] = event
                tracker.active_events[l_id].update(current_time, m)

    def _cleanup_temp(self, path: str) -> None:
        try: os.unlink(path)
        except Exception: pass
        linecache.clearcache()

    def _capture_frame_if_needed(self, scene: Any, timestamp: float, event_id: str) -> Optional[str]:
        """
        Capture frame at this timestamp if not already captured (deduplication).
        Returns frame_id for linking issues to screenshots.
        """
        if scene is None:
            return None
            
        # Round timestamp to avoid floating point comparison issues
        timestamp_key = round(timestamp, 3)
        
        # Already captured at this moment? Reuse it
        if timestamp_key in self.frame_captures:
            self.frame_captures[timestamp_key].event_ids.append(event_id)
            return self.frame_captures[timestamp_key].screenshot_path
        
        # Capture new frame
        try:
            screenshot_path = os.path.join(
                tempfile.gettempdir(),
                f"spatial_frame_{timestamp_key:.3f}_{id(scene)}.png"
            )
            
            # Get current frame and save
            frame = scene.renderer.get_frame()
            if frame is not None:
                from PIL import Image
                import numpy as np
                # Convert frame to image and save
                img = Image.fromarray(np.uint8(frame))
                img.save(screenshot_path)
                
                # Store in cache
                frame_capture = FrameCapture(
                    screenshot_path=screenshot_path,
                    timestamp=timestamp_key,
                    event_ids=[event_id]
                )
                self.frame_captures[timestamp_key] = frame_capture
                LOGGER.debug(f"Captured frame at t={timestamp_key}s: {screenshot_path}")
                return screenshot_path
        except Exception as e:
            LOGGER.warning(f"Failed to capture frame at t={timestamp}: {e}")
            
        return None
