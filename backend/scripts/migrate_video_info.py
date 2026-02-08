"""
Migration script: Backfill video_info.json for existing completed videos.

Reads from job_data/*.json and creates video_info.json in outputs/<id>/
for any completed job that has result data but no video_info.json yet.

Usage:
    python -m scripts.migrate_video_info
"""

import json
from pathlib import Path
import sys

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import OUTPUT_DIR, JOB_DATA_DIR
from app.core.video_info import (
    VideoInfo,
    VideoChapter,
    save_video_info,
    video_info_exists,
)


def migrate_video_info():
    """Migrate existing job results to video_info.json files."""
    migrated = 0
    skipped = 0
    errors = 0

    if not JOB_DATA_DIR.exists():
        print(f"Job data directory not found: {JOB_DATA_DIR}")
        return

    for job_file in JOB_DATA_DIR.glob("*.json"):
        try:
            with open(job_file, "r", encoding="utf-8") as f:
                job_data = json.load(f)

            job_id = job_data.get("id")
            if not job_id:
                continue

            # Skip if not completed
            if job_data.get("status") != "completed":
                continue

            # Skip if video_info.json already exists
            if video_info_exists(job_id):
                skipped += 1
                continue

            # Skip if no final video exists
            video_path = OUTPUT_DIR / job_id / "final_video.mp4"
            if not video_path.exists():
                continue

            # Get result data
            result_list = job_data.get("result", [])
            if not result_list or not isinstance(result_list, list):
                continue

            result = result_list[0]  # First result contains video info

            # Create VideoInfo
            chapters = [
                VideoChapter(
                    title=ch.get("title", ""),
                    start_time=ch.get("start_time", 0.0),
                    duration=ch.get("duration", 0.0),
                )
                for ch in result.get("chapters", [])
            ]

            video_info = VideoInfo(
                video_id=job_id,
                title=result.get("title", "Untitled"),
                duration=result.get("duration", 0.0),
                chapters=chapters,
                created_at=job_data.get("created_at"),
                thumbnail_url=result.get("thumbnail_url"),
            )

            # Save it
            save_video_info(video_info)
            migrated += 1
            print(f"✓ Migrated: {job_id[:8]}... - {video_info.title[:40]}")

        except Exception as e:
            errors += 1
            print(f"✗ Error processing {job_file.name}: {e}")

    print(f"\nMigration complete: {migrated} migrated, {skipped} skipped, {errors} errors")


if __name__ == "__main__":
    migrate_video_info()
