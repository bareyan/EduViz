"""
Visual Quality Control - Uses Gemini Flash Lite with video analysis to check generated videos
Analyzes video segments for overlaps, off-screen elements, and visual issues
Uses structured output for reliable error detection
"""

import os
import subprocess
import tempfile
import re
import json
import base64
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import asyncio

# Gemini SDK - Unified client for both API and Vertex AI
try:
    from app.services.gemini_client import create_client, get_types_module
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("[VisualQC] Warning: gemini_client not available")

# Model configuration
from app.config.models import get_model_config


class VisualQualityController:
    """
    Analyzes generated Manim videos using Gemini Flash Lite with video input
    Sends downscaled 480p video at 1fps for efficient analysis
    Uses structured output for reliable error detection
    """
    
    # Model configuration - loaded from centralized config
    _config = get_model_config("visual_qc")
    DEFAULT_MODEL = _config.model_name
    
    # Video processing settings
    TARGET_HEIGHT = 480  # 480p
    TARGET_FPS = 1  # 1 frame per second for analysis
    
    MAX_QC_ITERATIONS = 3  # Maximum times to retry fixing visual issues
    
    # Pricing for gemini-2.0-flash-lite (per 1M tokens)
    PRICING = {
        "input": 0.075,      # $0.075 per 1M input tokens (includes video tokens)
        "output": 0.30,      # $0.30 per 1M output tokens
    }
    
    # System instruction for strict visual error detection
    SYSTEM_INSTRUCTION = """You are an expert visual quality control inspector for educational Manim animation videos.

Your task is to analyze videos and detect CRITICAL VISUAL RENDERING ERRORS that affect readability and understanding.

## CRITICAL: ANIMATION-AWARE ANALYSIS

Manim videos contain ANIMATIONS. Objects fade in/out, move, transform, and transition constantly.
You MUST distinguish between:

1. **TRANSIENT issues** (animation artifacts - IGNORE THESE):
   - Issues visible for only 1-2 frames during a transition
   - Partial overlaps that immediately resolve as animation continues
   - Elements briefly at screen edge during movement
   - Temporary visual states during morphing/transforming animations
   
2. **PERSISTENT issues** (real problems - REPORT THESE):
   - Issues that remain visible for 2+ seconds in a STATIC state
   - Overlaps or overflow that persist AFTER an animation completes
   - Elements that stay in a broken state (not mid-animation)
   - Problems visible when the scene is "settled" (nothing actively animating)

## ERRORS TO DETECT (Only if PERSISTENT for 2+ seconds):

### 1. TEXT/EQUATION OVERFLOW (CRITICAL)
- Text or equations extending beyond the visible frame edges (left, right, top, bottom)
- Content cut off or partially hidden at screen boundaries
- Elements positioned too close to edges with risk of clipping
- **Only report if the overflow persists after animation settles**

### 2. ELEMENT OVERLAPS (CRITICAL)
- Text overlapping other text (making content unreadable)
- Equations overlapping explanatory text
- Shapes or diagrams covering text content
- **Only report if overlap persists in a static state, not during transitions**

### 3. RENDERING FAILURES
- Missing LaTeX symbols (showing as boxes or question marks)
- Corrupted or glitched visual elements
- Text not properly rendered (boxes instead of characters)
- **These are usually persistent - report if visible at any point**

### 4. LAYOUT ISSUES
- Text too close together (inadequate spacing) in the final position
- Elements not properly aligned in their final positions
- **Only report if visible after animation completes**

### 5. READABILITY PROBLEMS
- Text too small to read clearly
- Poor contrast in the final rendered state

## WHAT TO IGNORE (NOT ERRORS):
- Smooth animations and transitions (fading, morphing, moving)
- Elements animating in/out (partial opacity during transition)
- Temporary overlaps during animation that resolve immediately
- Brief edge proximity during movement animations
- Dark/black backgrounds (this is the standard Manim style)
- Empty frames at the very start or end
- Motion blur during fast animations
- Artistic style choices (colors, fonts)
- **Any issue that appears for only 1 frame then disappears**

## ANALYSIS APPROACH:
1. Watch the entire video carefully
2. For each potential issue, check if it PERSISTS for at least 2 seconds
3. If an issue appears during animation but resolves when animation ends, IGNORE IT
4. Only report issues that remain visible in a "settled" state
5. Include the duration the issue is visible (start_second to end_second)"""

    def __init__(self, model: str = None):
        """Initialize the visual QC service
        
        Args:
            model: Model name (default: gemini-2.0-flash-lite)
        """
        if not GEMINI_AVAILABLE:
            raise ImportError("gemini_client required")
        
        self.model = model or self.DEFAULT_MODEL
        
        # Initialize unified Gemini client (works with both API and Vertex AI)
        self.client = create_client()
        self.types = get_types_module()
        print(f"[VisualQC] Initialized with model: {self.model} (video mode, {self.TARGET_HEIGHT}p @ {self.TARGET_FPS}fps)")
        
        # Token usage tracking
        self.usage_stats = {
            "input_tokens": 0,
            "output_tokens": 0,
            "videos_processed": 0,
            "total_cost": 0.0
        }
        
        # Error tracking for debugging
        self.error_frames: List[Dict[str, Any]] = []
        self.errors_dir: Optional[Path] = None
        
        # Create structured output schema (lazy initialization)
        self._error_schema = None
    
    @property
    def error_schema(self):
        """Lazily create the structured output schema for error detection"""
        if self._error_schema is None:
            self._error_schema = genai.types.Schema(
                type=genai.types.Type.OBJECT,
                required=["errors_detected", "error_descriptions"],
                properties={
                    "errors_detected": genai.types.Schema(
                        type=genai.types.Type.BOOLEAN,
                        description="True if any PERSISTENT visual errors were detected (lasting 2+ seconds in static state), False if video is clean or only has transient animation artifacts"
                    ),
                    "error_descriptions": genai.types.Schema(
                        type=genai.types.Type.ARRAY,
                        description="List of PERSISTENT errors only (ignore transient animation artifacts)",
                        items=genai.types.Schema(
                            type=genai.types.Type.OBJECT,
                            required=["start_second", "end_second", "duration_seconds", "is_during_animation", "location", "error_type", "description"],
                            properties={
                                "start_second": genai.types.Schema(
                                    type=genai.types.Type.NUMBER,
                                    description="Timestamp in seconds when the error FIRST becomes visible"
                                ),
                                "end_second": genai.types.Schema(
                                    type=genai.types.Type.NUMBER,
                                    description="Timestamp in seconds when the error is no longer visible (or video ends)"
                                ),
                                "duration_seconds": genai.types.Schema(
                                    type=genai.types.Type.NUMBER,
                                    description="How long the error persists (end_second - start_second). Must be >= 2 seconds to be reported."
                                ),
                                "is_during_animation": genai.types.Schema(
                                    type=genai.types.Type.BOOLEAN,
                                    description="True if this issue only appears during active animation/transition and resolves when animation ends. Such issues should NOT be reported."
                                ),
                                "location": genai.types.Schema(
                                    type=genai.types.Type.STRING,
                                    description="Screen location: top-left, top-center, top-right, center-left, center, center-right, bottom-left, bottom-center, bottom-right, or full-screen"
                                ),
                                "error_type": genai.types.Schema(
                                    type=genai.types.Type.STRING,
                                    description="Type of error: overflow, overlap, rendering_failure, layout_issue, readability"
                                ),
                                "description": genai.types.Schema(
                                    type=genai.types.Type.STRING,
                                    description="Specific, concrete description of the PERSISTENT error. Mention that it persists in a static state."
                                )
                            }
                        )
                    )
                }
            )
        return self._error_schema
    
    def _track_usage(self, response, num_videos: int = 0):
        """Track token usage and cost from Gemini response
        
        Args:
            response: Gemini API response
            num_videos: Number of videos in the request
        """
        try:
            # Extract usage from response
            if hasattr(response, 'usage_metadata'):
                usage = response.usage_metadata
                input_tokens = getattr(usage, 'prompt_token_count', 0)
                output_tokens = getattr(usage, 'candidates_token_count', 0)
            else:
                input_tokens = 0
                output_tokens = 0
            
            # Update stats
            self.usage_stats["input_tokens"] += input_tokens
            self.usage_stats["output_tokens"] += output_tokens
            self.usage_stats["videos_processed"] += num_videos
            
            # Calculate cost
            input_cost = (input_tokens / 1_000_000) * self.PRICING["input"]
            output_cost = (output_tokens / 1_000_000) * self.PRICING["output"]
            
            self.usage_stats["total_cost"] += input_cost + output_cost
            
        except Exception as e:
            print(f"[VisualQC] Warning: Could not track usage: {e}")
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics and costs
        
        Returns:
            Dict with token counts, videos processed, and total cost
        """
        return {
            "input_tokens": self.usage_stats["input_tokens"],
            "output_tokens": self.usage_stats["output_tokens"],
            "total_tokens": self.usage_stats["input_tokens"] + self.usage_stats["output_tokens"],
            "videos_processed": self.usage_stats["videos_processed"],
            "total_cost_usd": round(self.usage_stats["total_cost"], 4)
        }
    
    def set_errors_dir(self, output_dir: str):
        """Set the directory to store error screenshots for debugging
        
        Args:
            output_dir: Base output directory (errors folder will be created inside)
        """
        self.errors_dir = Path(output_dir) / "errors"
        self.errors_dir.mkdir(parents=True, exist_ok=True)
        print(f"[VisualQC] Error screenshots will be saved to: {self.errors_dir}")
    
    def _extract_error_frame(
        self, 
        video_path: str,
        timestamp: float, 
        section_title: str,
        error_description: str,
        qc_iteration: int = 0
    ):
        """Extract and save a frame at the error timestamp for debugging
        
        Args:
            video_path: Path to the video file
            timestamp: Timestamp in seconds where error was detected
            section_title: Title of the section
            error_description: Description of the error
            qc_iteration: Which QC iteration this error was found in
        """
        if not self.errors_dir:
            return
        
        try:
            # Create a safe filename
            safe_title = "".join(c if c.isalnum() or c in "._-" else "_" for c in section_title[:30])
            filename = f"{safe_title}_t{timestamp:.1f}s_iter{qc_iteration}.jpg"
            dest_path = self.errors_dir / filename
            
            # Extract frame from video at the timestamp
            cmd = [
                "ffmpeg",
                "-ss", str(timestamp),
                "-i", str(video_path),
                "-vframes", "1",
                "-q:v", "2",
                "-y",
                str(dest_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                print(f"[VisualQC] Warning: Could not extract error frame at {timestamp}s")
                return
            
            # Track this error
            error_info = {
                "section": section_title,
                "timestamp": timestamp,
                "frame_path": str(dest_path),
                "error": error_description,
                "qc_iteration": qc_iteration
            }
            self.error_frames.append(error_info)
            
            print(f"[VisualQC] 📸 Saved error frame: {filename}")
            
        except Exception as e:
            print(f"[VisualQC] Warning: Could not save error frame: {e}")
    
    def print_error_summary(self):
        """Print a summary of all detected errors (even those that were fixed)"""
        if not self.error_frames:
            print("\n[VisualQC] ═══════════════════════════════════════════════════════")
            print("[VisualQC] ERROR SUMMARY: No visual errors detected during QC")
            print("[VisualQC] ═══════════════════════════════════════════════════════\n")
            return
        
        print("\n[VisualQC] ═══════════════════════════════════════════════════════")
        print(f"[VisualQC] ERROR SUMMARY: {len(self.error_frames)} error(s) detected")
        print("[VisualQC] ═══════════════════════════════════════════════════════")
        
        # Group by section
        sections = {}
        for err in self.error_frames:
            section = err.get("section", "Unknown")
            if section not in sections:
                sections[section] = []
            sections[section].append(err)
        
        for section, errors in sections.items():
            print(f"\n[VisualQC] Section: {section}")
            for err in errors:
                iter_str = f"[Iter {err['qc_iteration'] + 1}]" if err.get('qc_iteration', 0) > 0 else "[Initial]"
                print(f"[VisualQC]   {iter_str} {err['timestamp']:.1f}s: {err['error'][:100]}...")
        
        if self.errors_dir:
            print(f"\n[VisualQC] Error frames saved to: {self.errors_dir}")
        print("[VisualQC] ═══════════════════════════════════════════════════════\n")
    
    def get_error_frames(self) -> List[Dict[str, Any]]:
        """Get list of all detected error frames
        
        Returns:
            List of error frame info dicts
        """
        return self.error_frames.copy()
    
    def clear_error_frames(self):
        """Clear the error frames list (call at start of new job)"""
        self.error_frames = []

    async def check_model_available(self) -> bool:
        """Check if the Gemini API is accessible (always true if client initialized)"""
        return True
    
    def _prepare_video_for_analysis(self, video_path: str) -> Optional[str]:
        """Downscale video to 480p at 1fps for efficient analysis
        
        Args:
            video_path: Path to the original video file
        
        Returns:
            Path to the downscaled video file, or None if failed
        """
        video_path = Path(video_path)
        if not video_path.exists():
            print(f"[VisualQC] Video not found: {video_path}")
            return None
        
        # Create temp file for downscaled video
        temp_dir = video_path.parent / ".qc_temp"
        temp_dir.mkdir(exist_ok=True)
        output_path = temp_dir / f"qc_{video_path.stem}_480p_1fps.mp4"
        
        try:
            # Get original video info
            probe_cmd = [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height,duration",
                "-of", "json",
                str(video_path)
            ]
            
            result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                print(f"[VisualQC] Failed to probe video")
                return None
            
            # Downscale to 480p height at 1fps
            # Using -vf scale=-2:480 to maintain aspect ratio (width divisible by 2)
            cmd = [
                "ffmpeg",
                "-i", str(video_path),
                "-vf", f"scale=-2:{self.TARGET_HEIGHT},fps={self.TARGET_FPS}",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "28",  # Lower quality is fine for analysis
                "-an",  # No audio needed
                "-y",  # Overwrite
                str(output_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode != 0:
                print(f"[VisualQC] Failed to downscale video: {result.stderr}")
                return None
            
            if output_path.exists():
                # Get file size for logging
                size_mb = output_path.stat().st_size / (1024 * 1024)
                print(f"[VisualQC] ✓ Prepared video for analysis: {size_mb:.2f} MB ({self.TARGET_HEIGHT}p @ {self.TARGET_FPS}fps)")
                return str(output_path)
            else:
                return None
                
        except subprocess.TimeoutExpired:
            print(f"[VisualQC] Video preparation timed out")
            return None
        except Exception as e:
            print(f"[VisualQC] Error preparing video: {e}")
            return None
    
    def _cleanup_temp_video(self, temp_video_path: str):
        """Clean up temporary video file"""
        try:
            temp_path = Path(temp_video_path)
            if temp_path.exists():
                temp_path.unlink()
            
            # Remove parent directory if empty
            parent = temp_path.parent
            if parent.exists() and parent.name == ".qc_temp":
                try:
                    parent.rmdir()
                except OSError:
                    pass
        except Exception as e:
            print(f"[VisualQC] Warning: Could not clean up temp video: {e}")

    async def analyze_video(
        self,
        video_path: str,
        section_info: Dict[str, Any],
        qc_iteration: int = 0
    ) -> Dict[str, Any]:
        """Analyze a video segment for visual quality issues using Gemini video input
        
        Args:
            video_path: Path to the downscaled video file
            section_info: Section metadata
            qc_iteration: Current QC iteration
        
        Returns:
            Dict with status ("ok" or "issues") and error_report
        """
        section_title = section_info.get("title", "Unknown")
        full_narration = section_info.get("narration", section_info.get("tts_narration", ""))
        visual_description = section_info.get("visual_description", "")
        duration = section_info.get("duration_seconds", section_info.get("duration", 30))
        
        # Build context for the prompt
        narration_segments = section_info.get("narration_segments", [])
        segment_context = ""
        if narration_segments:
            segment_lines = []
            cumulative = 0.0
            for seg in narration_segments:
                seg_duration = seg.get("estimated_duration", seg.get("duration", 5))
                seg_text = seg.get("text", seg.get("tts_text", ""))[:80]
                segment_lines.append(f"  [{cumulative:.1f}s-{cumulative + seg_duration:.1f}s]: \"{seg_text}...\"")
                cumulative += seg_duration
            segment_context = "\n".join(segment_lines)
        
        # Build the analysis prompt
        user_prompt = f"""Analyze this Manim educational animation video for PERSISTENT VISUAL ERRORS.

