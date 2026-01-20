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


class ManimGenerator:
    """Generates Manim animations using Gemini AI"""
    
    MODEL = "gemini-3-flash-preview"  # Stable flash model for generation
    CORRECTION_MODEL = "gemini-3-flash-preview"  # Same model for corrections (fast enough)
    MAX_CORRECTION_ATTEMPTS = 3  # Maximum number of auto-correction attempts
    
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
        
        # Return both video path and the final manim code for persistence
        return {
            "video_path": output_video,
            "manim_code": final_code
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
        pause_count = narration.count('...') + narration.count('[PAUSE]') * 2
        
        # Distribute wait time: animations should be shorter, waits fill the rest
        total_animation_time = audio_duration * 0.35
        total_wait_time = audio_duration * 0.65
        
        # Calculate a padding wait at the end to ensure we fill the full duration
        end_wait = max(2.0, audio_duration * 0.1)
        
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
        
        # Special handling for static scenes
        is_static = animation_type in ['static', 'mixed']
        static_instructions = ""
        if is_static:
            static_instructions = """
═══════════════════════════════════════════════════════════════════════════════
STATIC/MIXED SCENE GUIDANCE
═══════════════════════════════════════════════════════════════════════════════
For STATIC scenes, the visual serves as a backdrop while the narrator explains:
- Use simple FadeIn/Write for initial display
- Then use long self.wait() calls (4-8 seconds each)
- Keep elements on screen - don't animate everything
- The NARRATION carries the content, not the animation
- Think of it like a slide presentation with voice-over

Example static scene:
        title = Text("Key Definition", font_size=42)
        title.to_edge(UP)
        self.play(FadeIn(title), run_time=1)
        
        points = VGroup(
            Text("• First point", font_size=32),
            Text("• Second point", font_size=32),
            Text("• Third point", font_size=32)
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.4)
        points.next_to(title, DOWN, buff=0.8)
        
        for point in points:
            self.play(FadeIn(point), run_time=0.5)
            self.wait(3)  # Let narrator explain each point
        
        self.wait(5)  # Final wait while narrator wraps up
"""
        
        # Check if this is a UNIFIED SECTION (NEW: single video for entire section with timing cues)
        is_unified_section = section.get('is_unified_section', False)
        unified_context = ""
        if is_unified_section:
            num_segments = section.get('num_segments', 1)
            segment_timing = section.get('segment_timing', [])
            total_duration = section.get('total_duration', audio_duration)
            
            # Build detailed timing breakdown
            timing_lines = []
            for seg in segment_timing:
                timing_lines.append(
                    f"  - [{seg['start_time']:.1f}s - {seg['end_time']:.1f}s] ({seg['duration']:.1f}s): \"{seg['text'][:80]}...\""
                )
            timing_breakdown = "\n".join(timing_lines) if timing_lines else "No timing info"
            
            unified_context = f"""
═══════════════════════════════════════════════════════════════════════════════
UNIFIED SECTION: {num_segments} NARRATION SEGMENTS - ONE CONTINUOUS VIDEO
═══════════════════════════════════════════════════════════════════════════════
Create ONE smooth, continuous animation for the ENTIRE section.
The timestamps below help you sync your animations with the narration.

TOTAL DURATION: {total_duration:.1f} seconds

SEGMENT TIMING (use as sync points, NOT as separate scenes):
{timing_breakdown}

IMPORTANT - UNIFIED ANIMATION GUIDELINES:
1. Create ONE continuous flow of animations - no "scene changes" between segments
2. Use the timing info to sync key visual elements with narration milestones
3. Elements can persist across segment boundaries - don't clear everything
4. Transitions should be smooth within the section
5. Think of segments as "chapters" of one story, not separate videos
6. If one segment introduces a concept, the next can build on it visually

TIMING SYNC APPROACH:
- At t=0.0s: Start your opening animations
- For each segment start time: Have relevant visual ready by that time
- Use self.wait() to pad timing between key moments
- Example: If segment 2 starts at 12.5s and discusses a formula,
  make sure the formula appears around t=12.5s
"""
        
        # Check if this is a segment (OLD: per-segment video approach - legacy support)
        is_segment = section.get('is_segment', False)
        segment_context = ""
        if is_segment:
            seg_idx = section.get('segment_index', 0)
            total_segs = section.get('total_segments', 1)
            seg_duration = section.get('segment_duration', audio_duration)
            seg_start = section.get('segment_start_time', 0)
            seg_end = section.get('segment_end_time', seg_duration)
            section_total = section.get('section_total_duration', seg_duration)
            
            # Get context about other segments
            all_texts = section.get('all_segment_texts', [])
            all_durations = section.get('all_segment_durations', [])
            
            # Build context string showing timing of all segments
            timing_context = []
            for i, (txt, dur) in enumerate(zip(all_texts, all_durations)):
                marker = ">>> " if i == seg_idx else "    "
                timing_context.append(f"{marker}Seg {i+1}: {dur:.1f}s - \"{txt[:60]}...\"")
            timing_str = "\n".join(timing_context) if timing_context else "No timing info"
            
            segment_context = f"""
═══════════════════════════════════════════════════════════════════════════════
SEGMENT TIMING CONTEXT: Segment {seg_idx + 1} of {total_segs}
═══════════════════════════════════════════════════════════════════════════════
- This segment: {seg_duration:.1f}s (from {seg_start:.1f}s to {seg_end:.1f}s in section)
- Section total: {section_total:.1f}s
- All segments in this section:
{timing_str}

CONTINUITY GUIDELINES:
- {"START with title/intro since this is the first segment" if seg_idx == 0 else "NO intro - this continues from previous segment"}
- {"END with conclusion/cleanup since this is the last segment" if seg_idx == total_segs - 1 else "NO conclusion - next segment continues the content"}
- Keep visual style consistent across segments
- Create animations that EXACTLY fill {seg_duration:.1f} seconds
"""
        
        # Check if this is a subsection (OLD: legacy approach)
        is_subsection = section.get('is_subsection', False)
        subsection_context = ""
        if is_subsection and not is_segment:
            sub_idx = section.get('subsection_index', 0)
            total_subs = section.get('total_subsections', 1)
            subsection_context = f"""
═══════════════════════════════════════════════════════════════════════════════
SUBSECTION CONTEXT: This is part {sub_idx + 1} of {total_subs} in a larger section
═══════════════════════════════════════════════════════════════════════════════
- This clip will be merged with other subsections
- Focus on THIS part of the narration only
- Keep visual style consistent (same colors, fonts)
- Don't add intro title if not part 1
- Make transitions smooth - content will continue
"""
        
        # Combine context strings - prioritize unified section over segment
        context_str = unified_context or segment_context or subsection_context
        
        prompt = f"""Generate Manim code for an educational animation. Code goes inside construct(self).

SECTION: {section.get('title', 'Untitled')}
NARRATION: {narration}
KEY CONCEPTS: {key_concepts}
DURATION: {audio_duration:.1f} seconds exactly
{language_instructions}
{context_str}
{style_instructions}

════════════════════════════════════════════════════════════════════════════════
CORE RULE: PREVENT OVERLAPS
════════════════════════════════════════════════════════════════════════════════

Screen layout - use these zones:
    TITLE (top):    .to_edge(UP, buff=0.5)
    CONTENT (middle): .move_to(ORIGIN) or position with .next_to()
    FOOTER (bottom): .to_edge(DOWN, buff=0.5)

To avoid overlaps:
- Position elements BEFORE animating them
- Use VGroup(...).arrange() for multiple items
- FadeOut old content before adding new content in same area
- Or use ReplacementTransform(old, new) to swap

════════════════════════════════════════════════════════════════════════════════
SIZE GUIDELINES
════════════════════════════════════════════════════════════════════════════════

Text: font_size=36 (titles), font_size=28 (body), font_size=24 (labels)
Equations: .scale(0.85)
Axes/Plots: scale to fit - typically width=6, height=4
Spacing: buff=0.5 between elements

════════════════════════════════════════════════════════════════════════════════
PATTERNS - Choose based on content type
════════════════════════════════════════════════════════════════════════════════

TEXT/LIST - Title with bullet points:
        title = Text("Topic", font_size=36).to_edge(UP, buff=0.5)
        items = VGroup(
            Text("• First point", font_size=28),
            Text("• Second point", font_size=28),
        ).arrange(DOWN, buff=0.4, aligned_edge=LEFT)
        items.next_to(title, DOWN, buff=0.8)
        
        self.play(Write(title))
        for item in items:
            self.play(FadeIn(item), run_time=0.5)
            self.wait(2)

EQUATIONS - Step by step (replace in place):
        eq1 = MathTex(r"2x + 4 = 10").scale(0.85).move_to(ORIGIN)
        self.play(Write(eq1))
        self.wait(2)
        
        eq2 = MathTex(r"x = 3").scale(0.85).move_to(ORIGIN)
        self.play(ReplacementTransform(eq1, eq2))
        self.wait(2)

GRAPH/PLOT - Function visualization:
        axes = Axes(
            x_range=[-3, 3, 1], y_range=[-2, 8, 2],
            x_length=6, y_length=4,
            axis_config={{"include_tip": True}}
        ).move_to(ORIGIN)
        
        graph = axes.plot(lambda x: x**2, color=BLUE)
        label = axes.get_graph_label(graph, label="f(x)=x^2", x_val=2)
        
        self.play(Create(axes), run_time=1)
        self.play(Create(graph), run_time=2)
        self.play(Write(label))
        self.wait(3)

COMPARISON - Side by side:
        left_title = Text("Option A", font_size=28)
        right_title = Text("Option B", font_size=28)
        
        left_content = VGroup(
            Text("• Feature 1", font_size=24),
            Text("• Feature 2", font_size=24),
        ).arrange(DOWN, buff=0.3, aligned_edge=LEFT)
        
        right_content = VGroup(
            Text("• Feature 1", font_size=24),
            Text("• Feature 2", font_size=24),
        ).arrange(DOWN, buff=0.3, aligned_edge=LEFT)
        
        left_group = VGroup(left_title, left_content).arrange(DOWN, buff=0.5)
        right_group = VGroup(right_title, right_content).arrange(DOWN, buff=0.5)
        
        comparison = VGroup(left_group, right_group).arrange(RIGHT, buff=1.5)
        comparison.move_to(ORIGIN)
        
        self.play(FadeIn(left_group))
        self.wait(2)
        self.play(FadeIn(right_group))
        self.wait(3)

DIAGRAM - Shapes with labels:
        circle = Circle(radius=1.5, color=BLUE)
        label = Text("r=1.5", font_size=24).next_to(circle, DOWN, buff=0.3)
        diagram = VGroup(circle, label).move_to(ORIGIN)
        
        self.play(Create(circle), run_time=1.5)
        self.play(Write(label))
        self.wait(3)

PROCESS/FLOW - Sequential steps with arrows:
        step1 = Text("Input", font_size=28)
        step2 = Text("Process", font_size=28)
        step3 = Text("Output", font_size=28)
        
        steps = VGroup(step1, step2, step3).arrange(RIGHT, buff=1.5)
        arrows = VGroup(
            Arrow(step1.get_right(), step2.get_left(), buff=0.1),
            Arrow(step2.get_right(), step3.get_left(), buff=0.1),
        )
        flow = VGroup(steps, arrows).move_to(ORIGIN)
        
        self.play(Write(step1))
        self.play(GrowArrow(arrows[0]), Write(step2))
        self.play(GrowArrow(arrows[1]), Write(step3))
        self.wait(3)

HIGHLIGHT/TRANSFORM - Emphasize parts:
        eq = MathTex(r"E", r"=", r"m", r"c^2").scale(0.9).move_to(ORIGIN)
        self.play(Write(eq))
        self.wait(1)
        self.play(eq[2:].animate.set_color(YELLOW))  # Highlight mc²
        self.wait(2)

════════════════════════════════════════════════════════════════════════════════
TIMING: {audio_duration:.1f} SECONDS TOTAL
════════════════════════════════════════════════════════════════════════════════

- Animations: run_time=0.5 to 2 seconds
- Waits: self.wait(2) to self.wait(5) for narration
- End with: self.wait({end_wait:.1f})

════════════════════════════════════════════════════════════════════════════════
SYNTAX
════════════════════════════════════════════════════════════════════════════════

- 8 spaces indentation
- MathTex(r"\\frac{{a}}{{b}}") - raw string, double braces
- Axes config uses double braces: axis_config={{...}}

OUTPUT: Python code only. No markdown. No explanations."""

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.MODEL,
                    contents=prompt
                ),
                timeout=300  # 5 minute timeout for Gemini API
            )
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
        """Clean up generated code"""
        
        # Remove markdown code blocks
        if code.startswith("```"):
            lines = code.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            code = "\n".join(lines)
        
        # Remove any class definitions or imports that might have slipped in
        lines = code.split("\n")
        cleaned_lines = []
        skip_until_construct = False
        
        for line in lines:
            # Skip import lines
            if line.strip().startswith("from manim") or line.strip().startswith("import"):
                continue
            # Skip class definition
            if line.strip().startswith("class "):
                skip_until_construct = True
                continue
            if skip_until_construct:
                if "def construct" in line:
                    skip_until_construct = False
                continue
            cleaned_lines.append(line)
        
        code = "\n".join(cleaned_lines)
        
        # Ensure proper indentation (8 spaces for inside construct)
        lines = code.split("\n")
        indented_lines = []
        for line in lines:
            if line.strip():
                # Remove existing indentation and add 8 spaces
                indented_lines.append("        " + line.strip())
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
        attempt: int = 0
    ) -> Optional[str]:
        """Render a Manim scene to video with auto-correction on errors"""
        
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
                print(f"Manim error for section {section_index} (attempt {attempt + 1}):")
                print(result.stderr)
                
                # Try auto-correction if we haven't exceeded max attempts
                if attempt < self.MAX_CORRECTION_ATTEMPTS and section:
                    print(f"Attempting auto-correction (attempt {attempt + 1}/{self.MAX_CORRECTION_ATTEMPTS})...")
                    corrected_code = await self._correct_manim_code(
                        content, 
                        result.stderr, 
                        section
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
                            attempt + 1
                        )
                
                # Fall back to simple scene if all corrections failed
                return await self._render_fallback_scene(section_index, output_dir, code_file.parent)
            
            # Find the actual output file
            video_dir = Path(output_dir) / "videos" / code_file.stem / "480p15"
            if video_dir.exists():
                videos = list(video_dir.glob("*.mp4"))
                if videos:
                    return str(videos[0])
            
            # Try alternate paths
            for pattern in ["**/*.mp4"]:
                videos = list(Path(output_dir).glob(pattern))
                if videos:
                    return str(videos[0])
            
            print(f"Could not find rendered video for section {section_index}")
            return None
            
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
        section: Dict[str, Any]
    ) -> Optional[str]:
        """Use Gemini (lighter model) to fix errors in the Manim code"""
        
        prompt = f"""You are an expert Manim (Community Edition) programmer. The following Manim code has an error that needs to be fixed.

ORIGINAL CODE:
```python
{original_code}
```

ERROR MESSAGE:
```
{error_message[-2000:]}
```

SECTION INFO:
- Title: {section.get('title', 'Untitled')}
- Visual Description: {section.get('visual_description', '')}

CRITICAL - FIX THE CODE following these guidelines:

INDENTATION IS CRITICAL (most common error):
- Use EXACTLY 4 spaces for each indentation level
- Class body: 4 spaces
- Method body (def construct): 8 spaces  
- Inside loops/conditionals: 12 spaces, 16 spaces, etc.
- NEVER use tabs, NEVER mix tabs and spaces
- Every line inside construct() must start with at least 8 spaces

FIXING GUIDELINES:
1. Analyze the error message carefully
2. If error mentions IndentationError, TabError, or unexpected indent:
   - Replace ALL tabs with 4 spaces
   - Ensure consistent spacing throughout
   - Check that all method bodies use 8-space indentation
3. Fix ONLY the issue causing the error
4. Keep the same visual intent and animations
5. Use modern Manim CE syntax (from manim import *)
6. Common syntax fixes:
   - Use MathTex for math, Text for regular text
   - Double backslashes in LaTeX strings (e.g., "\\\\frac" not "\\frac")
   - Colors should be uppercase: BLUE, RED, GREEN, etc.
   - Use .animate for chained animations (e.g., obj.animate.shift(UP))
   - VGroup elements must be Mobjects, not strings
   - Ensure all objects are created before being animated
   - self.play() requires animation objects, not Mobjects directly
   - IMPORTANT: Before removing/fading out objects, ensure they were added to the scene
   - Use self.add() or self.play(Create/Write/FadeIn) before self.play(FadeOut)
   - Clear objects properly: self.remove() or FadeOut before reusing variable names
7. LAYOUT FIXES (if elements overlap or are off-screen):
   - Use .next_to(obj, DOWN, buff=0.5) with buffer spacing
   - Scale down large equations: .scale(0.7)
   - Use .arrange(DOWN, buff=0.4) for VGroups
   - Position titles with .to_edge(UP, buff=0.5)
8. If the error is too complex, simplify the scene while keeping the core message

Return ONLY the complete corrected Python code (the full file with imports and class definition).
No markdown, no explanations, just the code.
ENSURE ALL INDENTATION USES SPACES, NOT TABS."""

        try:
            # Use lighter model for quick error fixes
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.CORRECTION_MODEL,
                contents=prompt
            )
            
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
