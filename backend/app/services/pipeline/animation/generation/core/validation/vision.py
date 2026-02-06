"""
Vision Validator

Post-render visual verification using a multimodal LLM over selected frames.

Architecture role: VERIFICATION ONLY.
    The spatial validator catches most issues deterministically during
    runtime validation. Vision QC's job is to:
    1. Visually verify uncertain spatial issues (needs_verification=True).
    2. Confirm or reject them based on actual rendered frames.
    3. Return confirmed issues for the Refiner to fix.

    It does NOT auto-fix anything. It does NOT replace spatial validation.
"""

import asyncio
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List, Optional

from app.core import get_logger
from app.services.infrastructure.llm import PromptingEngine, PromptConfig
from app.services.pipeline.animation.config import (
    VISION_QC_FRAME_DIR_NAME,
    VISION_QC_FRAME_TIME_ROUND,
    VISION_QC_FRAME_WIDTH,
    VISION_QC_MAX_FRAMES_PER_CALL,
    VISION_QC_MAX_OUTPUT_TOKENS,
    VISION_QC_TEMPERATURE,
    VISION_QC_TIMEOUT,
)
from app.services.pipeline.animation.prompts import VISION_QC_USER, VISION_QC_SCHEMA
from .models import IssueSeverity, IssueConfidence, IssueCategory, ValidationIssue
from .static import ValidationResult

logger = get_logger(__name__, component="vision_validator")


@dataclass(frozen=True)
class FrameTarget:
    time_sec: float
    source_message: str