VIDEO CONTEXT:
- Section Title: "{section_title}"
- Total Duration: {duration:.1f} seconds
- Expected Content: {visual_description[:300] if visual_description else "Educational mathematical animation"}

NARRATION TIMELINE (what should be shown when):
{segment_context if segment_context else full_narration[:500]}

## CRITICAL: ANIMATION-AWARE ANALYSIS

This is an ANIMATED video. Objects constantly fade in/out, move, transform, and transition.

**ONLY REPORT ERRORS THAT:**
1. Persist for AT LEAST 2 SECONDS in a STATIC state (not during animation)
2. Remain visible AFTER the animation/transition completes
3. Represent a final rendered state that is broken

**DO NOT REPORT:**
- Issues visible for only 1 frame during a transition
- Temporary overlaps that resolve as animation continues
- Brief edge proximity during movement
- Any issue that disappears when the animation settles

## ANALYSIS INSTRUCTIONS:
1. Watch the ENTIRE video carefully
2. When you see a potential issue, WAIT to see if it persists
3. If the issue resolves within 1-2 seconds (during animation), IGNORE IT
4. If the issue remains for 2+ seconds in a STATIC state, REPORT IT
5. Note BOTH the start_second AND end_second for each error
6. Set is_during_animation=true for any issue that only appears during transitions (these should NOT be in your final list)

