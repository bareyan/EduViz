"""
Manim Generator - Uses Gemini to generate Manim code for each video section
"""

import os
import json
import asyncio
import subprocess
import tempfile
from typing import Dict, Any, Optional
from pathlib import Path

# Gemini
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

# Visual Quality Control
try:
    from .visual_qc import VisualQualityController
    VISUAL_QC_AVAILABLE = True
except ImportError:
    VISUAL_QC_AVAILABLE = False
    print("[ManimGenerator] Visual QC not available")


class ManimGenerator:
    """Generates Manim animations using Gemini AI"""
    
    MODEL = "gemini-3-flash-preview"  # Main generation - Flash for speed and cost
    CORRECTION_MODEL = "gemini-2.5-flash"  # Cheap model for corrections
    STRONG_MODEL = "gemini-3-pro-preview"  # Strong fallback model for visual fixes
    MAX_CORRECTION_ATTEMPTS = 3  # Maximum number of auto-correction attempts
    
    # Visual QC settings
    ENABLE_VISUAL_QC = True  # Enable visual quality control
    QC_MODEL = "gemini-2.0-flash-lite"  # Vision model for QC (video mode, 480p @ 1fps)
    MAX_QC_ITERATIONS = 2  # Try to fix visual issues up to 2 times
    QC_SECONDS_PER_FRAME = 7.5  # Deprecated - using video mode now
    QC_SKIP_FIRST_FRAME = True  # Deprecated - using video mode now
    
    # Gemini pricing (per 1M tokens) - as of Jan 2026
    # See: https://ai.google.dev/pricing
    PRICING = {
        "gemini-3-pro-preview": {
            "input": 2.0,    # $2.00 per 1M input tokens (<=200K context)
            "output": 12.0   # $12.00 per 1M output tokens (<=200K context)
        },
        "gemini-3-flash-preview": {
            "input": 0.5,   # $0.5 per 1M input tokens
            "output": 3    # $3 per 1M output tokens
        },
        "gemini-flash-lite-latest": {
            "input": 0.075,  # $0.075 per 1M input tokens (similar to 2.0-flash)
            "output": 0.30,  # $0.30 per 1M output tokens
        },
        "gemini-2.0-flash-lite": {
            "input": 0.075,  # $0.075 per 1M input tokens (video converted to tokens)
            "output": 0.30,  # $0.30 per 1M output tokens
        }
    }
    
    # Base Manim template
    BASE_TEMPLATE = '''"""Auto-generated Manim scene"""
from manim import *

class Section{section_id}(Scene):
    def construct(self):
        # Duration target: {duration} seconds
{code}
'''
    
    def __init__(self):
        self.client = None
        api_key = os.getenv("GEMINI_API_KEY")
        if genai and api_key:
            self.client = genai.Client(api_key=api_key)
        else:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        
        # Token usage tracking
        self.token_usage = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_cost": 0.0,
            "by_model": {}
        }
        
        # Initialize visual QC controller
        self.visual_qc = None
        if VISUAL_QC_AVAILABLE and self.ENABLE_VISUAL_QC:
            try:
                self.visual_qc = VisualQualityController(model=self.QC_MODEL)
                print(f"[ManimGenerator] Visual QC enabled with model: {self.QC_MODEL}")
            except Exception as e:
                print(f"[ManimGenerator] Failed to initialize Visual QC: {e}")
                self.visual_qc = None
    
    def _track_token_usage(self, response, model_name: str):
        """Track token usage and calculate cost from Gemini response
        
        Args:
            response: Gemini API response object
            model_name: Name of the model used
        """
        try:
            # Handle None response
            if not response:
                return
            
            # Extract usage metadata from response
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                usage = response.usage_metadata
                input_tokens = getattr(usage, 'prompt_token_count', 0) or 0
                output_tokens = getattr(usage, 'candidates_token_count', 0) or 0
            else:
                # Fallback for different response formats
                input_tokens = 0
                output_tokens = 0
            
            # Update totals
            self.token_usage["input_tokens"] += input_tokens
            self.token_usage["output_tokens"] += output_tokens
            
            # Track by model
            if model_name not in self.token_usage["by_model"]:
                self.token_usage["by_model"][model_name] = {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost": 0.0
                }
            
            self.token_usage["by_model"][model_name]["input_tokens"] += input_tokens
            self.token_usage["by_model"][model_name]["output_tokens"] += output_tokens
            
            # Calculate cost for this call
            if model_name in self.PRICING:
                pricing = self.PRICING[model_name]
                input_cost = (input_tokens / 1_000_000) * pricing["input"]
                output_cost = (output_tokens / 1_000_000) * pricing["output"]
                call_cost = input_cost + output_cost
                
                self.token_usage["by_model"][model_name]["cost"] += call_cost
                self.token_usage["total_cost"] += call_cost
        
        except Exception as e:
            print(f"[ManimGenerator] Warning: Could not track token usage: {e}")
    
    def get_cost_summary(self) -> Dict[str, Any]:
        """Get a summary of token usage and costs
        
        Returns:
            Dict with token counts, costs, and breakdown by model
        """
        summary = {
            "total_input_tokens": self.token_usage["input_tokens"],
            "total_output_tokens": self.token_usage["output_tokens"],
            "total_tokens": self.token_usage["input_tokens"] + self.token_usage["output_tokens"],
            "total_cost_usd": round(self.token_usage["total_cost"], 4),
            "by_model": {
                model: {
                    "input_tokens": data["input_tokens"],
                    "output_tokens": data["output_tokens"],
                    "total_tokens": data["input_tokens"] + data["output_tokens"],
                    "cost_usd": round(data["cost"], 4)
                }
                for model, data in self.token_usage["by_model"].items()
            }
        }
        
        # Add Visual QC stats if available
        if self.visual_qc:
            qc_stats = self.visual_qc.get_usage_stats()
            summary["visual_qc"] = qc_stats
            # Add QC cost to total (convert to same precision)
            summary["total_cost_usd"] = round(summary["total_cost_usd"] + qc_stats["total_cost_usd"], 4)
        
        return summary
    
    def print_cost_summary(self):
        """Print a formatted cost summary to console"""
        summary = self.get_cost_summary()
        
        print("\n" + "=" * 60)
        print("💰 GEMINI API COST SUMMARY")
        print("=" * 60)
        print(f"Total Input Tokens:  {summary['total_input_tokens']:,}")
        print(f"Total Output Tokens: {summary['total_output_tokens']:,}")
        print(f"Total Tokens:        {summary['total_tokens']:,}")
        
        if summary['by_model']:
            print("\nBreakdown by Model:")
            print("-" * 60)
            for model, data in summary['by_model'].items():
                print(f"\n{model}:")
                print(f"  Input:  {data['input_tokens']:,} tokens")
                print(f"  Output: {data['output_tokens']:,} tokens")
                print(f"  Cost:   ${data['cost_usd']:.4f}")
        
        # Display Visual QC stats
        if 'visual_qc' in summary:
            qc = summary['visual_qc']
            print("\nVisual QC (gemini-2.0-flash-lite - video mode):")
            print("-" * 60)
            print(f"  Input:  {qc['input_tokens']:,} tokens")
            print(f"  Output: {qc['output_tokens']:,} tokens")
            print(f"  Videos: {qc['videos_processed']} segments analyzed")
            print(f"  Cost:   ${qc['total_cost_usd']:.4f}")
        
        print(f"\n💵 Total Cost:        ${summary['total_cost_usd']:.4f}")
        print("=" * 60 + "\n")
    
    async def generate_section_video(
        self,
        section: Dict[str, Any],
        output_dir: str,
        section_index: int,
        audio_duration: Optional[float] = None,
        style: str = "3b1b",  # "3b1b" (dark) or "clean" (light)
        language: str = "en"  # Language code for non-Latin script handling
    ) -> Dict[str, Any]:
        """Generate a video for a single section
        
        Args:
            section: Section data with title, narration, visual_description, etc.
            output_dir: Directory to save output files
            section_index: Index of this section
            audio_duration: Actual audio duration in seconds (if audio was pre-generated)
            style: Visual style - "3b1b" for dark theme, "clean" for light theme
            language: Language code for proper text/LaTeX handling
        
        Returns:
            Dict with video_path and manim_code
        """
        
        # Use audio duration as the target if available, otherwise fall back to estimated
        target_duration = audio_duration if audio_duration else section.get("duration_seconds", 60)
        section["target_duration"] = target_duration
        section["language"] = language  # Pass language to code generation
        section["style"] = style  # Pass style to code generation
        
        # Generate Manim code using Gemini
        manim_code = await self._generate_manim_code(section, target_duration)
        
        # Write the code to a temp file
        section_id = section.get("id", f"section_{section_index}").replace("-", "_").replace(" ", "_")
        scene_name = f"Section{section_id.title().replace('_', '')}"
        
        code_file = Path(output_dir) / f"scene_{section_index}.py"
        
        # Create the full scene file
        full_code = self._create_scene_file(manim_code, section_id, target_duration)
        
        with open(code_file, "w") as f:
            f.write(full_code)
        
        # Render the scene (with auto-correction support)
        output_video = await self._render_scene(
            code_file, 
            scene_name, 
            output_dir, 
            section_index,
            section=section  # Pass section for error correction context
        )
        
        # Re-read the final code (may have been corrected during rendering)
        with open(code_file, "r") as f:
            final_code = f.read()
        
        # Return video path and manim code path (store path, not code content)
        return {
            "video_path": output_video,
            "manim_code": final_code,  # Keep for backward compatibility
            "manim_code_path": str(code_file)  # Store path for script.json
        }
    
    async def render_from_code(
        self,
        manim_code: str,
        output_dir: str,
        section_index: int = 0
    ) -> Optional[str]:
        """Render a Manim scene from existing code (e.g., translated code)
        
        Args:
            manim_code: Complete Manim Python code to render
            output_dir: Directory to save output files
            section_index: Index for naming the output file
        
        Returns:
            Path to rendered video, or None if rendering failed
        """
        import re
        
        # Validate the code has basic structure
        if not manim_code or len(manim_code.strip()) < 50:
            print(f"[ManimGenerator] Code too short or empty, skipping render")
            return None
        
        # Fix common translation issues
        manim_code = self._fix_translated_code(manim_code)
        
        # Ensure imports are present
        if "from manim import" not in manim_code and "import manim" not in manim_code:
            manim_code = "from manim import *\n\n" + manim_code
        
        # Extract scene name from code
        match = re.search(r"class\s+(\w+)\s*\(\s*Scene\s*\)", manim_code)
        if not match:
            print(f"[ManimGenerator] No Scene class found in code, skipping render")
            return None
        scene_name = match.group(1)
        
        # Write the code to a file
        code_file = Path(output_dir) / f"scene.py"
        
        with open(code_file, "w") as f:
            f.write(manim_code)
        
        # Check for Python syntax errors before rendering
        try:
            compile(manim_code, str(code_file), 'exec')
        except SyntaxError as e:
            print(f"[ManimGenerator] Syntax error in translated code: {e}")
            return None
        
        # Render
        output_path = Path(output_dir) / f"section_{section_index}.mp4"
        
        cmd = [
            "manim",
            "-ql",  # Low quality for faster rendering
            "--format=mp4",
            f"--output_file=section_{section_index}",
            f"--media_dir={output_dir}",
            str(code_file),
            scene_name
        ]
        
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                # Log more helpful error info
                stderr = result.stderr
                if "Error" in stderr or "Exception" in stderr:
                    # Find the actual error message
                    lines = stderr.split('\n')
                    error_lines = [l for l in lines if 'Error' in l or 'Exception' in l or 'error' in l.lower()]
                    if error_lines:
                        print(f"[ManimGenerator] Render error: {error_lines[-1][:200]}")
                    else:
                        print(f"[ManimGenerator] Render failed with exit code {result.returncode}")
                else:
                    print(f"[ManimGenerator] Render failed: {stderr[:300]}")
                return None
            
            # Find the rendered video (Manim puts it in a subdirectory)
            video_subdir = Path(output_dir) / "videos" / "scene" / "480p15"
            if video_subdir.exists():
                for video_file in video_subdir.glob("*.mp4"):
                    return str(video_file)
            
            # Also check direct output
            if output_path.exists():
                return str(output_path)
            
            # Check other possible locations
            for subdir in Path(output_dir).rglob("*.mp4"):
                return str(subdir)
            
            print(f"[ManimGenerator] Video file not found in expected locations")
            return None
            
        except subprocess.TimeoutExpired:
            print(f"[ManimGenerator] Render timed out after 300 seconds")
            return None
        except Exception as e:
            print(f"[ManimGenerator] Render exception: {e}")
            return None
    
    def _fix_translated_code(self, code: str) -> str:
        """Fix common issues in translated Manim code"""
        import re
        
        lines = code.split('\n')
        fixed_lines = []
        
        for i, line in enumerate(lines):
            # Fix: First line is a bare comment without quotes (should be docstring or comment)
            # Pattern: starts with text like "Auto-generated..." without # or """
            if i == 0 and line.strip() and not line.strip().startswith(('#', '"', "'", 'from', 'import')):
                # Check if it looks like a docstring that lost its quotes
                if 'auto-generated' in line.lower() or 'manim scene' in line.lower() or 'section:' in line.lower():
                    fixed_lines.append(f'"""{line}"""')
                    continue
                # Otherwise make it a comment
                elif not line.strip().startswith('class'):
                    fixed_lines.append(f'# {line}')
                    continue
            
            # Fix: Unquoted text that should be a comment
            # (lines that are just plain text, not code)
            stripped = line.strip()
            if stripped and i < 5:  # Only check first few lines
                # If it's not a valid Python start and not empty
                if not stripped.startswith(('#', '"', "'", 'from', 'import', 'class', 'def', '@', '"""')):
                    if not any(c in stripped for c in ['=', '(', ')', '[', ']', ':', '+', '-', '*', '/']):
                        # Looks like plain text, make it a comment
                        fixed_lines.append(f'# {line}')
                        continue
            
            fixed_lines.append(line)
        
        result = '\n'.join(fixed_lines)
        
        # Ensure the code starts with proper import if missing
        if 'from manim import' not in result and 'import manim' not in result:
            # Find where to insert import (after any docstrings/comments at top)
            insert_pos = 0
            for i, line in enumerate(fixed_lines):
                stripped = line.strip()
                if stripped and not stripped.startswith(('#', '"""', "'''")):
                    if not (stripped.startswith('"""') or stripped.endswith('"""')):
                        insert_pos = i
                        break
            
            fixed_lines.insert(insert_pos, 'from manim import *\n')
            result = '\n'.join(fixed_lines)
        
        return result
    
    async def _generate_manim_code(self, section: Dict[str, Any], target_duration: float) -> str:
        """Use Gemini to generate Manim code for a section"""
        
        # Calculate timing - audio is already generated, we know exact duration
        audio_duration = target_duration
        
        # Count pause markers in narration to estimate natural break points
        narration = section.get('narration', '')
        
        # Build subsection timing breakdown from narration_segments
        narration_segments = section.get('narration_segments', [])
        subsection_timing_lines = []
        cumulative_time = 0.0
        for seg in narration_segments:
            seg_duration = seg.get('estimated_duration', 7.0)
            start_time = cumulative_time
            end_time = cumulative_time + seg_duration
            seg_text = seg.get('text', '')[:80]
            subsection_timing_lines.append(
                f"  Segment {seg.get('segment_index', 0) + 1}: [{start_time:.1f}s - {end_time:.1f}s] ({seg_duration:.1f}s) \"{seg_text}...\""
            )
            cumulative_time = end_time
        subsection_timing_str = "\n".join(subsection_timing_lines) if subsection_timing_lines else "No subsection timing available"
        
        # Get style and language settings
        style = section.get('style', '3b1b')
        language = section.get('language', 'en')
        animation_type = section.get('animation_type', 'text')
        key_concepts = section.get('key_concepts', section.get('key_equations', []))
        
        # Language-specific instructions for non-Latin scripts
        language_instructions = self._get_language_instructions(language)
        
        # Style-specific instructions - support multiple themes
        style_configs = {
            '3b1b': {
                'instructions': """
VISUAL STYLE: 3BLUE1BROWN (DARK THEME)
- Dark background (default Manim - #1a1a2e)
- Text color: WHITE (default)
- Primary accent: BLUE (#3b82f6)
- Secondary accent: YELLOW (#fbbf24)
- Highlight: GREEN, RED for emphasis
- Elegant mathematical animations with smooth transitions
- Example: Text("Title", font_size=48)"""
            },
            'clean': {
                'instructions': """
VISUAL STYLE: CLEAN/LIGHT THEME
- Use WHITE background: self.camera.background_color = WHITE
- Text color: BLACK or DARK_GRAY
- Primary: BLUE (#2563eb)
- Secondary: GREEN (#059669)
- Accent: RED (#dc2626) for emphasis
- Clean, minimalist look suitable for presentations
- Example: Text("Title", color=BLACK, font_size=48)"""
            },
            'dracula': {
                'instructions': """
VISUAL STYLE: DRACULA (DARK PURPLE THEME)
- Dark purple background: self.camera.background_color = "#282a36"
- Text color: "#f8f8f2" (off-white)
- Primary: "#bd93f9" (purple)
- Secondary: "#8be9fd" (cyan)
- Accent: "#ff79c6" (pink), "#50fa7b" (green)
- Moody, stylish aesthetic - popular in programming
- Example: Text("Title", color="#f8f8f2", font_size=48)"""
            },
            'solarized': {
                'instructions': """
VISUAL STYLE: SOLARIZED (WARM PROFESSIONAL)
- Warm dark background: self.camera.background_color = "#002b36"
- Text color: "#839496" (light gray-blue)
- Primary: "#268bd2" (blue)
- Secondary: "#2aa198" (cyan)
- Accent: "#b58900" (yellow), "#cb4b16" (orange)
- Professional, easy on the eyes
- Example: Text("Title", color="#839496", font_size=48)"""
            },
            'nord': {
                'instructions': """
VISUAL STYLE: NORD (ARCTIC COOL)
- Cool dark background: self.camera.background_color = "#2e3440"
- Text color: "#eceff4" (snow white)
- Primary: "#88c0d0" (frost blue)
- Secondary: "#81a1c1" (steel blue)
- Accent: "#bf616a" (aurora red), "#a3be8c" (aurora green)
- Cool, calming Nordic aesthetic
- Example: Text("Title", color="#eceff4", font_size=48)"""
            }
        }
        
        style_config = style_configs.get(style, style_configs['3b1b'])
        style_instructions = style_config['instructions']
        
        # Animation type specific instructions - now includes static and mixed
        animation_guidance = {
            'equation': "Focus on mathematical equations with MathTex. Highlight terms, transform equations step-by-step.",
            'text': "Use Text objects for explanations. Fade in key points one by one.",
            'diagram': "Create shapes, arrows, and diagrams to illustrate concepts.",
            'code': "Show code snippets with Code() or Text() with monospace font. Highlight important lines.",
            'graph': "Create axes with Axes(), plot functions, show data relationships.",
            'process': "Show step-by-step processes with arrows connecting stages.",
            'comparison': "Show side-by-side comparisons with clear visual distinction.",
            'static': """STATIC SCENE - minimal animation, focus on displaying content:
- Display text/equations that STAY on screen while narrator explains
- Use simple FadeIn animations, then long self.wait() calls
- No complex transformations - let the narration do the explaining
- Example: Show title, then bullet points one by one, then wait
- Most time should be self.wait() while content is displayed""",
            'mixed': """MIXED SCENE - combine static displays with some animation:
- Start with static elements (title, context)
- Add some animated elements for key points
- Balance: 40% animation, 60% static display with waits"""
        }
        type_guidance = animation_guidance.get(animation_type, animation_guidance['text'])
        
        # Build timing context - combine segment info into one clear section
        is_unified_section = section.get('is_unified_section', False)
        is_segment = section.get('is_segment', False)
        
        timing_context = ""
        if is_unified_section:
            # Unified section with multiple segments
            segment_timing = section.get('segment_timing', [])
            timing_lines = [f"  [{s['start_time']:.1f}s-{s['end_time']:.1f}s] \"{s['text'][:60]}...\"" for s in segment_timing]
            timing_context = "\n".join(timing_lines) if timing_lines else subsection_timing_str
        elif is_segment:
            # Individual segment
            seg_idx = section.get('segment_index', 0)
            total_segs = section.get('total_segments', 1)
            is_first = seg_idx == 0
            is_last = seg_idx == total_segs - 1
            timing_context = f"Segment {seg_idx + 1}/{total_segs}. {'Include title.' if is_first else 'No intro.'} {'Add conclusion.' if is_last else 'Continues to next.'}"
        else:
            timing_context = subsection_timing_str
        
        prompt = f"""Generate Manim code for construct(self). Output ONLY Python code.

SECTION: {section.get('title', 'Untitled')}
DURATION: {audio_duration:.1f}s (STRICT - animations + waits must sum to this)
TYPE: {animation_type} - {type_guidance}

NARRATION (sync visuals to this):
{narration}

TIMING BREAKDOWN:
{timing_context}

KEY CONCEPTS: {key_concepts}

{language_instructions}
{style_instructions}

LAYOUT GUIDELINES (CRITICAL - AVOID OVERLAPS):
1. **Vertical Stacking**: When placing elements below others, use `buff=0.7` or larger. `buff=0.2` is too small.
   - Good: `text2.next_to(text1, DOWN, buff=0.8)`
2. **Buffer Zones**: Keep away from screen edges.
   - Good: `.to_edge(UP, buff=1.0)`
3. **Clear Before New**: Don't let text accumulate. Use `ReplacementTransform` or `FadeOut` old content before showing new content unless it's a list.
4. **Scale Control**: If equations are long, use `.scale(0.85)` immediately.

SIZES: title font_size=36, body=28, labels=24, equations .scale(0.85)

COMMON PATTERNS:
- Text list: VGroup(Text("• Item 1"), Text("• Item 2")).arrange(DOWN, buff=0.5, aligned_edge=LEFT)
- Equations: MathTex(r"x = 3").scale(0.85), use ReplacementTransform for step-by-step
- Graph: Axes(x_range, y_range, x_length=6, y_length=4), then axes.plot(lambda x: ...)
- Highlight: obj.animate.set_color(YELLOW)

SYNTAX:
- 8 spaces indent inside construct(), +4 for each nested block
- MathTex uses raw strings: r"\\frac{{a}}{{b}}"
- Double braces in f-strings: axis_config={{"include_tip": True}}

OUTPUT: Python code only. No markdown. No explanations."""

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.7,  # Balanced creativity for code generation
                        top_p=0.95,
                        top_k=40
                    )
                ),
                timeout=300  # 5 minute timeout for Gemini API
            )
            
            # Track token usage
            self._track_token_usage(response, self.MODEL)
            
        except asyncio.TimeoutError:
            print(f"[ManimGenerator] Gemini API timed out for section code generation")
            # Return minimal fallback code
            return '''        text = Text("Section", font_size=48)
        self.play(Write(text))
        self.wait(2)'''
        except Exception as e:
            print(f"[ManimGenerator] Gemini API error: {e}")
            return '''        text = Text("Section", font_size=48)
        self.play(Write(text))
        self.wait(2)'''
        
        code = response.text.strip()
        
        # Clean up the code
        code = self._clean_code(code)
        
        return code
    
    def _get_language_instructions(self, language: str) -> str:
        """Get language-specific instructions for Manim code generation"""
        
        # Non-Latin scripts need special handling
        non_latin_scripts = {
            'hy': 'Armenian',
            'ar': 'Arabic',
            'he': 'Hebrew',
            'zh': 'Chinese',
            'ja': 'Japanese',
            'ko': 'Korean',
            'ru': 'Russian',
            'el': 'Greek',
            'th': 'Thai',
            'hi': 'Hindi',
            'bn': 'Bengali',
            'ta': 'Tamil',
            'te': 'Telugu',
            'ml': 'Malayalam',
            'kn': 'Kannada',
            'gu': 'Gujarati',
            'pa': 'Punjabi',
            'mr': 'Marathi',
        }
        
        if language in non_latin_scripts:
            script_name = non_latin_scripts[language]
            return f"""
═══════════════════════════════════════════════════════════════════════════════
{script_name.upper()} TEXT - USE SMALLER FONTS
═══════════════════════════════════════════════════════════════════════════════

Content is in {script_name}. Rules:
1. NEVER mix {script_name} text with LaTeX in same object
2. Use Text() for {script_name}: Text("text here", font_size=28)
3. Use MathTex() ONLY for math: MathTex(r"x^2 + y^2")
4. Position separately with .next_to()

FONT SIZES for {script_name}:
- Titles: font_size=32 (smaller than usual)
- Body: font_size=26
- Labels: font_size=22
- Always add .scale(0.8) if content is wide

SIMPLE PATTERN:
        title = Text("Title in {script_name}", font_size=32)
        title.to_edge(UP, buff=0.5)
        
        eq = MathTex(r"x = 2").scale(0.9)
        eq.move_to(ORIGIN)
        
        label = Text("Explanation", font_size=26)
        label.next_to(eq, DOWN, buff=0.6)
"""
        elif language != 'en':
            # Latin script but non-English (French, German, Spanish, etc.)
            return f"""
═══════════════════════════════════════════════════════════════════════════════
NOTE: NON-ENGLISH LATIN TEXT
═══════════════════════════════════════════════════════════════════════════════
Text is in a non-English language. Remember:
- Text() handles accented characters fine: Text("Théorème", font_size=36)
- MathTex is ONLY for math notation: MathTex(r"\\frac{{x}}{{y}}")
- NEVER put non-math text inside MathTex - use Text() for words
- Keep math and text as separate objects positioned with .next_to()
"""
        else:
            return ""  # No special instructions for English
    
    def _clean_code(self, code: str) -> str:
        """Clean up generated code while preserving nested indentation"""
        
        # Remove markdown code blocks
        if code.startswith("```"):
            lines = code.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            code = "\n".join(lines)
        
        # Remove any class definitions or imports that might have slipped in
        lines = code.split("\n")
        cleaned_lines = []
        skip_until_construct = False
        in_construct = False
        
        for line in lines:
            stripped = line.strip()
            # Skip import lines
            if stripped.startswith("from manim") or stripped.startswith("import"):
                continue
            # Skip class definition
            if stripped.startswith("class "):
                skip_until_construct = True
                continue
            if skip_until_construct:
                if "def construct" in line:
                    skip_until_construct = False
                    in_construct = True
                continue
            cleaned_lines.append(line)
        
        code = "\n".join(cleaned_lines)
        
        # Normalize indentation while PRESERVING relative indentation
        lines = code.split("\n")
        
        # Find the minimum non-zero indentation to understand the base level
        min_indent = float('inf')
        for line in lines:
            if line.strip():
                # Replace tabs with 4 spaces for counting
                normalized_line = line.replace('\t', '    ')
                indent = len(normalized_line) - len(normalized_line.lstrip())
                if indent > 0:
                    min_indent = min(min_indent, indent)
        
        if min_indent == float('inf'):
            min_indent = 0
        
        # Re-indent: shift everything so base level is 8 spaces (inside construct)
        indented_lines = []
        for line in lines:
            if line.strip():
                # Replace tabs with 4 spaces
                normalized_line = line.replace('\t', '    ')
                current_indent = len(normalized_line) - len(normalized_line.lstrip())
                content = normalized_line.lstrip()
                
                # Calculate relative indentation (how many levels above base)
                if min_indent > 0:
                    relative_indent = current_indent - min_indent
                else:
                    relative_indent = current_indent
                
                # New indent: 8 spaces (base) + relative indentation
                new_indent = 8 + max(0, relative_indent)
                indented_lines.append(" " * new_indent + content)
            else:
                indented_lines.append("")
        
        return "\n".join(indented_lines)
    
    def _normalize_indentation(self, code: str) -> str:
        """Normalize indentation to use consistent 4-space indentation
        
        This fixes common issues:
        - Tabs converted to 4 spaces
        - Mixed tabs/spaces normalized
        - Inconsistent indentation levels fixed
        """
        lines = code.split('\n')
        normalized_lines = []
        
        for line in lines:
            if not line.strip():
                # Empty line
                normalized_lines.append('')
                continue
            
            # Count leading whitespace
            stripped = line.lstrip()
            leading = line[:len(line) - len(stripped)]
            
            # Replace tabs with 4 spaces
            leading = leading.replace('\t', '    ')
            
            # Count the indentation level (how many 4-space units)
            # Handle cases where spaces might not be exact multiples of 4
            space_count = len(leading)
            indent_level = (space_count + 2) // 4  # Round to nearest 4
            
            # Reconstruct with clean 4-space indentation
            normalized_lines.append('    ' * indent_level + stripped)
        
        return '\n'.join(normalized_lines)
    
    def _create_scene_file(self, code: str, section_id: str, duration: float) -> str:
        """Create a complete Manim scene file with minimum duration padding"""
        
        # Normalize indentation to fix any tab/space issues from AI generation
        normalized_code = self._normalize_indentation(code)
        
        # Ensure the code has proper base indentation for inside construct()
        # The code should already have 8 spaces, but let's make sure
        lines = normalized_code.split('\n')
        indented_lines = []
        for line in lines:
            if line.strip():
                # Ensure minimum 8-space indentation (inside construct method)
                current_indent = len(line) - len(line.lstrip())
                if current_indent < 8:
                    # Add base indentation to reach 8 spaces for construct body
                    line = '        ' + line.lstrip()
            indented_lines.append(line)
        normalized_code = '\n'.join(indented_lines)
        
        # Sanitize section_id for class name
        class_name = "".join(word.title() for word in section_id.split("_"))
        
        # Add extra wait time at the end to ensure we meet minimum duration
        # This acts as a safety buffer - the actual animations might be shorter
        padding_wait = max(2, duration * 0.15)  # At least 2 seconds or 15% of duration
        
        scene_code = f'''"""Auto-generated Manim scene for section: {section_id}"""
from manim import *

class Scene{class_name}(Scene):
    def construct(self):
        # Target duration: {duration:.1f} seconds (synced with audio)
        # The animation should match or exceed this duration
        
{normalized_code}
        
        # Padding to ensure minimum duration matches audio
        # This ensures the video is at least as long as the narration
        self.wait({padding_wait:.1f})
'''
        return scene_code
    
    async def _render_scene(
        self,
        code_file: Path,
        scene_name: str,
        output_dir: str,
        section_index: int,
        section: Dict[str, Any] = None,
        attempt: int = 0,
        qc_iteration: int = 0
    ) -> Optional[str]:
        """Render a Manim scene to video with auto-correction on errors and visual QC"""
        
        output_path = Path(output_dir) / f"section_{section_index}.mp4"
        
        # Get the actual class name from the file
        with open(code_file, "r") as f:
            content = f.read()
        
        # Extract class name
        import re
        match = re.search(r"class (\w+)\(Scene\)", content)
        if match:
            scene_name = match.group(1)
        
        # Build manim command
        cmd = [
            "manim",
            "-ql",  # Low quality for faster rendering (change to -qh for high quality)
            "--format=mp4",
            f"--output_file=section_{section_index}",
            f"--media_dir={output_dir}",
            str(code_file),
            scene_name
        ]
        
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout per section
            )
            
            if result.returncode != 0:
                qc_note = f" (QC iteration {qc_iteration})" if qc_iteration > 0 else ""
                print(f"[ManimGenerator] Render error for section {section_index}{qc_note} (attempt {attempt + 1}):")
                # Print last 1500 chars of error to avoid flooding
                print(result.stderr[-1500:] if len(result.stderr) > 1500 else result.stderr)
                
                # Try auto-correction if we haven't exceeded max attempts
                if attempt < self.MAX_CORRECTION_ATTEMPTS and section:
                    print(f"[ManimGenerator] Attempting auto-correction (attempt {attempt + 1}/{self.MAX_CORRECTION_ATTEMPTS})...")
                    corrected_code = await self._correct_manim_code(
                        content, 
                        result.stderr, 
                        section,
                        attempt=attempt  # Pass attempt number for model selection
                    )
                    
                    if corrected_code:
                        # Overwrite the original file with corrected code (no versioning)
                        with open(code_file, "w") as f:
                            f.write(corrected_code)
                        
                        # Try rendering again with corrected code (same file)
                        return await self._render_scene(
                            code_file, 
                            scene_name, 
                            output_dir, 
                            section_index,
                            section,
                            attempt + 1,
                            qc_iteration  # Keep same QC iteration
                        )
                
                # Fall back to simple scene if all corrections failed
                print(f"[ManimGenerator] All correction attempts failed, using fallback scene")
                return await self._render_fallback_scene(section_index, output_dir, code_file.parent)
            
            # Find the actual output file
            video_dir = Path(output_dir) / "videos" / code_file.stem / "480p15"
            rendered_video = None
            
            if video_dir.exists():
                videos = list(video_dir.glob("*.mp4"))
                if videos:
                    rendered_video = str(videos[0])
            
            # Try alternate paths if not found
            if not rendered_video:
                for pattern in ["**/*.mp4"]:
                    videos = list(Path(output_dir).glob(pattern))
                    if videos:
                        rendered_video = str(videos[0])
                        break
            
            if not rendered_video:
                print(f"Could not find rendered video for section {section_index}")
                return None
            
            # ═══════════════════════════════════════════════════════════════
            # VISUAL QUALITY CONTROL - Check rendered video for visual issues
            # ═══════════════════════════════════════════════════════════════
            if self.visual_qc and section and qc_iteration < self.MAX_QC_ITERATIONS:
                print(f"[ManimGenerator] Running Visual QC (iteration {qc_iteration + 1}/{self.MAX_QC_ITERATIONS})...")
                
                try:
                    # Check if model is available
                    if not await self.visual_qc.check_model_available():
                        print("[ManimGenerator] Visual QC model not available, skipping QC")
                    else:
                        # Run visual quality check with video-based analysis
                        qc_result = await self.visual_qc.check_video_quality(
                            rendered_video,
                            section,
                            qc_iteration=qc_iteration
                        )
                        
                        # Clean up temporary video after analysis
                        if qc_result.get("temp_video_path"):
                            self.visual_qc.cleanup_frames(temp_video_path=qc_result["temp_video_path"])
                        
                        # Check if issues were found
                        if qc_result.get("status") == "issues" and qc_result.get("error_report"):
                            error_report = qc_result.get("error_report")
                            print(f"[ManimGenerator] Found visual issues:")
                            for line in error_report.split('\n'):
                                print(f"[ManimGenerator]   {line}")
                            
                            # Generate fixed code using Gemini - pass section for context
                            print(f"[ManimGenerator] Generating visual fix...")
                            fixed_code = await self._generate_visual_fix(
                                content,
                                error_report,
                                section=section
                            )
                            
                            if fixed_code:
                                print(f"[ManimGenerator] Applying visual QC fix and re-rendering...")
                                
                                # Save the fixed code
                                with open(code_file, "w") as f:
                                    f.write(fixed_code)
                                
                                # Re-render with fixed code
                                # attempt=0 allows syntax error correction if needed
                                return await self._render_scene(
                                    code_file,
                                    scene_name,
                                    output_dir,
                                    section_index,
                                    section,
                                    attempt=0,  # Reset - allows syntax error correction
                                    qc_iteration=qc_iteration + 1  # Increment QC iteration
                                )
                            else:
                                print("[ManimGenerator] Failed to generate visual fix, using current video")
                        else:
                            print(f"[ManimGenerator] ✅ Visual QC passed")
                
                except Exception as qc_error:
                    print(f"[ManimGenerator] Visual QC error (non-fatal): {qc_error}")
                    # Continue with the rendered video even if QC fails
            
            return rendered_video
            
        except subprocess.TimeoutExpired:
            print(f"Manim rendering timed out for section {section_index}")
            return await self._render_fallback_scene(section_index, output_dir, code_file.parent)
        except Exception as e:
            print(f"Error rendering section {section_index}: {e}")
            return await self._render_fallback_scene(section_index, output_dir, code_file.parent)
    
    async def _correct_manim_code(
        self,
        original_code: str,
        error_message: str,
        section: Dict[str, Any],
        attempt: int = 0
    ) -> Optional[str]:
        """Use Gemini to fix errors in the Manim code
        
        On the last attempt (attempt == MAX_CORRECTION_ATTEMPTS - 1), uses a stronger model.
        """
        
        # Use stronger model on last attempt
        is_last_attempt = attempt >= self.MAX_CORRECTION_ATTEMPTS - 1
        model_to_use = self.STRONG_MODEL if is_last_attempt else self.CORRECTION_MODEL
        
        if is_last_attempt:
            print(f"[ManimGenerator] Using stronger model ({self.STRONG_MODEL}) for final fix attempt")
        
        # Build timing context for fix
        timing_context = ""
        if section.get('is_unified_section', False):
            segment_timing = section.get('segment_timing', [])
            timing_lines = [f"  [{s['start_time']:.1f}s-{s['end_time']:.1f}s] \"{s['text'][:60]}...\"" for s in segment_timing]
            if timing_lines:
                timing_context = "\nTIMING INSTRUCTIONS (sync visuals to audio):\n" + "\n".join(timing_lines)
        
        # System instruction with Manim CE reference
        system_instruction = """You are an expert Manim Community Edition (manim) programmer and debugger.
Your task is to fix Python code errors in Manim animations.

MANIM CE QUICK REFERENCE:

DIRECTION CONSTANTS (use these, NOT "BOTTOM"):
- UP, DOWN, LEFT, RIGHT (unit vectors)
- UL, UR, DL, DR (diagonals: upper-left, upper-right, etc.)
- ORIGIN (center point)
- IN, OUT (for 3D scenes only)
NOTE: There is NO "BOTTOM" constant! Use DOWN instead.

COLOR CONSTANTS (uppercase):
- RED, GREEN, BLUE, YELLOW, ORANGE, PURPLE, PINK, WHITE, BLACK, GRAY/GREY
- Variants: LIGHT_GRAY, DARK_GRAY, BLUE_A, BLUE_B, BLUE_C, BLUE_D, BLUE_E
- TEAL, MAROON, GOLD, etc.

POSITIONING METHODS:
- .to_edge(UP/DOWN/LEFT/RIGHT, buff=0.5) - move to screen edge
- .to_corner(UL/UR/DL/DR, buff=0.5) - move to corner
- .next_to(obj, UP/DOWN/LEFT/RIGHT, buff=0.25) - position relative to another object
- .move_to(point or obj) - move center to position
- .shift(direction * amount) - relative movement
- .align_to(obj, direction) - align edges

COMMON MOBJECTS:
- Text("string", font_size=48) - regular text
- MathTex(r"\\frac{a}{b}") - LaTeX math (double backslashes!)
- Tex(r"Text with $math$") - mixed text and math
- Circle(), Square(), Rectangle(), Triangle(), Polygon()
- Line(start, end), Arrow(start, end), DashedLine()
- Dot(), NumberLine(), Axes(), NumberPlane()
- VGroup(*mobjects) - group multiple objects
- SurroundingRectangle(obj), Brace(obj, direction)

ANIMATIONS:
- Create(mobject), Write(mobject), FadeIn(mobject), FadeOut(mobject)
- Transform(source, target), ReplacementTransform(source, target)
- Indicate(mobject), Circumscribe(mobject), Flash(mobject)
- GrowFromCenter(mobject), GrowArrow(arrow)
- self.play(animation, run_time=1) - play animation
- self.wait(seconds) - pause
- self.add(mobject) - add without animation
- self.remove(mobject) - remove without animation

ANIMATE SYNTAX (for property changes):
- obj.animate.shift(UP)
- obj.animate.scale(2)
- obj.animate.set_color(RED)
- obj.animate.move_to(ORIGIN)
- Can chain: obj.animate.shift(UP).scale(0.5)

COMMON ERRORS TO FIX:
1. "BOTTOM" is not defined → Use DOWN instead
2. "TOP" is not defined → Use UP instead  
3. IndentationError → Use 8 spaces inside construct()
4. NameError for colors → Use uppercase: BLUE not blue
5. MathTex needs double backslashes: r"\\frac{a}{b}"
6. VGroup elements must be Mobjects, not strings
7. self.play() needs animations, not raw Mobjects
8. Objects must be added before FadeOut

OUTPUT: Return ONLY the complete fixed Python code. No markdown, no explanations."""

        prompt = f"""Fix the following Manim code error:

ORIGINAL CODE:
```python
{original_code}
```

ERROR MESSAGE:
```
{error_message[-2000:]}
```

SECTION CONTEXT:
- Title: {section.get('title', 'Untitled')}
- Visual: {section.get('visual_description', '')[:300]}
{timing_context}

Analyze the error and fix the code. Return ONLY the complete corrected Python file."""

        try:
            # Use stronger model on last attempt, lighter model otherwise
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=model_to_use,
                contents=[
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=prompt)]
                    )
                ],
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.1,  # Low temperature for reliable fixes
                    max_output_tokens=8192
                )
            )
            
            # Track token usage
            self._track_token_usage(response, model_to_use)
            
            if not response or not response.text:
                print("[ManimGenerator] Empty response from correction model")
                return None
            
            corrected = response.text.strip()
            
            # Remove markdown if present
            if corrected.startswith("```"):
                lines = corrected.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                corrected = "\n".join(lines)
            
            # Validate it has the basic structure
            if "from manim import" in corrected and "class " in corrected and "def construct" in corrected:
                return corrected
            else:
                print("Corrected code missing basic Manim structure")
                return None
                
        except Exception as e:
            print(f"Error during code correction: {e}")
            return None
    
    async def _generate_visual_fix(
        self,
        original_code: str,
        error_report: str,
        section: Dict[str, Any] = None
    ) -> Optional[str]:
        """Generate fixed Manim code based on visual QC error report using Gemini
        
        This method generates a fix for visual layout issues. The returned code
        will be validated through the normal render pipeline which handles
        syntax errors automatically.
        
        Args:
            original_code: The original Manim code that has visual issues
            error_report: Concatenated error descriptions with timestamps
            section: Section info for context
        
        Returns:
            Fixed Manim code, or None if fix generation failed
        """
        if not error_report:
            return None
        
        # Extract section context
        section_title = section.get('title', 'Untitled') if section else 'Untitled'
        duration = section.get('duration_seconds', section.get('duration', 30)) if section else 30
        narration = section.get('narration', section.get('tts_narration', ''))[:500] if section else ''
        
        # Build timing context for fix
        timing_context = ""
        if section and section.get('is_unified_section', False):
            segment_timing = section.get('segment_timing', [])
            timing_lines = [f"  [{s['start_time']:.1f}s-{s['end_time']:.1f}s] \"{s['text'][:60]}...\"" for s in segment_timing]
            if timing_lines:
                timing_context = "\nTIMING BREAKDOWN (sync visuals to audio):\n" + "\n".join(timing_lines)
        elif section and section.get('narration_segments'):
            segments = section.get('narration_segments', [])
            cumulative = 0.0
            timing_lines = []
            for seg in segments:
                seg_dur = seg.get('estimated_duration', seg.get('duration', 5))
                seg_text = seg.get('text', seg.get('tts_text', ''))[:60]
                timing_lines.append(f"  [{cumulative:.1f}s-{cumulative + seg_dur:.1f}s] \"{seg_text}...\"")
                cumulative += seg_dur
            if timing_lines:
                timing_context = "\nTIMING BREAKDOWN (sync visuals to audio):\n" + "\n".join(timing_lines)

        prompt = f"""You are an expert Manim (Community Edition) programmer. Your task is to fix VISUAL LAYOUT ERRORS in the code below.

SECTION: {section_title}
TARGET DURATION: {duration} seconds

NARRATION (for context):
{narration}
{timing_context}

ORIGINAL MANIM CODE WITH VISUAL ISSUES:
```python
{original_code}
```

VISUAL ERRORS DETECTED BY QC SYSTEM:
{error_report}

YOUR TASK: Fix ONLY the visual layout errors while preserving:
1. The same educational content
2. The same animations and transitions  
3. The same total duration (~{duration}s)
4. The same code structure

SPECIFIC FIXES TO APPLY:

**FOR OVERLAPS:**
- Increase vertical spacing: `.next_to(obj, DOWN, buff=0.8)` instead of default
- Use `.arrange(DOWN, buff=0.6, aligned_edge=LEFT)` for VGroups
- Clear old content: `self.play(FadeOut(old_stuff))` before adding new content
- Use `ReplacementTransform` instead of `Transform` when replacing content

**FOR OVERFLOW/CLIPPING:**
- Scale down large elements: `.scale(0.8)` or `.scale(0.7)`
- Use safe margins: `.to_edge(LEFT, buff=1.0)` not `buff=0.5`
- Break long text into multiple lines with VGroup
- Center properly: `.move_to(ORIGIN)` or `.to_edge(UP, buff=0.8)`

**FOR LAYOUT ISSUES:**
- Ensure proper spacing between all elements
- Check that nothing goes off-screen (frame is roughly -7 to +7 horizontal, -4 to +4 vertical)

CRITICAL REQUIREMENTS:
- Output ONLY valid Python code - no markdown, no explanations
- Include all imports: `from manim import *`
- Keep the same class name and structure
- Use 8-space indentation inside `construct()`
- The code must compile and run without errors

OUTPUT: Complete fixed Python file only."""

        try:
            # Use STRONG_MODEL for visual fixes
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.STRONG_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,  # Lower temperature for more reliable fixes
                    max_output_tokens=8192  # Allow for longer code
                )
            )
            
            # Track token usage (with error handling)
            try:
                self._track_token_usage(response, self.STRONG_MODEL)
            except Exception as track_err:
                print(f"[ManimGenerator] Warning: Could not track token usage: {track_err}")
            
            # Check if response has text
            if not response or not response.text:
                print(f"[ManimGenerator] Visual fix: Empty response from Gemini")
                # Check for safety/block reasons
                if hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'finish_reason'):
                        print(f"[ManimGenerator] Finish reason: {candidate.finish_reason}")
                return None
            
            fixed_code = response.text.strip()
            
            if not fixed_code:
                print(f"[ManimGenerator] Visual fix: Response text is empty")
                return None
            
            # Remove markdown code blocks if present
            if fixed_code.startswith("```"):
                lines = fixed_code.split("\n")
                # Remove first line if it's ```python or ```
                if lines[0].strip().startswith("```"):
                    lines = lines[1:]
                # Remove last line if it's ```
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                fixed_code = "\n".join(lines)
            
            # Basic validation - must have required structure
            if "from manim import" not in fixed_code:
                fixed_code = "from manim import *\n\n" + fixed_code
            
            if "class " not in fixed_code or "def construct" not in fixed_code:
                print("[ManimGenerator] Visual fix missing required structure")
                return None
            
            # Ensure proper line endings
            fixed_code = fixed_code.replace('\r\n', '\n')
            
            # Test-render the visual fix and correct errors if needed
            fixed_code = await self._validate_and_fix_code(fixed_code, section)
            
            return fixed_code
        
        except Exception as e:
            print(f"[ManimGenerator] Error generating visual fix: {e}")
            return None
    
    async def _validate_and_fix_code(
        self,
        code: str,
        section: Dict[str, Any] = None,
        max_attempts: int = 3
    ) -> Optional[str]:
        """Test-render code and fix any errors (syntax or runtime)
        
        Args:
            code: The Manim code to validate
            section: Section info for context in error fixing
            max_attempts: Maximum correction attempts
            
        Returns:
            Working code or None if unfixable
        """
        import tempfile
        import re
        
        for attempt in range(max_attempts):
            # Extract class name
            match = re.search(r"class (\w+)\(Scene\)", code)
            if not match:
                print(f"[ManimGenerator] No Scene class found in visual fix code")
                return None
            scene_name = match.group(1)
            
            # Create temp file for test render
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_file = f.name
            
            # Create temp output dir
            temp_output = tempfile.mkdtemp(prefix='manim_test_')
            
            try:
                # Try to render
                cmd = [
                    "manim",
                    "-ql",  # Low quality for speed
                    "--format=mp4",
                    f"--media_dir={temp_output}",
                    temp_file,
                    scene_name
                ]
                
                result = await asyncio.to_thread(
                    subprocess.run,
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=120  # 2 minute timeout for test render
                )
                
                if result.returncode == 0:
                    print(f"[ManimGenerator] ✓ Visual fix validated via test render (attempt {attempt + 1})")
                    # Clean up temp files
                    try:
                        os.unlink(temp_file)
                        import shutil
                        shutil.rmtree(temp_output, ignore_errors=True)
                    except:
                        pass
                    return code
                
                # Render failed - extract error and try to fix
                error_msg = result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr
                print(f"[ManimGenerator] Visual fix render error (attempt {attempt + 1}/{max_attempts}):")
                # Print condensed error
                error_lines = [l for l in error_msg.split('\n') if l.strip() and not l.strip().startswith('─')]
                print('\n'.join(error_lines[-10:]))  # Last 10 meaningful lines
                
                if attempt < max_attempts - 1:
                    print(f"[ManimGenerator] Attempting to fix render error...")
                    fixed_code = await self._fix_render_error(code, error_msg, section)
                    
                    if fixed_code:
                        code = fixed_code
                    else:
                        print(f"[ManimGenerator] Could not generate fix, aborting")
                        break
                
            except subprocess.TimeoutExpired:
                print(f"[ManimGenerator] Test render timed out")
                break
            except Exception as e:
                print(f"[ManimGenerator] Test render error: {e}")
                break
            finally:
                # Clean up temp files
                try:
                    os.unlink(temp_file)
                    import shutil
                    shutil.rmtree(temp_output, ignore_errors=True)
                except:
                    pass
        
        print(f"[ManimGenerator] ⚠️ Could not validate visual fix after {max_attempts} attempts")
        return None
    
    async def _fix_render_error(
        self,
        code: str,
        error_message: str,
        section: Dict[str, Any] = None
    ) -> Optional[str]:
        """Fix a render error (syntax or runtime) in the code using Gemini"""
        
        # System instruction with Manim CE reference
        system_instruction = """You are an expert Manim Community Edition debugger.
Fix the error in the provided Manim code.

MANIM CE QUICK REFERENCE:

DIRECTION CONSTANTS (use these, NOT "BOTTOM" or "TOP"):
- UP, DOWN, LEFT, RIGHT (unit vectors)
- UL, UR, DL, DR (diagonals)
- ORIGIN (center)
NOTE: "BOTTOM" and "TOP" do NOT exist! Use DOWN and UP instead.

COLOR CONSTANTS: RED, GREEN, BLUE, YELLOW, WHITE, BLACK, GRAY, etc. (uppercase)

POSITIONING:
- .to_edge(UP/DOWN/LEFT/RIGHT, buff=0.5)
- .next_to(obj, direction, buff=0.25)
- .move_to(point), .shift(direction * amount)

COMMON FIXES:
1. BOTTOM → DOWN, TOP → UP
2. Colors must be uppercase
3. MathTex needs double backslashes: r"\\frac{a}{b}"
4. 8 spaces indentation inside construct()
5. Objects must be added before FadeOut

OUTPUT: Return ONLY the complete fixed Python code. No markdown."""

        prompt = f"""Fix this Manim code error:

CODE:
```python
{code}
```

ERROR:
```
{error_message[-1500:]}
```

Return the complete fixed Python file only."""

        try:
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.CORRECTION_MODEL,
                contents=[
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=prompt)]
                    )
                ],
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.1,
                    max_output_tokens=8192
                )
            )
            
            # Track token usage
            try:
                self._track_token_usage(response, self.CORRECTION_MODEL)
            except Exception:
                pass
            
            if not response or not response.text:
                return None
            
            fixed_code = response.text.strip()
            
            # Remove markdown code blocks if present
            if fixed_code.startswith("```"):
                lines = fixed_code.split("\n")
                if lines[0].strip().startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                fixed_code = "\n".join(lines)
            
            # Ensure proper structure
            if "from manim import" not in fixed_code:
                fixed_code = "from manim import *\n\n" + fixed_code
            
            return fixed_code
        
        except Exception as e:
            print(f"[ManimGenerator] Error fixing render error: {e}")
            return None

    async def _render_fallback_scene(
        self,
        section_index: int,
        output_dir: str,
        code_dir: Path
    ) -> Optional[str]:
        """Render a simple fallback scene if the generated one fails"""
        
        fallback_code = f'''"""Fallback scene"""
from manim import *

class FallbackSection{section_index}(Scene):
    def construct(self):
        text = Text("Section {section_index + 1}", font_size=72)
        self.play(Write(text))
        self.wait(2)
        self.play(FadeOut(text))
'''
        
        fallback_file = code_dir / f"fallback_{section_index}.py"
        with open(fallback_file, "w") as f:
            f.write(fallback_code)
        
        cmd = [
            "manim",
            "-ql",
            "--format=mp4",
            f"--output_file=section_{section_index}",
            f"--media_dir={output_dir}",
            str(fallback_file),
            f"FallbackSection{section_index}"
        ]
        
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=180  # 3 minute timeout for fallback
            )
            
            # Find output
            for pattern in ["**/*.mp4"]:
                videos = list(Path(output_dir).glob(pattern))
                if videos:
                    return str(videos[0])
            
            return None
        except Exception as e:
            print(f"Fallback render also failed: {e}")
            return None
