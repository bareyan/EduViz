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
    
    MODEL = "gemini-3-flash-preview"  # Main model for generation
    CORRECTION_MODEL = "gemini-3-flash-preview"  # Lighter model for quick error fixes
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
        audio_duration: Optional[float] = None
    ) -> Dict[str, Any]:
        """Generate a video for a single section
        
        Args:
            section: Section data with title, narration, visual_description, etc.
            output_dir: Directory to save output files
            section_index: Index of this section
            audio_duration: Actual audio duration in seconds (if audio was pre-generated)
        
        Returns:
            Dict with video_path and manim_code
        """
        
        # Use audio duration as the target if available, otherwise fall back to estimated
        target_duration = audio_duration if audio_duration else section.get("duration_seconds", 60)
        section["target_duration"] = target_duration
        
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
    
    async def _generate_manim_code(self, section: Dict[str, Any], target_duration: float) -> str:
        """Use Gemini to generate Manim code for a section"""
        
        # Calculate timing - audio is already generated, we know exact duration
        audio_duration = target_duration
        
        # Count pause markers in narration to estimate natural break points
        narration = section.get('narration', '')
        pause_count = narration.count('...') + narration.count('[PAUSE]') * 2
        
        # Distribute wait time: some for pauses, some for content viewing
        total_animation_time = audio_duration * 0.4  # ~40% for animations
        total_wait_time = audio_duration * 0.6  # ~60% for waits/pauses
        
        prompt = f"""You are an expert Manim (Community Edition) programmer creating animations for a mathematical lecture video (like 3Blue1Brown).

Generate Manim code for this video section. The code goes INSIDE the construct(self) method.

SECTION DETAILS:
- Title: {section.get('title', 'Untitled')}
- Narration: {narration}
- Visual Description: {section.get('visual_description', '')}
- Key Equations: {section.get('key_equations', [])}
- Animation Type: {section.get('animation_type', 'text')}

═══════════════════════════════════════════════════════════════════════════════
CRITICAL: AUDIO IS ALREADY GENERATED - DURATION IS EXACTLY {audio_duration:.1f} SECONDS
═══════════════════════════════════════════════════════════════════════════════

Your animation MUST total EXACTLY {audio_duration:.1f} seconds to sync with the audio.

TIMING BREAKDOWN:
- Total animation run_time: ~{total_animation_time:.1f} seconds
- Total self.wait() time: ~{total_wait_time:.1f} seconds  
- Number of natural pauses in narration: {pause_count}
- Each "..." in narration = self.wait(1.5-2)
- Each "[PAUSE]" = self.wait(3-4)

TIMING STRATEGY:
1. Add up all your run_time values and wait() values - they should sum to ~{audio_duration:.1f}s
2. Animations: self.play(..., run_time=1.0-2.0) 
3. After each visual element appears: self.wait(2-4)
4. End with self.wait(2) for clean ending
5. Err on the side of longer waits - better to have video slightly longer than audio

═══════════════════════════════════════════════════════════════════════════════
CRITICAL: PYTHON INDENTATION
═══════════════════════════════════════════════════════════════════════════════
- Use exactly 8 spaces for indentation (code goes inside construct method)
- Every line must start with 8 spaces
- For nested blocks (if/for/while), add 4 more spaces per level
- NO TABS - only spaces
- Check every line has correct indentation before outputting

EXAMPLE OF CORRECT INDENTATION:
        # This comment has 8 spaces before it
        title = Text("Hello", font_size=42)
        self.play(Write(title), run_time=1.5)
        self.wait(2)
        
        if some_condition:
            # 12 spaces for nested block
            self.play(FadeOut(title))
        
        for i in range(3):
            # 12 spaces for loop body
            obj = Circle()
            self.play(Create(obj), run_time=1)
            self.wait(1)

═══════════════════════════════════════════════════════════════════════════════
CRITICAL: LAYOUT AND POSITIONING
═══════════════════════════════════════════════════════════════════════════════

AVOID OVERLAPPING ELEMENTS - this is a common problem:
1. Use .next_to(obj, DOWN, buff=0.5) instead of stacking at same position
2. Always include buff (buffer) parameter: buff=0.3 to buff=0.8
3. Use .to_edge(UP) for titles, .to_edge(DOWN) for labels
4. Scale down objects if needed: .scale(0.7) or .scale(0.8)
5. Use .arrange(DOWN, buff=0.5) for VGroups to auto-space elements
6. For multi-line equations, use .arrange(DOWN, center=True, buff=0.4)
7. Check positioning before animating: obj.next_to(other, RIGHT, buff=0.5)

LAYOUT PATTERNS:
- Title at top: title.to_edge(UP, buff=0.5)
- Main content centered: eq.move_to(ORIGIN)
- Steps list: VGroup(*steps).arrange(DOWN, buff=0.4, aligned_edge=LEFT)
- Side-by-side: VGroup(left, right).arrange(RIGHT, buff=1.0)
- Keep old steps visible: old.shift(UP * 1.5) before adding new

SCALING FOR COMPLEX EQUATIONS:
- Long equations: MathTex(...).scale(0.7)
- Multiple items: reduce font_size=28 instead of 36
- If too crowded, fade out less important elements first

═══════════════════════════════════════════════════════════════════════════════

MANIM SYNTAX REMINDERS:
1. MathTex for equations: MathTex(r"\\frac{{x}}{{y}}") - use raw strings and double braces
2. Text for labels: Text("label", font_size=32)
3. VGroup to group objects: group = VGroup(obj1, obj2)
4. Animations: Write(), FadeIn(), FadeOut(), Transform(), Create()
5. Positioning: .to_edge(UP), .next_to(obj, DOWN), .move_to(ORIGIN)
6. Colors: BLUE, YELLOW, WHITE, GRAY, GREEN, RED

SCENE MANAGEMENT:
1. Track ALL objects you create
2. Always clean up: end with FadeOut of remaining objects
3. Use VGroup for related elements
4. Don't lose references after Transform (use ReplacementTransform if needed)

Generate ONLY the Python code. No markdown, no ```python blocks, no explanations.
Start directly with the indented code (8 spaces)."""

        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model=self.MODEL,
            contents=prompt
        )
        
        code = response.text.strip()
        
        # Clean up the code
        code = self._clean_code(code)
        
        return code
    
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
                timeout=120  # 2 minute timeout per section
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
                timeout=60
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