## EXAMPLES:
- Text overlaps another element during FadeIn but separates when animation ends → IGNORE (transient)
- Text overlaps another element and stays overlapped for 5 seconds → REPORT (persistent)
- Equation briefly touches screen edge during Transform animation → IGNORE (transient)  
- Equation is cut off at screen edge for the rest of the video → REPORT (persistent)

REMEMBER: When in doubt, check if the issue persists in a "settled" state. Only report PERSISTENT issues."""

        try:
            # Read video file as bytes
            with open(video_path, "rb") as f:
                video_bytes = f.read()
            
            # Create video part for Gemini
            # Note: video_metadata is not supported in from_bytes, fps is inferred from the video
            video_part = types.Part.from_bytes(
                data=video_bytes,
                mime_type="video/mp4"
            )
            
            # Create content with video and prompt
            contents = [
                types.Content(
                    role="user",
                    parts=[video_part]
                ),
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=user_prompt)]
                )
            ]
            
            # Generate content config with structured output
            config = types.GenerateContentConfig(
                system_instruction=[types.Part.from_text(text=self.SYSTEM_INSTRUCTION)],
                media_resolution="MEDIA_RESOLUTION_LOW",  # Low res for efficiency
                temperature=0.1,  # Low temperature for consistent analysis
                max_output_tokens=2048,
                response_mime_type="application/json",
                response_schema=self.error_schema
            )
            
            # Call Gemini API
            print(f"[VisualQC] Sending video to Gemini for analysis...")
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model,
                contents=contents,
                config=config
            )
            
            # Track usage
            self._track_usage(response, num_videos=1)
            
            # Parse structured JSON response
            response_text = response.text.strip() if response.text else "{}"
            
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError as e:
                print(f"[VisualQC] Warning: Failed to parse JSON response: {e}")
                print(f"[VisualQC] Raw response: {response_text[:500]}")
                return {
                    "status": "error",
                    "error_report": "Failed to parse QC response"
                }
            
            # Process structured result
            errors_detected = result.get("errors_detected", False)
            error_descriptions = result.get("error_descriptions", [])
            
            if errors_detected and error_descriptions:
                error_reports = []
                filtered_count = 0
                
                # Get the original video path for frame extraction
                original_video = section_info.get("_original_video_path", video_path)
                
                # Minimum duration threshold for persistent errors (in seconds)
                MIN_PERSISTENT_DURATION = 1.5  # Slightly under 2s to account for frame timing
                
                for error in error_descriptions:
                    # Get timing information from new schema
                    start_second = error.get("start_second", error.get("second", 0))
                    end_second = error.get("end_second", start_second + 1)
                    duration = error.get("duration_seconds", end_second - start_second)
                    is_during_animation = error.get("is_during_animation", False)
                    
                    location = error.get("location", "unknown")
                    error_type = error.get("error_type", "unknown")
                    description = error.get("description", "No description")
                    
                    # Filter out transient/animation issues
                    if is_during_animation:
                        print(f"[VisualQC] Filtered (animation): {description[:60]}...")
                        filtered_count += 1
                        continue
                    
                    if duration < MIN_PERSISTENT_DURATION:
                        print(f"[VisualQC] Filtered (transient, {duration:.1f}s < {MIN_PERSISTENT_DURATION}s): {description[:60]}...")
                        filtered_count += 1
                        continue
                    
                    # This is a persistent error - report it
                    error_str = f"At {start_second:.1f}s-{end_second:.1f}s ({duration:.1f}s) [{location}] ({error_type}): {description}"
                    error_reports.append(error_str)
                    
                    # Extract and save error frame for debugging (at midpoint of error)
                    frame_timestamp = (start_second + end_second) / 2
                    self._extract_error_frame(
                        original_video,
                        frame_timestamp,
                        section_title,
                        f"[{location}] {error_type}: {description}",
                        qc_iteration
                    )
                
                if filtered_count > 0:
                    print(f"[VisualQC] Filtered out {filtered_count} transient/animation issue(s)")
                
                if error_reports:
                    full_report = "\n".join(error_reports)
                    print(f"[VisualQC] ⚠️  Found {len(error_reports)} PERSISTENT issue(s):")
                    for report in error_reports:
                        print(f"[VisualQC]    {report}")
                    
                    return {
                        "status": "issues",
                        "error_report": full_report
                    }
                else:
                    print(f"[VisualQC] ✅ QC PASSED - All detected issues were transient (animation artifacts)")
                    return {
                        "status": "ok",
                        "error_report": ""
                    }
            else:
                print(f"[VisualQC] ✅ QC PASSED - No visual errors detected")
                return {
                    "status": "ok",
                    "error_report": ""
                }
        
        except Exception as e:
            print(f"[VisualQC] Error analyzing video: {e}")
            import traceback
            traceback.print_exc()
            return {
                "status": "error",
                "error_report": f"Analysis failed: {str(e)}"
            }

    async def check_video_quality(
        self,
        video_path: str,
        section_info: Dict[str, Any],
        seconds_per_frame: float = 7.5,  # Kept for backward compatibility, not used
        skip_first: bool = True,  # Kept for backward compatibility, not used
        qc_iteration: int = 0
    ) -> Dict[str, Any]:
        """Complete quality check workflow: prepare video, analyze with Gemini, return results
        
        Args:
            video_path: Path to the generated video
            section_info: Section metadata
            seconds_per_frame: (Deprecated) Not used in video mode
            skip_first: (Deprecated) Not used in video mode
            qc_iteration: Current QC iteration (0 = initial, 1 = after first fix, etc.)
        
        Returns:
            Dict with status, error_report, and temp_video_path
        """
        section_title = section_info.get("title", "Unknown")
        print(f"[VisualQC] Starting video QC for section: '{section_title}'")
        print(f"[VisualQC] Video path: {video_path}")
        print(f"[VisualQC] Mode: Video analysis ({self.TARGET_HEIGHT}p @ {self.TARGET_FPS}fps)")
        
        # Prepare video for analysis (downscale to 480p at 1fps)
        temp_video_path = self._prepare_video_for_analysis(video_path)
        
        if not temp_video_path:
            print(f"[VisualQC] ❌ Failed to prepare video for analysis")
            return {
                "status": "error",
                "error_report": "Failed to prepare video for analysis",
                "temp_video_path": None
            }
        
        # Store original video path for frame extraction on errors
        section_info["_original_video_path"] = video_path
        
        # Analyze video
        analysis = await self.analyze_video(temp_video_path, section_info, qc_iteration)
        analysis["temp_video_path"] = temp_video_path
        
        return analysis
    
    def cleanup_frames(self, frame_paths: List[str] = None, temp_video_path: str = None):
        """Clean up temporary files
        
        Args:
            frame_paths: (Deprecated) Not used in video mode
            temp_video_path: Path to temporary video file to clean up
        """
        if temp_video_path:
            self._cleanup_temp_video(temp_video_path)


# Convenience function for easy import
async def check_section_video(
    video_path: str,
    section_info: Dict[str, Any],
    model: str = "gemini-2.0-flash-lite"
) -> Dict[str, Any]:
    """
    Quick check of a section video
    
    Args:
        video_path: Path to video file
        section_info: Section metadata
        model: Model name (default: gemini-2.0-flash-lite)
    
    Returns:
        Analysis result with status and error_report
    """
    qc = VisualQualityController(model=model)
    
    # Check if model is available
    if not await qc.check_model_available():
        return {
            "status": "error",
            "error_report": f"Model {qc.model} not available"
        }
    
    # Run QC
    result = await qc.check_video_quality(video_path, section_info)
    
    # Cleanup
    if result.get("temp_video_path"):
        qc.cleanup_frames(temp_video_path=result["temp_video_path"])
    
    return result
