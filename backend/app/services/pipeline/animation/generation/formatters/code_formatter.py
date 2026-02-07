"""
Code Formatting Utilities

Handles class name generation, segment formatting, and other
code-related formatting tasks.

Responsibilities:
- Convert section IDs to valid Python class names
- Format narration segments for LLM context
- Clean and normalize code output
"""

import json
from typing import Dict, Any, Optional

# Language code to display name mapping
_SUPPORTED_LANGUAGES = {
    "en": "English",
    "fr": "French",
    "es": "Spanish",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "ar": "Arabic",
    "ru": "Russian",
    "ua": "Ukrainian",
    "hy": "Armenian",
}

_DEFAULT_SAFE_BOUNDS = {
    "x_min": -5.5,
    "x_max": 5.5,
    "y_min": -3.0,
    "y_max": 3.0,
}

_POSITION_TO_POINT = {
    "center": {"x": 0.0, "y": 0.0},
    "left": {"x": -4.0, "y": 0.0},
    "right": {"x": 4.0, "y": 0.0},
    "up": {"x": 0.0, "y": 2.5},
    "down": {"x": 0.0, "y": -2.5},
    "upper_left": {"x": -4.5, "y": 2.5},
    "upper_right": {"x": 4.5, "y": 2.5},
    "lower_left": {"x": -4.5, "y": -2.5},
    "lower_right": {"x": 4.5, "y": -2.5},
}

_ALLOWED_RELATIONS = {"above", "below", "left_of", "right_of"}
_ALLOWED_PLACEMENT_TYPES = {"absolute", "relative"}


