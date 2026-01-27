"""
Manim scene renderer with error correction and fallback support
"""

import os
import re
import asyncio
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, TYPE_CHECKING

from .code_helpers import ensure_manim_structure
from ..config import QUALITY_DIR_MAP, QUALITY_FLAGS, RENDER_TIMEOUT

if TYPE_CHECKING:
    from . import ManimGenerator


def get_quality_subdir(quality: str) -> str:
    """Get the Manim output subdirectory for a quality setting"""
    return QUALITY_DIR_MAP.get(quality, "480p15")


def cleanup_partial_movie_files(output_dir: str, code_file: Path, quality: str = "low") -> None:
    """Clean up partial movie files directory before re-rendering.
    
    This prevents Manim from having stale partial files that won't be 
    included in the final concatenation. When a scene is re-rendered,
    Manim only tracks the new partial files in partial_movie_file_list.txt,
    but old files remain in the directory, causing confusion.
    """
    quality_subdir = get_quality_subdir(quality)
    video_base = Path(output_dir) / "videos" / code_file.stem / quality_subdir
    partial_dir = video_base / "partial_movie_files"

    if partial_dir.exists():
        print(f"[ManimGenerator] Cleaning up partial movie files before re-render: {partial_dir}")
        try:
            shutil.rmtree(partial_dir)
            print("[ManimGenerator] OK Partial movie files cleaned up")
        except Exception as e:
            print(f"[ManimGenerator] WARN Failed to clean up partial movie files: {e}")

    # Also remove any existing combined video to force fresh concatenation
    for existing_video in video_base.glob("*.mp4"):
        try:
            existing_video.unlink()
            print(f"[ManimGenerator] Removed existing video: {existing_video}")
        except Exception as e:
            print(f"[ManimGenerator] WARN Failed to remove video {existing_video}: {e}")


