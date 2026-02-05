"""
Timing Validator - Ensures video duration matches audio duration

Calculates actual animation duration from Manim code by parsing
self.play() and self.wait() calls, then adjusts final wait time
to match target audio duration.
"""

import re
import ast
from typing import Tuple
from app.core import get_logger

logger = get_logger(__name__, component="timing_validator")

# Default Manim timings
DEFAULT_ANIMATION_RUN_TIME = 1.0  # Default for self.play()
DEFAULT_WAIT_TIME = 1.0  # Default for self.wait() without args
MIN_WAIT_TIME = 0.1  # Avoid zero/negative waits that Manim rejects


def extract_timing_from_code(code: str) -> Tuple[float, int]:
    """
    Calculate total animation duration from Manim code.
    
    Returns:
        Tuple of (total_duration_seconds, line_count)
    """
    total_time = 0.0
    play_count = 0
    wait_count = 0
    
    # Find all self.play() calls
    # Pattern: self.play(..., run_time=X.X) or self.play(...) without run_time
    play_pattern = r'self\.play\s*\([^)]*\)'
    play_matches = re.finditer(play_pattern, code, re.DOTALL)
    
    for match in play_matches:
        play_call = match.group(0)
        play_count += 1
        
        # Check if run_time is specified
        run_time_match = re.search(r'run_time\s*=\s*([\d.]+)', play_call)
        if run_time_match:
            total_time += float(run_time_match.group(1))
        else:
            # No run_time specified, use default
            total_time += DEFAULT_ANIMATION_RUN_TIME
    
    # Find all self.wait() calls
    # Pattern: self.wait(X.X) or self.wait() without args
    wait_pattern = r'self\.wait\s*\(([^)]*)\)'
    wait_matches = re.finditer(wait_pattern, code)
    
    for match in wait_matches:
        wait_count += 1
        args = match.group(1).strip()
        
        if args:
            # Extract numeric value
            try:
                # Handle simple numbers
                wait_time = float(args)
                total_time += wait_time
            except ValueError:
                # If not a simple number, use default
                total_time += DEFAULT_WAIT_TIME
        else:
            # No argument, use default
            total_time += DEFAULT_WAIT_TIME
    
    logger.debug(f"Calculated timing: {total_time:.2f}s ({play_count} plays, {wait_count} waits)")
    return total_time, play_count + wait_count


def adjust_timing_to_match_audio(code: str, target_duration: float) -> str:
    """
    Adjust video timing to match target audio duration.
    
    Strategy:
    1. Calculate current video duration from code
    2. If video is shorter than audio, add/adjust final wait
    3. If video is much longer (>10%), warn but don't cut
    
    Args:
        code: Manim code to adjust
        target_duration: Target duration in seconds (audio length)
    
    Returns:
        Adjusted code with proper timing
    """
    current_duration, call_count = extract_timing_from_code(code)
    
    if call_count == 0:
        # No animations found, just add a wait for full duration
        logger.warning(f"No animations found in code, adding wait for {target_duration:.2f}s")
        return _add_final_wait(code, target_duration)
    
    duration_diff = target_duration - current_duration
    
    # If video is already long enough (within 0.5s), leave it
    if duration_diff < 0.5:
        logger.info(f"Video duration {current_duration:.2f}s matches audio {target_duration:.2f}s")
        return code
    
    # If video is too short, add padding
    if duration_diff > 0.5:
        logger.info(f"Video too short ({current_duration:.2f}s vs {target_duration:.2f}s), adding {duration_diff:.2f}s padding")
        return _adjust_final_wait(code, duration_diff)
    
    # If video is significantly longer, warn but don't cut
    if current_duration > target_duration * 1.1:
        logger.warning(f"Video duration {current_duration:.2f}s exceeds audio {target_duration:.2f}s by >10%")
    
    return code


def _add_final_wait(code: str, duration: float) -> str:
    """Add a final wait to the end of construct()"""
    duration = max(duration, MIN_WAIT_TIME)
    lines = code.split('\n')
    
    # Find indentation of last non-empty line in construct
    last_indent = "        "  # Default 8 spaces
    for line in reversed(lines):
        if line.strip() and not line.strip().startswith('#'):
            last_indent = re.match(r'^\s*', line).group(0)
            break
    
    # Add wait before the last line (usually after last animation)
    wait_line = f"{last_indent}self.wait({duration:.2f})"
    
    # Insert before closing (find last non-empty line)
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip():
            lines.insert(i + 1, wait_line)
            break
    
    return '\n'.join(lines)


def _adjust_final_wait(code: str, additional_time: float) -> str:
    """
    Adjust the final wait() call to add additional time.
    If no final wait exists, add one.
    """
    lines = code.split('\n')
    
    # Find the last self.wait() call
    last_wait_idx = None
    for i in range(len(lines) - 1, -1, -1):
        if 'self.wait(' in lines[i]:
            last_wait_idx = i
            break
    
    if last_wait_idx is not None:
        # Adjust existing wait
        wait_line = lines[last_wait_idx]
        indent = re.match(r'^\s*', wait_line).group(0)
        
        # Extract current wait time
        wait_match = re.search(r'self\.wait\s*\(([^)]*)\)', wait_line)
        if wait_match:
            args = wait_match.group(1).strip()
            if args:
                try:
                    current_wait = float(args)
                    new_wait = max(current_wait + additional_time, MIN_WAIT_TIME)
                    lines[last_wait_idx] = f"{indent}self.wait({new_wait:.2f})"
                    logger.debug(f"Adjusted wait from {current_wait:.2f}s to {new_wait:.2f}s")
                except ValueError:
                    # Can't parse, append new wait instead
                    return _add_final_wait(code, additional_time)
            else:
                # No args, default is 1.0
                new_wait = max(DEFAULT_WAIT_TIME + additional_time, MIN_WAIT_TIME)
                lines[last_wait_idx] = f"{indent}self.wait({new_wait:.2f})"
        
        return '\n'.join(lines)
    else:
        # No wait found, add one
        return _add_final_wait(code, additional_time)


def _sanitize_waits(code: str) -> str:
    """Replace zero/negative waits with a small positive value."""
    pattern = re.compile(r"self\.wait\(\s*([+-]?\d+(?:\.\d+)?)\s*\)")

    def _replace(match: re.Match) -> str:
        try:
            value = float(match.group(1))
        except ValueError:
            return match.group(0)
        if value <= 0:
            return "self.wait(0.10)"
        return match.group(0)

    return pattern.sub(_replace, code)


class TimingValidator:
    """Validates and adjusts timing in Manim code"""
    
    def validate_and_fix(self, code: str, target_duration: float) -> str:
        """
        Validate timing and adjust if necessary.
        
        Args:
            code: Manim code
            target_duration: Target duration in seconds
            
        Returns:
            Adjusted code
        """
        try:
            adjusted = adjust_timing_to_match_audio(code, target_duration)
            return _sanitize_waits(adjusted)
        except Exception as e:
            logger.error(f"Failed to adjust timing: {e}")
            # Return original code if adjustment fails
            return code