class CodeFormatter:
    """Formats code and related strings for animation generation."""
    
    @staticmethod
    def derive_class_name(section: Dict[str, Any]) -> str:
        """Convert section ID to valid PEP8 class name.
        
        Args:
            section: Section dictionary with 'id' or 'index'
            
        Returns:
            Valid Python class name in PascalCase
            
        Example:
            >>> CodeFormatter.derive_class_name({"id": "intro-to-calculus"})
            'IntroToCalculus'
        """
        raw_id = section.get("id", f"section_{section.get('index', 0)}")
        normalized = raw_id.replace("-", "_").replace(" ", "_")
        return "".join(word.title() for word in normalized.split("_"))
    
    @staticmethod
    def summarize_segments(section: Dict[str, Any], max_chars: int = 60) -> str:
        """Format narration segments for LLM context.
        
        Args:
            section: Section dictionary with 'narration_segments'
            max_chars: Maximum characters per segment text
            
        Returns:
            Formatted string with timestamped segments
            
        Example:
            >>> formatter.summarize_segments({"narration_segments": [
            ...     {"start_time": 0.0, "text": "Welcome to calculus"},
            ...     {"start_time": 2.5, "text": "Today we'll learn derivatives"}
            ... ]})
            '- T+0.0s: Welcome to calculus\\n- T+2.5s: Today we\\'ll learn derivatives'
        """
        segs = section.get("narration_segments", [])
        lines = []
        running_time = 0.0

        for seg in segs:
            raw_start = seg.get("start_time")
            if isinstance(raw_start, (int, float)):
                start_time = float(raw_start)
            else:
                start_time = running_time

            text = str(seg.get("text", ""))[:max_chars]
            lines.append(f"- T+{start_time:.1f}s: {text}")

            est = seg.get("estimated_duration")
            if isinstance(est, (int, float)) and est > 0:
                running_time = max(running_time, start_time + float(est))

        return "\n".join(lines)

    @staticmethod
    def serialize_for_prompt(data: Any, default: str = "None provided") -> str:
        """Serialize optional structured data for prompt templates."""
        if data in (None, "", [], {}):
            return default
        if isinstance(data, str):
            return data
        try:
            return json.dumps(data, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            return str(data)
    
    @staticmethod
    def get_language_name(language_code: str) -> str:
        """Convert language code to display name.
        
        Args:
            language_code: ISO language code (e.g., 'en', 'fr', 'ru')
            
        Returns:
            Display name of the language (e.g., 'English', 'French', 'Russian')
            Defaults to 'English' for unknown codes
            
        Example:
            >>> CodeFormatter.get_language_name('ru')
            'Russian'
            >>> CodeFormatter.get_language_name('unknown')
            'English'
        """
        from ..constants import DEFAULT_LANGUAGE
        return _SUPPORTED_LANGUAGES.get(language_code, _SUPPORTED_LANGUAGES[DEFAULT_LANGUAGE])

    @staticmethod
    def serialize_choreography_plan(plan: Any, language_name: str = "English") -> str:
        """Serialize choreography plan (legacy or v2) for prompt injection."""
        normalized = CodeFormatter.normalize_choreography_plan(
            plan,
            language_name=language_name,
        )
        return json.dumps(normalized, ensure_ascii=False, indent=2)

    @staticmethod
    def normalize_choreography_plan(plan: Any, language_name: str = "English") -> Dict[str, Any]:
        """Normalize legacy or partial plans into ChoreographyPlan v2 shape."""
        parsed: Any = plan
        if isinstance(plan, str):
            try:
                parsed = json.loads(plan)
            except (TypeError, ValueError):
                return CodeFormatter._empty_v2_plan(language_name=language_name)

        if isinstance(parsed, dict) and str(parsed.get("version", "")).strip() == "2.0":
            return CodeFormatter._normalize_v2_plan(parsed, language_name=language_name)
        if isinstance(parsed, dict):
            return CodeFormatter._adapt_legacy_plan(parsed, language_name=language_name)
        return CodeFormatter._empty_v2_plan(language_name=language_name)

    @staticmethod
    def _empty_v2_plan(language_name: str) -> Dict[str, Any]:
        return {
            "version": "2.0",
            "scene": {
                "mode": "2D",
                "camera": None,
                "safe_bounds": dict(_DEFAULT_SAFE_BOUNDS),
            },
            "objects": [],
            "timeline": [],
            "constraints": {
                "language": language_name,
                "max_visible_objects": 10,
                "forbidden_constants": ["TOP", "BOTTOM"],
            },
            "notes": [],
        }

    @staticmethod
    def _normalize_v2_plan(plan: Dict[str, Any], language_name: str) -> Dict[str, Any]:
        normalized = CodeFormatter._empty_v2_plan(language_name=language_name)
        normalized["version"] = "2.0"

        scene = plan.get("scene")
        if isinstance(scene, dict):
            mode = str(scene.get("mode", "2D")).upper()
            normalized["scene"]["mode"] = "3D" if mode == "3D" else "2D"
            normalized["scene"]["camera"] = scene.get("camera")
            safe_bounds = CodeFormatter._normalize_safe_bounds(scene.get("safe_bounds"))
            normalized["scene"]["safe_bounds"] = safe_bounds

        objects = plan.get("objects")
        if isinstance(objects, list):
            normalized["objects"] = [
                CodeFormatter._normalize_v2_object(obj, idx)
                for idx, obj in enumerate(objects)
                if isinstance(obj, dict)
            ]

        timeline = plan.get("timeline")
        if isinstance(timeline, list):
            normalized["timeline"] = [
                CodeFormatter._normalize_v2_timeline_segment(seg, idx)
                for idx, seg in enumerate(timeline)
                if isinstance(seg, dict)
            ]

        constraints = plan.get("constraints")
        if isinstance(constraints, dict):
            forbidden_raw = constraints.get("forbidden_constants")
            if isinstance(forbidden_raw, list):
                forbidden_constants = [str(item) for item in forbidden_raw if isinstance(item, (str, int, float))]
            else:
                forbidden_constants = ["TOP", "BOTTOM"]
            normalized["constraints"] = {
                "language": str(constraints.get("language") or language_name),
                "max_visible_objects": CodeFormatter._coerce_int(constraints.get("max_visible_objects"), default=10),
                "forbidden_constants": forbidden_constants or ["TOP", "BOTTOM"],
            }

        notes = plan.get("notes")
        if isinstance(notes, list):
            normalized["notes"] = [str(note) for note in notes if isinstance(note, (str, int, float))]

        return normalized

    @staticmethod
    def _adapt_legacy_plan(plan: Dict[str, Any], language_name: str) -> Dict[str, Any]:
        normalized = CodeFormatter._empty_v2_plan(language_name=language_name)

        scene_type = str(plan.get("scene_type", "2D")).upper()
        normalized["scene"]["mode"] = "3D" if scene_type == "3D" else "2D"
        camera = plan.get("camera")
        normalized["scene"]["camera"] = camera if isinstance(camera, dict) else None
        normalized["scene"]["safe_bounds"] = CodeFormatter._legacy_safe_bounds(plan.get("screen_bounds"))

        notes: list[str] = []
        objects = plan.get("objects")
        if isinstance(objects, list):
            adapted_objects = []
            for idx, obj in enumerate(objects):
                if not isinstance(obj, dict):
                    continue
                adapted_objects.append(CodeFormatter._adapt_legacy_object(obj, idx))
                note = obj.get("notes")
                if isinstance(note, str) and note.strip():
                    notes.append(note.strip())
            normalized["objects"] = adapted_objects

        segments = plan.get("segments")
        if isinstance(segments, list):
            adapted_timeline = []
            for idx, segment in enumerate(segments):
                if not isinstance(segment, dict):
                    continue
                adapted_timeline.append(CodeFormatter._adapt_legacy_segment(segment, idx))
                for step in segment.get("steps", []) if isinstance(segment.get("steps"), list) else []:
                    if isinstance(step, dict):
                        step_note = step.get("notes")
                        if isinstance(step_note, str) and step_note.strip():
                            notes.append(step_note.strip())
            normalized["timeline"] = adapted_timeline

        normalized["notes"] = notes
        return normalized

    @staticmethod
    def _normalize_v2_object(obj: Dict[str, Any], index: int) -> Dict[str, Any]:
        object_id = str(obj.get("id") or f"object_{index}")
        kind = str(obj.get("kind") or "Text")
        content = obj.get("content") if isinstance(obj.get("content"), dict) else {}
        placement = obj.get("placement") if isinstance(obj.get("placement"), dict) else {}
        lifecycle = obj.get("lifecycle") if isinstance(obj.get("lifecycle"), dict) else {}

        placement_type = str(placement.get("type") or "absolute").lower()
        if placement_type not in _ALLOWED_PLACEMENT_TYPES:
            placement_type = "absolute"

        absolute = placement.get("absolute") if isinstance(placement.get("absolute"), dict) else None
        relative = placement.get("relative") if isinstance(placement.get("relative"), dict) else None
        if placement_type == "absolute" and absolute is None:
            absolute = {"x": 0.0, "y": 0.0}
        if placement_type == "relative" and relative is None:
            placement_type = "absolute"
            absolute = {"x": 0.0, "y": 0.0}

        return {
            "id": object_id,
            "kind": kind,
            "content": {
                "text": CodeFormatter._nullable_text(content.get("text")),
                "latex": CodeFormatter._nullable_text(content.get("latex")),
                "asset_path": CodeFormatter._nullable_text(content.get("asset_path")),
            },
            "placement": {
                "type": placement_type,
                "absolute": CodeFormatter._normalize_absolute_position(absolute) if placement_type == "absolute" else None,
                "relative": CodeFormatter._normalize_relative_position(relative) if placement_type == "relative" else None,
            },
            "lifecycle": {
                "appear_at": CodeFormatter._quantize_time(lifecycle.get("appear_at")),
                "remove_at": CodeFormatter._quantize_time(lifecycle.get("remove_at")),
            },
        }

    @staticmethod
    def _normalize_v2_timeline_segment(segment: Dict[str, Any], index: int) -> Dict[str, Any]:
        actions = segment.get("actions")
        normalized_actions = []
        if isinstance(actions, list):
            normalized_actions = [
                CodeFormatter._normalize_v2_action(action)
                for action in actions
                if isinstance(action, dict)
            ]
        return {
            "segment_index": int(segment.get("segment_index", index)),
            "start_at": CodeFormatter._quantize_time(segment.get("start_at")),
            "end_at": CodeFormatter._quantize_time(segment.get("end_at")),
            "actions": normalized_actions,
        }

    @staticmethod
    def _normalize_v2_action(action: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "at": CodeFormatter._quantize_time(action.get("at")),
            "op": str(action.get("op") or "Wait"),
            "target": str(action.get("target") or ""),
            "source": CodeFormatter._nullable_text(action.get("source")),
            "run_time": CodeFormatter._quantize_time(action.get("run_time")),
        }

    @staticmethod
    def _adapt_legacy_object(obj: Dict[str, Any], index: int) -> Dict[str, Any]:
        object_id = str(obj.get("id") or f"object_{index}")
        relative_to_raw = obj.get("relative_to")
        relative_to = CodeFormatter._nullable_text(relative_to_raw)
        relation_raw = CodeFormatter._nullable_text(obj.get("relation"))
        relation = relation_raw if relation_raw in _ALLOWED_RELATIONS else None
        spacing = CodeFormatter._coerce_float(obj.get("spacing"), default=0.5)

        if relative_to and relation:
            placement = {
                "type": "relative",
                "absolute": None,
                "relative": {
                    "relative_to": relative_to,
                    "relation": relation,
                    "spacing": spacing,
                },
            }
        else:
            placement = {
                "type": "absolute",
                "absolute": CodeFormatter._position_to_point(obj.get("position")),
                "relative": None,
            }

        return {
            "id": object_id,
            "kind": str(obj.get("type") or "Text"),
            "content": {
                "text": CodeFormatter._nullable_text(obj.get("text")),
                "latex": CodeFormatter._nullable_text(obj.get("latex")),
                "asset_path": CodeFormatter._nullable_text(obj.get("asset_path")),
            },
            "placement": placement,
            "lifecycle": {
                "appear_at": CodeFormatter._quantize_time(obj.get("appears_at")),
                "remove_at": CodeFormatter._quantize_time(obj.get("removed_at")),
            },
        }

    @staticmethod
    def _adapt_legacy_segment(segment: Dict[str, Any], index: int) -> Dict[str, Any]:
        steps = segment.get("steps")
        actions = []
        if isinstance(steps, list):
            for step in steps:
                if not isinstance(step, dict):
                    continue
                actions.append(
                    {
                        "at": CodeFormatter._quantize_time(step.get("time")),
                        "op": str(step.get("action") or "Wait"),
                        "target": str(step.get("target") or ""),
                        "source": CodeFormatter._nullable_text(step.get("source")),
                        "run_time": CodeFormatter._quantize_time(step.get("duration")),
                    }
                )
        return {
            "segment_index": int(segment.get("segment_index", index)),
            "start_at": CodeFormatter._quantize_time(segment.get("start_time")),
            "end_at": CodeFormatter._quantize_time(segment.get("end_time")),
            "actions": actions,
        }

    @staticmethod
    def _legacy_safe_bounds(raw_bounds: Any) -> Dict[str, float]:
        if not isinstance(raw_bounds, dict):
            return dict(_DEFAULT_SAFE_BOUNDS)
        x_bounds = raw_bounds.get("x")
        y_bounds = raw_bounds.get("y")
        if (
            isinstance(x_bounds, list)
            and len(x_bounds) == 2
            and isinstance(y_bounds, list)
            and len(y_bounds) == 2
        ):
            return {
                "x_min": CodeFormatter._coerce_float(x_bounds[0], default=_DEFAULT_SAFE_BOUNDS["x_min"]),
                "x_max": CodeFormatter._coerce_float(x_bounds[1], default=_DEFAULT_SAFE_BOUNDS["x_max"]),
                "y_min": CodeFormatter._coerce_float(y_bounds[0], default=_DEFAULT_SAFE_BOUNDS["y_min"]),
                "y_max": CodeFormatter._coerce_float(y_bounds[1], default=_DEFAULT_SAFE_BOUNDS["y_max"]),
            }
        return dict(_DEFAULT_SAFE_BOUNDS)

    @staticmethod
    def _normalize_safe_bounds(raw_bounds: Any) -> Dict[str, float]:
        if not isinstance(raw_bounds, dict):
            return dict(_DEFAULT_SAFE_BOUNDS)
        return {
            "x_min": CodeFormatter._coerce_float(raw_bounds.get("x_min"), default=_DEFAULT_SAFE_BOUNDS["x_min"]),
            "x_max": CodeFormatter._coerce_float(raw_bounds.get("x_max"), default=_DEFAULT_SAFE_BOUNDS["x_max"]),
            "y_min": CodeFormatter._coerce_float(raw_bounds.get("y_min"), default=_DEFAULT_SAFE_BOUNDS["y_min"]),
            "y_max": CodeFormatter._coerce_float(raw_bounds.get("y_max"), default=_DEFAULT_SAFE_BOUNDS["y_max"]),
        }

    @staticmethod
    def _position_to_point(position: Any) -> Dict[str, float]:
        if isinstance(position, str):
            normalized = position.strip().lower()
            if normalized in _POSITION_TO_POINT:
                return dict(_POSITION_TO_POINT[normalized])
            if "," in normalized:
                x_str, y_str = normalized.split(",", 1)
                return {
                    "x": CodeFormatter._coerce_float(x_str, default=0.0),
                    "y": CodeFormatter._coerce_float(y_str, default=0.0),
                }
        if isinstance(position, dict):
            return CodeFormatter._normalize_absolute_position(position)
        return {"x": 0.0, "y": 0.0}

    @staticmethod
    def _normalize_absolute_position(position: Optional[Dict[str, Any]]) -> Dict[str, float]:
        if not isinstance(position, dict):
            return {"x": 0.0, "y": 0.0}
        return {
            "x": CodeFormatter._coerce_float(position.get("x"), default=0.0),
            "y": CodeFormatter._coerce_float(position.get("y"), default=0.0),
        }

    @staticmethod
    def _normalize_relative_position(position: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not isinstance(position, dict):
            return {"relative_to": "", "relation": "below", "spacing": 0.5}
        relation_raw = str(position.get("relation") or "").strip().lower()
        relation = relation_raw if relation_raw in _ALLOWED_RELATIONS else "below"
        return {
            "relative_to": str(position.get("relative_to") or ""),
            "relation": relation,
            "spacing": CodeFormatter._coerce_float(position.get("spacing"), default=0.5),
        }

    @staticmethod
    def _coerce_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _coerce_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _quantize_time(value: Any) -> float:
        return round(CodeFormatter._coerce_float(value), 3)

    @staticmethod
    def _nullable_text(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped or stripped.lower() == "null":
                return None
            return stripped
        return str(value)

    @staticmethod
    def _string_or_none(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped if stripped else None
        return str(value)