async def render_scene(
    generator: "ManimGenerator",
    code_file: Path,
    scene_name: str,
    output_dir: str,
    section_index: int,
    section: Dict[str, Any] = None,
    attempt: int = 0,
    qc_iteration: int = 0,
    clean_retry: int = 0,
    quality: str = "low",
) -> Optional[str]:
    """Render a Manim scene to video with auto-correction on errors and visual QC
    
    When all corrections fail:
    - If clean_retry < MAX_CLEAN_RETRIES: returns None to trigger clean regeneration
    - If clean_retry >= MAX_CLEAN_RETRIES: uses fallback scene as last resort
    """
    # Get the actual class name from the file
    with open(code_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract class name
    match = re.search(r"class (\w+)\(Scene\)", content)
    if match:
        scene_name = match.group(1)

    # Get quality flag from config
    quality_flag = QUALITY_FLAGS.get(quality, "-ql")

    # Build manim command
    cmd = [
        "manim",
        quality_flag,  # Use quality flag
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
            timeout=RENDER_TIMEOUT
        )

        if result.returncode != 0:
            qc_note = f" (QC iteration {qc_iteration})" if qc_iteration > 0 else ""
            retry_note = f" (clean retry {clean_retry})" if clean_retry > 0 else ""
            print(f"[ManimGenerator] Render error for section {section_index}{qc_note}{retry_note} (attempt {attempt + 1}):")
            # Print last 1500 chars of error
            print(result.stderr[-1500:] if len(result.stderr) > 1500 else result.stderr)

            # Try auto-correction if we haven't exceeded max attempts
            if attempt < generator.MAX_CORRECTION_ATTEMPTS and section:
                print(f"[ManimGenerator] Attempting auto-correction (attempt {attempt + 1}/{generator.MAX_CORRECTION_ATTEMPTS})...")

                # Use tool-based correction
                corrected_code = await correct_manim_code(
                    generator,
                    content,
                    result.stderr,
                    section,
                    attempt=attempt
                )

                if corrected_code:
                    # Overwrite the original file with corrected code
                    with open(code_file, "w", encoding="utf-8") as f:
                        f.write(corrected_code)

                    # Clean up partial movie files before re-rendering
                    cleanup_partial_movie_files(output_dir, code_file, quality)

                    # Try rendering again with corrected code
                    return await render_scene(
                        generator,
                        code_file,
                        scene_name,
                        output_dir,
                        section_index,
                        section,
                        attempt + 1,
                        qc_iteration,
                        clean_retry,
                        quality  # Pass through quality setting
                    )

            # All correction attempts exhausted
            if clean_retry < generator.MAX_CLEAN_RETRIES:
                print(f"[ManimGenerator] ERROR All {generator.MAX_CORRECTION_ATTEMPTS} correction attempts failed - will try clean regeneration")
                return None
            else:
                print(f"[ManimGenerator] ERROR All correction attempts failed on clean retry {clean_retry}, using fallback scene")
                return await render_fallback_scene(section_index, output_dir, code_file.parent)

        # Find the actual output file
        quality_subdir = get_quality_subdir(quality)
        video_dir = Path(output_dir) / "videos" / code_file.stem / quality_subdir
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

        # Successfully rendered and validated
        return rendered_video

    except subprocess.TimeoutExpired:
        print(f"Manim rendering timed out for section {section_index}")
        if clean_retry < generator.MAX_CLEAN_RETRIES:
            return None
        return await render_fallback_scene(section_index, output_dir, code_file.parent)
    except Exception as e:
        print(f"Error rendering section {section_index}: {e}")
        if clean_retry < generator.MAX_CLEAN_RETRIES:
            return None
        return await render_fallback_scene(section_index, output_dir, code_file.parent)


async def render_from_code(
    generator: "ManimGenerator",
    manim_code: str,
    output_dir: str,
    section_index: int = 0,
    quality: str = "low"
) -> Optional[str]:
    """Render a Manim scene from existing code (e.g., translated code)"""
    from .code_helpers import fix_translated_code, extract_scene_name

    # Validate the code has basic structure
    if not manim_code or len(manim_code.strip()) < 50:
        print("[ManimGenerator] Code too short or empty, skipping render")
        return None

    # Fix common translation issues
    manim_code = fix_translated_code(manim_code)

    # Ensure imports are present
    if "from manim import" not in manim_code and "import manim" not in manim_code:
        manim_code = "from manim import *\n\n" + manim_code

    # Extract scene name from code
    scene_name = extract_scene_name(manim_code)
    if not scene_name:
        print("[ManimGenerator] No Scene class found in code, skipping render")
        return None

    # Write the code to a file
    code_file = Path(output_dir) / "scene.py"

    with open(code_file, "w", encoding="utf-8") as f:
        f.write(manim_code)

    # Check for Python syntax errors before rendering
    try:
        compile(manim_code, str(code_file), 'exec')
    except SyntaxError as e:
        print(f"[ManimGenerator] Syntax error in translated code: {e}")
        return None

    # Render
    output_path = Path(output_dir) / f"section_{section_index}.mp4"

    # Determine quality flag
    quality_flags = {"low": "-ql", "medium": "-qm", "high": "-qh", "4k": "-qk"}
    quality_flag = quality_flags.get(quality, "-ql")

    cmd = [
        "manim",
        quality_flag,
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
            stderr = result.stderr
            if "Error" in stderr or "Exception" in stderr:
                lines = stderr.split('\n')
                error_lines = [l for l in lines if 'Error' in l or 'Exception' in l or 'error' in l.lower()]
                if error_lines:
                    print(f"[ManimGenerator] Render error: {error_lines[-1][:200]}")
                else:
                    print(f"[ManimGenerator] Render failed with exit code {result.returncode}")
            else:
                print(f"[ManimGenerator] Render failed: {stderr[:300]}")
            return None

        # Find the rendered video
        quality_subdir = get_quality_subdir(quality)
        video_subdir = Path(output_dir) / "videos" / "scene" / quality_subdir
        if video_subdir.exists():
            for video_file in video_subdir.glob("*.mp4"):
                return str(video_file)

        if output_path.exists():
            return str(output_path)

        for subdir in Path(output_dir).rglob("*.mp4"):
            return str(subdir)

        print("[ManimGenerator] Video file not found in expected locations")
        return None

    except subprocess.TimeoutExpired:
        print("[ManimGenerator] Render timed out after 300 seconds")
        return None
    except Exception as e:
        print(f"[ManimGenerator] Render exception: {e}")
        return None


async def render_fallback_scene(
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
    with open(fallback_file, "w", encoding="utf-8") as f:
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
        await asyncio.to_thread(
            subprocess.run,
            cmd,
            capture_output=True,
            text=True,
            timeout=180
        )

        for pattern in ["**/*.mp4"]:
            videos = list(Path(output_dir).glob(pattern))
            if videos:
                return str(videos[0])

        return None
    except Exception as e:
        print(f"Fallback render also failed: {e}")
        return None


async def correct_manim_code(
    generator: "ManimGenerator",
    original_code: str,
    error_message: str,
    section: Dict[str, Any],
    attempt: int = 0
) -> Optional[str]:
    """Use GenerationToolHandler.fix() to correct code errors"""
    try:
        result = await generator.correction_handler.fix(
            code=original_code,
            error_message=error_message,
            section=section,
            attempt=attempt,
        )

        if result.success and result.code:
            corrected = result.code.strip()
            if ensure_manim_structure(corrected):
                return corrected
            print("[ManimGenerator] Corrected code missing basic Manim structure")
            return None

        print(f"[ManimGenerator] Correction failed: {result.error}")
        return None

    except Exception as e:
        print(f"[ManimGenerator] Error during code correction: {e}")
        return None


async def generate_visual_fix(
    generator: "ManimGenerator",
    original_code: str,
    error_report: str,
    section: Dict[str, Any] = None
) -> Optional[str]:
    """Generate fixed Manim code based on visual QC error report"""
    if not error_report:
        return None

    if not section:
        section = {}

    try:
        result = await generator.correction_handler.fix(
            code=original_code,
            error_message=error_report,
            section=section,
            attempt=0,
        )

        if not result.success or not result.code:
            print(f"[ManimGenerator] Visual fix failed: {result.error}")
            return None

        fixed_code = result.code.strip()

        if "from manim import" not in fixed_code:
            fixed_code = "from manim import *\n\n" + fixed_code

        if not ensure_manim_structure(fixed_code):
            print("[ManimGenerator] Visual fix missing required structure")
            return None

        fixed_code = fixed_code.replace('\r\n', '\n')

        # Validate the fix
        fixed_code = await validate_and_fix_code(generator, fixed_code, section)

        return fixed_code

    except Exception as e:
        print(f"[ManimGenerator] Error generating visual fix: {e}")
        return None


async def validate_and_fix_code(
    generator: "ManimGenerator",
    code: str,
    section: Dict[str, Any] = None,
    max_attempts: int = 3
) -> Optional[str]:
    """Test-render code and fix any errors"""
    from .code_helpers import extract_scene_name

    for attempt in range(max_attempts):
        scene_name = extract_scene_name(code)
        if not scene_name:
            print("[ManimGenerator] No Scene class found in visual fix code")
            return None

        # Create temp file for test render
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name

        temp_output = tempfile.mkdtemp(prefix='manim_test_')

        try:
            cmd = [
                "manim",
                "-ql",
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
                timeout=120
            )

            if result.returncode == 0:
                print(f"[ManimGenerator] OK Visual fix validated (attempt {attempt + 1})")
                try:
                    os.unlink(temp_file)
                    shutil.rmtree(temp_output, ignore_errors=True)
                except:
                    pass
                return code

            error_msg = result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr
            print(f"[ManimGenerator] Visual fix render error (attempt {attempt + 1}/{max_attempts}):")
            error_lines = [l for l in error_msg.split('\n') if l.strip() and not l.strip().startswith('─')]
            print('\n'.join(error_lines[-10:]))

            if attempt < max_attempts - 1:
                print("[ManimGenerator] Attempting to fix render error...")
                fixed_code = await fix_render_error(generator, code, error_msg, section)

                if fixed_code:
                    code = fixed_code
                else:
                    print("[ManimGenerator] Could not generate fix, aborting")
                    break

        except subprocess.TimeoutExpired:
            print("[ManimGenerator] Test render timed out")
            break
        except Exception as e:
            print(f"[ManimGenerator] Test render error: {e}")
            break
        finally:
            try:
                os.unlink(temp_file)
                shutil.rmtree(temp_output, ignore_errors=True)
            except:
                pass

    print(f"[ManimGenerator] WARN Could not validate visual fix after {max_attempts} attempts")
    return None


async def fix_render_error(
    generator: "ManimGenerator",
    code: str,
    error_message: str,
    section: Dict[str, Any] = None
) -> Optional[str]:
    """Fix a render error in the code using Gemini"""
    try:
        result = await generator.correction_handler.fix(
            code=code,
            error_message=error_message,
            section=section,
            attempt=0,
        )

        if not result.success or not result.code:
            print(f"[ManimGenerator] Render fix failed: {result.error}")
            return None

        fixed_code = result.code.strip()

        if "from manim import" not in fixed_code:
            fixed_code = "from manim import *\n\n" + fixed_code

        return fixed_code

    except Exception as e:
        print(f"[ManimGenerator] Error fixing render error: {e}")
        return None