class VisionValidator:
    """Visually verify uncertain spatial issues against rendered frames.

    This is NOT a primary detector. The spatial validator (injected into
    the Manim subprocess) catches issues deterministically. VisionValidator
    only runs on issues that were uncertain (low/medium confidence) to
    provide a visual confirmation before committing to an expensive
    LLM fix round.
    """

    def __init__(self, engine: PromptingEngine):
        self.engine = engine

    async def verify_issues(
        self,
        video_path: str,
        uncertain_issues: List[ValidationIssue],
        output_dir: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[ValidationIssue]:
        """Visually verify uncertain spatial issues against the rendered video.

        Args:
            video_path: Path to the rendered video file.
            uncertain_issues: Issues with needs_verification=True from spatial check.
            output_dir: Directory for frame extraction.
            context: Optional logging context.

        Returns:
            List of visually CONFIRMED issues (false positives removed).
        """
        if not uncertain_issues:
            return []

        # Build frame targets from uncertain issues
        frame_targets = []
        issue_map: Dict[float, List[ValidationIssue]] = {}
        for issue in uncertain_issues:
            time_sec = issue.details.get("time_sec")
            if not isinstance(time_sec, (int, float)):
                # No time info — can't extract frame, keep as uncertain
                frame_targets.append(FrameTarget(
                    time_sec=0.0,
                    source_message=issue.message,
                ))
                issue_map.setdefault(0.0, []).append(issue)
                continue
            frame_targets.append(FrameTarget(
                time_sec=float(time_sec),
                source_message=issue.message,
            ))
            issue_map.setdefault(float(time_sec), []).append(issue)

        result = await self.validate(video_path, frame_targets, output_dir, context)

        if not result.issues:
            # Vision QC found nothing — all uncertain issues are likely false positives
            logger.info(
                f"Vision QC verified {len(uncertain_issues)} issues as clean"
            )
            return []

        # Return the vision-confirmed issues
        logger.info(
            f"Vision QC confirmed {len(result.issues)} of "
            f"{len(uncertain_issues)} uncertain issues"
        )
        return result.issues

    async def validate(
        self,
        video_path: str,
        frame_targets: List[FrameTarget],
        output_dir: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        result = ValidationResult(valid=True)
        if not frame_targets:
            return result

        frames_dir = Path(output_dir) / VISION_QC_FRAME_DIR_NAME
        frames_dir.mkdir(parents=True, exist_ok=True)

        frame_items = await self._extract_frames(video_path, frame_targets, frames_dir)
        if not frame_items:
            return result

        for batch_start in range(0, len(frame_items), VISION_QC_MAX_FRAMES_PER_CALL):
            batch = frame_items[batch_start:batch_start + VISION_QC_MAX_FRAMES_PER_CALL]
            batch_issues = await self._analyze_frames(batch, context)
            for issue in batch_issues:
                result.add_issue(issue)

        return result

    async def _extract_frames(
        self,
        video_path: str,
        frame_targets: List[FrameTarget],
        frames_dir: Path,
    ) -> List[Dict[str, Any]]:
        seen = set()
        items: List[Dict[str, Any]] = []
        round_unit = VISION_QC_FRAME_TIME_ROUND if VISION_QC_FRAME_TIME_ROUND > 0 else 0.1
        for idx, target in enumerate(frame_targets):
            time_key = round(target.time_sec / round_unit) * round_unit
            if time_key in seen:
                continue
            seen.add(time_key)

            filename = f"frame_{idx}_t{time_key:.2f}.png"
            frame_path = frames_dir / filename
            ok = await self._extract_frame(video_path, frame_path, time_key)
            if not ok:
                continue

            items.append({
                "frame_path": frame_path,
                "frame_file": filename,
                "time_sec": time_key,
                "source_message": target.source_message,
            })

        return items

    async def _extract_frame(self, video_path: str, output_path: Path, time_sec: float) -> bool:
        scale_filter = f"scale={VISION_QC_FRAME_WIDTH}:-1" if VISION_QC_FRAME_WIDTH else None
        cmd = [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-ss",
            f"{time_sec:.3f}",
            "-i",
            video_path,
            "-frames:v",
            "1",
        ]
        if scale_filter:
            cmd.extend(["-vf", scale_filter])
        cmd.append(str(output_path))

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                logger.warning(
                    f"Frame extraction failed at {time_sec:.2f}s: {result.stderr[:200]}"
                )
                return False
        except Exception as exc:
            logger.warning(f"Frame extraction error: {exc}")
            return False

        return output_path.exists()

    async def _analyze_frames(
        self,
        batch: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]],
    ) -> List[ValidationIssue]:
        frame_context = "\n".join(
            f"- {item['frame_file']} @ {item['time_sec']:.2f}s (source: {item['source_message'][:120]})"
            for item in batch
        )

        prompt = VISION_QC_USER.format(frame_context=frame_context)
        contents = [prompt]
        for item in batch:
            image_bytes = item["frame_path"].read_bytes()
            contents.append(self._build_image_part(image_bytes))

        config = PromptConfig(
            temperature=VISION_QC_TEMPERATURE,
            max_output_tokens=VISION_QC_MAX_OUTPUT_TOKENS,
            timeout=VISION_QC_TIMEOUT,
            response_format="json",
            response_schema=VISION_QC_SCHEMA,
        )

        response = await self.engine.generate(
            prompt=prompt,
            config=config,
            contents=contents,
            context=context,
        )

        if not response.get("success"):
            logger.warning(f"Vision QC request failed: {response.get('error')}")
            return []

        payload = response.get("parsed_json") or {}
        issues = payload.get("issues") if isinstance(payload, dict) else None
        if not isinstance(issues, list):
            return []

        mapped: List[ValidationIssue] = []
        for issue in issues:
            if not isinstance(issue, dict):
                continue

            frame_file = issue.get("frame")
            time_sec = issue.get("time_sec")
            message = issue.get("message")
            if not message:
                continue

            severity = _map_severity(issue.get("severity"))
            confidence = _map_confidence(issue.get("confidence"))
            fix_hint = issue.get("fix_hint")

            frame_match = next((i for i in batch if i["frame_file"] == frame_file), None)
            if frame_match:
                frame_path = frame_match["frame_path"]
                source_message = frame_match["source_message"]
                if time_sec is None:
                    time_sec = frame_match["time_sec"]
            else:
                frame_path = None
                source_message = ""

            details = {
                "frame_file": frame_file,
                "frame_path": str(frame_path) if frame_path else None,
                "time_sec": time_sec,
                "source_message": source_message,
            }

            mapped.append(ValidationIssue(
                severity=severity,
                confidence=confidence,
                category=IssueCategory.VISUAL_QUALITY,
                message=f"{message} (t={time_sec:.2f}s)" if isinstance(time_sec, (int, float)) else message,
                auto_fixable=False,
                fix_hint=fix_hint,
                details=details,
            ))

        return mapped

    def _build_image_part(self, image_bytes: bytes):
        try:
            return self.engine.types.Part.from_data(data=image_bytes, mime_type="image/png")
        except AttributeError:
            return self.engine.types.Part.from_bytes(data=image_bytes, mime_type="image/png")


def _map_severity(raw: Optional[str]) -> IssueSeverity:
    value = (raw or "").lower()
    if value == "critical":
        return IssueSeverity.CRITICAL
    if value == "info":
        return IssueSeverity.INFO
    return IssueSeverity.WARNING


def _map_confidence(raw: Optional[str]) -> IssueConfidence:
    value = (raw or "").lower()
    if value == "high":
        return IssueConfidence.HIGH
    if value == "low":
        return IssueConfidence.LOW
    return IssueConfidence.MEDIUM
