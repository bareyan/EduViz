"""
Highlight box detection and cropping utilities.
"""

from pathlib import Path
from typing import Any, List, Optional, Set, Tuple

from .events import LintEvent
from .geometry import get_overlap_metrics
from .models import FrameCapture
from .utils import get_atomic_mobjects, is_connector_type_name


class HighlightBoxChecker:
    """Detect highlight boxes, verify overlap, and capture cropped evidence."""

    def __init__(self, engine: Any) -> None:
        self.engine = engine
        self._seen: Set[Tuple[int, float]] = set()

    def reset(self) -> None:
        self._seen.clear()

    def detect(
        self,
        scene: Any,
        play_args: tuple,
        triggering_line: int,
    ) -> tuple[List[LintEvent], List[FrameCapture]]:
        """Return highlight events and crop captures for boxes in play_args."""
        if not play_args:
            return [], []

        current_time = getattr(scene.renderer, "time", 0.0)
        timestamp_key = round(float(current_time), 2) if current_time is not None else 0.0

        atoms: List[Any] = []
        try:
            for m in scene.mobjects:
                atoms.extend(get_atomic_mobjects(m, self.engine.mobject_classes))
        except Exception:
            atoms = list(getattr(scene, "mobjects", []) or [])

        non_connector_atoms = [
            m for m in atoms if not is_connector_type_name(m.__class__.__name__)
        ]

        animations: List[Any] = []
        for arg in play_args:
            animations.extend(list(self._iter_animations(arg)))

        candidate_boxes: List[Any] = []
        for anim in animations:
            mobj = getattr(anim, "mobject", None)
            if mobj is not None and self.is_highlight_box(mobj):
                candidate_boxes.append(mobj)

        if not candidate_boxes:
            return [], []

        events: List[LintEvent] = []
        captures: List[FrameCapture] = []
        capture_map: dict[Tuple[int, float], FrameCapture] = {}

        for box in candidate_boxes:
            key = (id(box), timestamp_key)
            if key in self._seen:
                continue
            self._seen.add(key)

            targets: List[Any] = []
            for other in non_connector_atoms:
                if other is box:
                    continue
                area, _, _ = get_overlap_metrics(box, other)
                if area > 0.0:
                    targets.append(other)

            frame_id = None
            capture = capture_map.get(key)
            if not capture:
                frame_id = self.crop_highlight_box(scene, box, self.engine.config)
                if frame_id:
                    capture = FrameCapture(
                        screenshot_path=frame_id,
                        timestamp=timestamp_key,
                        event_ids=[f"HLB_{id(box)}_{timestamp_key}"],
                    )
                    capture_map[key] = capture
                    captures.append(capture)
            else:
                frame_id = capture.screenshot_path

            if targets:
                for target in targets:
                    ev = LintEvent(box, target, "highlight_target", current_time, "user_code", triggering_line)
                    ev.details = self._describe_target(target)
                    ev.frame_id = frame_id
                    ev.finish(triggering_line, is_scene_end=False)
                    events.append(ev)
            else:
                ev = LintEvent(box, None, "highlight_miss", current_time, "user_code", triggering_line)
                ev.details = "Highlight box does not overlap any visible object"
                ev.frame_id = frame_id
                ev.finish(triggering_line, is_scene_end=False)
                events.append(ev)

        return events, captures

    def is_highlight_box(self, mobj: Any) -> bool:
        """Heuristic for detecting highlight rectangles."""
        name = mobj.__class__.__name__
        if name == "SurroundingRectangle":
            return True
        if name != "Rectangle":
            return False
        stroke_width = getattr(mobj, "stroke_width", 1)
        fill_opacity = getattr(mobj, "fill_opacity", 0.0)
        return stroke_width >= 3 and fill_opacity <= 0.2

    def crop_highlight_box(
        self,
        scene: Any,
        box: Any,
        config: Any,
        output_dir: Optional[Path] = None,
    ) -> Optional[str]:
        """Crop the highlight box region from the current frame."""
        if scene is None or config is None:
            return None
        try:
            frame = scene.renderer.get_frame()
            if frame is None:
                return None

            frame_h, frame_w = frame.shape[0], frame.shape[1]
            frame_width = float(getattr(config, "frame_width", 0.0)) or 0.0
            frame_height = float(getattr(config, "frame_height", 0.0)) or 0.0
            if frame_width <= 0.0 or frame_height <= 0.0:
                return None

            c = box.get_center()
            half_w = float(getattr(box, "width", 0.0)) / 2.0
            half_h = float(getattr(box, "height", 0.0)) / 2.0

            left = c[0] - half_w
            right = c[0] + half_w
            top = c[1] + half_h
            bottom = c[1] - half_h

            def _to_px_x(x: float) -> int:
                return int(round((x + frame_width / 2.0) / frame_width * frame_w))

            def _to_px_y(y: float) -> int:
                return int(round((frame_height / 2.0 - y) / frame_height * frame_h))

            x0 = max(0, min(frame_w - 1, _to_px_x(left)))
            x1 = max(0, min(frame_w, _to_px_x(right)))
            y0 = max(0, min(frame_h - 1, _to_px_y(top)))
            y1 = max(0, min(frame_h, _to_px_y(bottom)))

            if x1 <= x0 or y1 <= y0:
                return None

            crop = frame[y0:y1, x0:x1]
            if crop.size == 0:
                return None

            from PIL import Image
            import numpy as np

            img = Image.fromarray(np.uint8(crop))
            if output_dir is None:
                output_dir = Path("backend/outputs").resolve()
            output_dir.mkdir(parents=True, exist_ok=True)
            filename = output_dir / f"highlight_crop_{id(box)}_{int(getattr(scene.renderer, 'time', 0.0) * 1000)}.png"
            img.save(filename)
            return str(filename)
        except Exception:
            return None

    def _describe_target(self, target: Any) -> str:
        """Return a short description of a target."""
        content = getattr(target, "tex_string", None) or getattr(target, "text", None) or ""
        content = content.replace("\n", " ").strip()
        if len(content) > 30:
            content = content[:30] + "..."
        if content:
            return f'{target.__class__.__name__}("{content}")'
        return target.__class__.__name__

    def _iter_animations(self, anim: Any):
        """Yield individual animations from nested groups."""
        if anim is None:
            return
        if hasattr(anim, "animations"):
            try:
                for sub in anim.animations:
                    yield from self._iter_animations(sub)
                return
            except Exception:
                pass
        yield anim
