#!/usr/bin/env python3
"""
Test script to extract a random frame from a random video and save it as test.jpg
This helps verify what the QC is actually seeing.
"""

import random
import subprocess
from pathlib import Path

# Add backend to path
import sys
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from PIL import Image

# Configuration
TARGET_HEIGHT = 480
JPEG_QUALITY = 85
OUTPUT_FILE = Path(__file__).parent / "test.jpg"

def get_random_video():
    """Find a random video from the outputs directory"""
    outputs_dir = Path(__file__).parent / "backend" / "outputs"

    if not outputs_dir.exists():
        print(f"Outputs directory not found: {outputs_dir}")
        return None

    # Find all mp4 files
    videos = list(outputs_dir.rglob("*.mp4"))

    if not videos:
        print("No videos found in outputs directory")
        return None

    video = random.choice(videos)
    print(f"Selected video: {video}")
    return video

def get_video_duration(video_path: Path) -> float:
    """Get video duration using ffprobe"""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

    if result.returncode != 0:
        print(f"Failed to get duration: {result.stderr}")
        return 0.0

    return float(result.stdout.strip())

def extract_frame(video_path: Path, timestamp: float, output_path: Path) -> bool:
    """Extract a single frame from video"""
    # First extract as PNG (high quality)
    temp_png = output_path.with_suffix('.png')

    cmd = [
        "ffmpeg",
        "-ss", str(timestamp),
        "-i", str(video_path),
        "-vframes", "1",
        "-q:v", "2",
        "-y",
        str(temp_png)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

    if result.returncode != 0 or not temp_png.exists():
        print(f"Failed to extract frame: {result.stderr}")
        return False

    return str(temp_png)

def downscale_image(image_path: str, output_path: Path) -> None:
    """Downscale image to 480p and save as JPEG (same as QC does)"""
    with Image.open(image_path) as img:
        original_size = img.size

        # Calculate new dimensions maintaining aspect ratio
        width, height = img.size
        if height > TARGET_HEIGHT:
            ratio = TARGET_HEIGHT / height
            new_width = int(width * ratio)
            new_height = TARGET_HEIGHT
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Convert to RGB if necessary (for JPEG)
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')

        # Save as JPEG with same quality as QC
        img.save(output_path, format='JPEG', quality=JPEG_QUALITY)

        final_size = img.size
        file_size = output_path.stat().st_size / 1024  # KB

        print(f"Original size: {original_size}")
        print(f"Downscaled size: {final_size}")
        print(f"JPEG quality: {JPEG_QUALITY}")
        print(f"File size: {file_size:.1f} KB")

def main():
    print("=" * 60)
    print("QC Image Test - Extracting random frame")
    print("=" * 60)

    # Get random video
    video = get_random_video()
    if not video:
        return

    # Get duration
    duration = get_video_duration(video)
    if duration <= 0:
        print("Could not get video duration")
        return

    print(f"Video duration: {duration:.1f}s")

    # Pick random timestamp (avoid first and last 10%)
    min_time = duration * 0.1
    max_time = duration * 0.9
    timestamp = random.uniform(min_time, max_time)
    print(f"Random timestamp: {timestamp:.2f}s")

    # Extract frame
    temp_frame = extract_frame(video, timestamp, OUTPUT_FILE)
    if not temp_frame:
        return

    print(f"Extracted frame to: {temp_frame}")

    # Downscale like QC does
    downscale_image(temp_frame, OUTPUT_FILE)

    # Clean up temp PNG
    Path(temp_frame).unlink()

    print("=" * 60)
    print(f"✓ Saved to: {OUTPUT_FILE}")
    print("=" * 60)
    print("\nThis is exactly what the QC model sees.")
    print("Open test.jpg to verify quality is sufficient for detecting issues.")

if __name__ == "__main__":
    main()
