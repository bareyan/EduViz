"""
Visual Quality Control - Uses local LLM with vision to check generated videos
Analyzes video frames for overlaps, off-screen elements, and visual issues
"""

import os
import subprocess
import tempfile
import re
import json
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import asyncio

try:
    from ollama import AsyncClient
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    print("[VisualQC] Warning: ollama package not installed. Run: pip install ollama")


class VisualQualityController:
    """
    Analyzes generated Manim videos using a local vision-capable LLM
    Checks for visual issues and suggests code fixes
    """
    
    # Fast local model with vision capabilities
    # Options: llama3.2-vision, minicpm-v, llava, moondream
    DEFAULT_MODEL = "llama3.2-vision:latest"
    
    # Alternative models (in order of speed vs capability)
    MODELS = {
        "fastest": "moondream:latest",           # ~2GB, very fast
        "balanced": "llama3.2-vision:latest",    # ~8GB, good balance
        "capable": "llava:13b",                  # ~8GB, more capable
        "best": "minicpm-v:latest"               # ~16GB, most capable
    }
    
    MAX_QC_ITERATIONS = 2  # Maximum times to retry fixing visual issues
    
    def __init__(self, model: str = None):
        """Initialize the visual QC service
        
        Args:
            model: Model name or tier ("fastest", "balanced", "capable", "best")
        """
        if not OLLAMA_AVAILABLE:
            raise ImportError("ollama package required. Install with: pip install ollama")
        
        # Resolve model name
        if model in self.MODELS:
            self.model = self.MODELS[model]
        elif model:
            self.model = model
        else:
            self.model = self.DEFAULT_MODEL
        
        self.client = AsyncClient()
        print(f"[VisualQC] Initialized with model: {self.model}")
    
    async def check_model_available(self) -> bool:
        """Check if the vision model is available locally"""
        try:
            # List available models
            models_response = await self.client.list()
            
            # Handle different response formats
            if hasattr(models_response, 'models'):
                models_list = models_response.models
            elif isinstance(models_response, dict):
                models_list = models_response.get('models', [])
            else:
                models_list = []
            
            # Extract model names
            available_models = []
            for m in models_list:
                if hasattr(m, 'model'):
                    available_models.append(m.model)
                elif isinstance(m, dict) and 'name' in m:
                    available_models.append(m['name'])
                elif isinstance(m, dict) and 'model' in m:
                    available_models.append(m['model'])
            
            # Check if our model is available
            model_base = self.model.split(':')[0]
            is_available = any(model_base in m for m in available_models)
            
            if not is_available:
                print(f"[VisualQC] Model {self.model} not found locally")
                print(f"[VisualQC] To install: ollama pull {self.model}")
                print(f"[VisualQC] Available models: {', '.join(available_models) if available_models else 'none'}")
            
            return is_available
        except Exception as e:
            print(f"[VisualQC] Error checking model availability: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def extract_keyframes(self, video_path: str, num_frames: int = 5) -> tuple[List[str], List[float]]:
        """Extract keyframes from video for analysis
        
        Args:
            video_path: Path to the video file
            num_frames: Number of frames to extract (evenly distributed)
        
        Returns:
            Tuple of (list of frame image paths, list of timestamps in seconds)
        """
        video_path = Path(video_path)
        if not video_path.exists():
            print(f"[VisualQC] Video not found: {video_path}")
            return [], []
        
        # Create temp directory for frames
        temp_dir = video_path.parent / f".qc_frames_{video_path.stem}"
        temp_dir.mkdir(exist_ok=True)
        
        frame_paths = []
        timestamps = []
        
        try:
            # Get video duration first
            duration_cmd = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(video_path)
            ]
            
            result = subprocess.run(duration_cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                print(f"[VisualQC] Failed to get video duration")
                return [], []
            
            try:
                duration = float(result.stdout.strip())
            except ValueError:
                print(f"[VisualQC] Invalid duration value")
                return [], []
            
            # Extract frames at even intervals
            for i in range(num_frames):
                # Calculate timestamp (avoid very start and end)
                timestamp = (duration * (i + 1)) / (num_frames + 1)
                
                frame_path = temp_dir / f"frame_{i:02d}.png"
                
                # Extract frame using ffmpeg
                cmd = [
                    "ffmpeg",
                    "-ss", str(timestamp),
                    "-i", str(video_path),
                    "-vframes", "1",
                    "-q:v", "2",  # High quality
                    "-y",  # Overwrite
                    str(frame_path)
                ]
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0 and frame_path.exists():
                    frame_paths.append(str(frame_path))
                    timestamps.append(round(timestamp, 2))  # Round to 2 decimal places
                else:
                    print(f"[VisualQC] Failed to extract frame {i}")
            
            return frame_paths, timestamps
        
        except subprocess.TimeoutExpired:
            print(f"[VisualQC] Frame extraction timed out")
            return frame_paths, timestamps
        except Exception as e:
            print(f"[VisualQC] Error extracting frames: {e}")
            return frame_paths, timestamps
    
    async def analyze_frames(
        self,
        frame_paths: List[str],
        timestamps: List[float],
        section_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze video frames for visual quality issues
        
        Args:
            frame_paths: List of frame image paths to analyze
            timestamps: List of timestamps (in seconds) corresponding to each frame
            section_info: Section metadata (title, narration, visual_description)
        
        Returns:
            Dict with status ("ok" or "issues"), description, and issues list
        """
        if not frame_paths:
            return {
                "status": "error",
                "description": "No frames to analyze",
                "issues": []
            }
        
        # Build analysis prompt
        title = section_info.get("title", "Untitled")
        visual_desc = section_info.get("visual_description", "")
        narration = section_info.get("narration", "")[:500]  # Truncate for context
        
        # Build frame info with timestamps
        frame_info = "\n".join([
            f"Frame {i}: {ts}s into the video"
            for i, ts in enumerate(timestamps)
        ])
        
        prompt = f"""You are analyzing frames from an educational math/science video animation made with Manim.

**Section Context:**
- Title: {title}
- Intended Visuals: {visual_desc}
- Narration (excerpt): {narration}

**Frames Analyzed:**
{frame_info}

**Your Task:**
Analyze these frames and identify ANY visual problems:

**CRITICAL ISSUES** (must fix):
1. **Text Overlap**: Text overlapping with other text or equations
2. **Off-screen Elements**: Important content cut off or outside the frame
3. **Unreadable Text**: Text too small, wrong color contrast, or blurry
4. **Crowded Layout**: Too many elements squeezed into one area
5. **Element Collision**: Shapes/diagrams overlapping inappropriately
6. **Poor Positioning**: Elements awkwardly placed or misaligned

**MODERATE ISSUES** (should fix if easy):
7. **Timing Issues**: Elements appearing/disappearing too quickly
8. **Color Problems**: Poor color choices or insufficient contrast
9. **Layout Imbalance**: Content heavily weighted to one side
10. **Visual Clutter**: Too many elements on screen at once

**Response Format:**
Provide a JSON object:
```json
{{
  "status": "ok" or "issues",
  "description": "Detailed overall summary of all visual problems found (ONLY if there are issues)",
  "issues": [
    {{
      "severity": "critical" or "moderate",
      "type": "overlap|offscreen|unreadable|crowded|collision|positioning|timing|color|balance|clutter",
      "description": "Detailed, specific description of what's wrong - include which elements are affected, their positions, and visual impact",
      "timestamps": [1.5, 3.2],
      "suggestion": "Specific, actionable Manim code suggestion with concrete methods and parameters"
    }}
  ]
}}
```

**IMPORTANT - Be Detailed When Reporting Issues**: 
- For each issue, provide SPECIFIC details: which elements (by their visible text/content), exact nature of the problem, and visual impact
- Example GOOD description: "The title text 'Linear Equations' overlaps with the equation 'y = mx + b' below it by approximately 20 pixels, making both partially unreadable. The title is positioned at screen top-center while the equation is also near top, causing the collision."
- Example BAD description: "Text overlaps with equation"
- Include the TIMESTAMP(S) in seconds where the problem appears
- Provide specific Manim code suggestions: "Use title.next_to(equation, UP, buff=0.8) to position title above with proper spacing"

**If NO Issues Found:**
Respond with ONLY:
```json
{{
  "status": "ok",
  "issues": []
}}
```
DO NOT include a description if status is "ok".

Analyze carefully and be DETAILED and SPECIFIC about problems you see."""

        try:
            # Prepare images for the model
            messages = [
                {
                    "role": "user",
                    "content": prompt,
                    "images": frame_paths
                }
            ]
            
            # Call vision model
            response = await self.client.chat(
                model=self.model,
                messages=messages,
                options={
                    "temperature": 0.1,  # Low temperature for consistent analysis
                    "num_predict": 1000,  # Allow detailed response
                }
            )
            
            response_text = response.get("message", {}).get("content", "")
            
            # Parse JSON response
            result = self._parse_analysis_response(response_text)
            
            # Print results to console
            if result.get("status") == "ok":
                print(f"[VisualQC] ✅ QC PASSED - {result.get('description', 'No issues found')}")
            elif result.get("status") == "issues":
                issues = result.get("issues", [])
                critical = [i for i in issues if i.get("severity") == "critical"]
                moderate = [i for i in issues if i.get("severity") == "moderate"]
                print(f"[VisualQC] ⚠️  QC FOUND ISSUES - {result.get('description', '')}")
                if critical:
                    print(f"[VisualQC]    Critical issues: {len(critical)}")
                    for issue in critical:
                        print(f"[VisualQC]      - {issue.get('type', 'unknown')}: {issue.get('description', 'N/A')}")
                if moderate:
                    print(f"[VisualQC]    Moderate issues: {len(moderate)}")
                    for issue in moderate:
                        print(f"[VisualQC]      - {issue.get('type', 'unknown')}: {issue.get('description', 'N/A')}")
            else:
                print(f"[VisualQC] ❌ QC ERROR - {result.get('description', 'Unknown error')}")
            
            return result
        
        except Exception as e:
            print(f"[VisualQC] Error during frame analysis: {e}")
            return {
                "status": "error",
                "description": f"Analysis failed: {str(e)}",
                "issues": []
            }
    
    def _parse_analysis_response(self, response_text: str) -> Dict[str, Any]:
        """Parse the LLM's analysis response"""
        import re
        
        # Try to extract JSON from response
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if not json_match:
            # Try without code blocks
            json_match = re.search(r'(\{.*\})', response_text, re.DOTALL)
        
        if json_match:
            try:
                result = json.loads(json_match.group(1))
                return result
            except json.JSONDecodeError:
                pass
        
        # Fallback: parse manually
        if "ok" in response_text.lower() and "no issues" in response_text.lower():
            return {
                "status": "ok",
                "description": "Visuals appear acceptable",
                "issues": []
            }
        else:
            # If we can't parse but there seem to be issues mentioned
            return {
                "status": "issues",
                "description": "Potential issues detected (parse failed)",
                "issues": [{
                    "severity": "moderate",
                    "type": "unknown",
                    "description": response_text[:300],
                    "frame_indices": [],
                    "suggestion": "Review the video manually"
                }]
            }
    
    async def generate_fix(
        self,
        original_code: str,
        section_info: Dict[str, Any],
        analysis_result: Dict[str, Any]
    ) -> Optional[str]:
        """Generate fixed Manim code based on visual QC analysis
        
        Args:
            original_code: The original Manim code that produced issues
            section_info: Section metadata
            analysis_result: The QC analysis result with issues
        
        Returns:
            Fixed Manim code, or None if fix generation failed
        """
        issues = analysis_result.get("issues", [])
        if not issues:
            return None
        
        # Build fix prompt with timestamp information
        issues_description = "\n".join([
            f"- [{issue.get('severity', 'unknown').upper()}] {issue.get('type', 'unknown')} at {', '.join(str(t)+'s' for t in issue.get('timestamps', []))}: {issue.get('description', '')}\n  Suggestion: {issue.get('suggestion', 'N/A')}"
            for issue in issues
        ])
        
        prompt = f"""You are an expert Manim programmer fixing visual quality issues.

**ORIGINAL MANIM CODE:**
```python
{original_code}
```

**VISUAL QUALITY ISSUES DETECTED:**
{issues_description}

**SECTION INFO:**
- Title: {section_info.get('title', '')}
- Visual Description: {section_info.get('visual_description', '')}
- Target Duration: {section_info.get('target_duration', 30)} seconds

**YOUR TASK:**
Fix the Manim code to address ALL the identified issues while maintaining the educational intent.

**COMMON FIXES:**

1. **Text Overlap:**
   - Use `.next_to()` with proper buffer: `text2.next_to(text1, DOWN, buff=0.5)`
   - Use `.arrange()` for groups: `VGroup(text1, text2).arrange(DOWN, buff=0.5)`
   - Scale down if needed: `text.scale(0.8)`

2. **Off-screen Elements:**
   - Use `.to_edge()`: `text.to_edge(UP)`
   - Use `.shift()`: `equation.shift(UP * 2)`
   - Center with `.move_to(ORIGIN)` or `.center()`

3. **Unreadable Text:**
   - Increase font_size: `Text("Title", font_size=48)`
   - Use high-contrast colors: `Text("Text", color=WHITE)` on dark bg
   - Avoid tiny text: minimum font_size=24

4. **Crowded Layout:**
   - Show fewer elements at once
   - Use FadeOut to remove old content before adding new
   - Spread elements: `.arrange(RIGHT, buff=1.0)`

5. **Element Collision:**
   - Check positions with `.get_center()`, `.get_top()`, etc.
   - Use `.next_to()` relative positioning
   - Clear the scene: `self.play(FadeOut(VGroup(*self.mobjects)))`

6. **Poor Positioning:**
   - Align to edges: `.to_edge(LEFT)`, `.to_corner(UL)`
   - Use standard positions: `UP`, `DOWN`, `LEFT`, `RIGHT`
   - Balance layout: place related items together

**RESPOND WITH ONLY THE FIXED CODE:**
Return the complete, working Python code with the fixes applied. Start with imports, include the full class definition.
Do NOT include explanations or markdown - just the code."""

        try:
            # Use the LLM to generate fixed code (text-only, no vision needed)
            response = await self.client.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                options={
                    "temperature": 0.2,
                    "num_predict": 2000
                }
            )
            
            fixed_code = response.get("message", {}).get("content", "")
            
            # Extract code if wrapped in markdown
            code_match = re.search(r'```python\s*(.*?)\s*```', fixed_code, re.DOTALL)
            if code_match:
                fixed_code = code_match.group(1)
            
            # Validate the fixed code has basic structure
            if "class" in fixed_code and "def construct" in fixed_code:
                return fixed_code
            else:
                print("[VisualQC] Fixed code missing required structure")
                return None
        
        except Exception as e:
            print(f"[VisualQC] Error generating fix: {e}")
            return None
    
    def cleanup_frames(self, frame_paths: List[str]):
        """Clean up extracted frame files"""
        for frame_path in frame_paths:
            try:
                frame_file = Path(frame_path)
                if frame_file.exists():
                    frame_file.unlink()
                
                # Remove parent directory if empty
                parent = frame_file.parent
                if parent.exists() and parent.name.startswith('.qc_frames_'):
                    try:
                        parent.rmdir()
                    except OSError:
                        pass  # Directory not empty
            except Exception as e:
                print(f"[VisualQC] Error cleaning up frame: {e}")
    
    async def check_video_quality(
        self,
        video_path: str,
        section_info: Dict[str, Any],
        num_frames: int = 5
    ) -> Dict[str, Any]:
        """Complete quality check workflow: extract frames, analyze, return results
        
        Args:
            video_path: Path to the generated video
            section_info: Section metadata
            num_frames: Number of frames to extract for analysis
        
        Returns:
            Dict with status, description, issues, and frame_paths
        """
        section_title = section_info.get("title", "Unknown")
        print(f"[VisualQC] Starting QC for section: '{section_title}'")
        print(f"[VisualQC] Video path: {video_path}")
        
        # Extract keyframes
        frame_paths, timestamps = self.extract_keyframes(video_path, num_frames)
        
        if not frame_paths:
            print(f"[VisualQC] ❌ Failed to extract frames")
            return {
                "status": "error",
                "description": "Failed to extract frames from video",
                "issues": [],
                "frame_paths": []
            }
        
        print(f"[VisualQC] ✓ Extracted {len(frame_paths)} frames at: {', '.join(f'{t}s' for t in timestamps)}")
        
        # Analyze frames
        analysis = await self.analyze_frames(frame_paths, timestamps, section_info)
        analysis["frame_paths"] = frame_paths
        
        # Enhanced console output
        if analysis["status"] == "ok":
            print(f"[VisualQC] ✅ Visual QC passed - no issues detected")
        elif analysis["status"] == "issues":
            issues = analysis.get("issues", [])
            description = analysis.get("description", "")
            
            print(f"[VisualQC] ⚠️ Found {len(issues)} issue(s)")
            if description:
                print(f"[VisualQC] Summary: {description}")
            print(f"[VisualQC] Issues:")
            
            for idx, issue in enumerate(issues, 1):
                severity_emoji = "❌" if issue.get("severity") == "critical" else "⚠️"
                timestamps_str = ", ".join(f"{t}s" for t in issue.get("timestamps", []))
                issue_type = issue.get('type', 'unknown').upper()
                
                print(f"  {idx}. {severity_emoji} [{issue_type}] at {timestamps_str}")
                print(f"     Problem: {issue.get('description', 'No description')}")
                print(f"     Fix: {issue.get('suggestion', 'No suggestion')}")
        
        return analysis


# Convenience function for easy import
async def check_section_video(
    video_path: str,
    section_info: Dict[str, Any],
    model: str = "balanced"
) -> Dict[str, Any]:
    """
    Quick check of a section video
    
    Args:
        video_path: Path to video file
        section_info: Section metadata
        model: Model tier ("fastest", "balanced", "capable", "best")
    
    Returns:
        Analysis result with status and issues
    """
    qc = VisualQualityController(model=model)
    
    # Check if model is available
    if not await qc.check_model_available():
        return {
            "status": "error",
            "description": f"Model {qc.model} not available. Install with: ollama pull {qc.model}",
            "issues": []
        }
    
    # Run QC
    result = await qc.check_video_quality(video_path, section_info)
    
    # Cleanup
    if result.get("frame_paths"):
        qc.cleanup_frames(result["frame_paths"])
    
    return result
