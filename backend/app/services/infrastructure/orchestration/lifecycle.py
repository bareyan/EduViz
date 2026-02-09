"""
Lifecycle management for the EduViz application.
Handles startup checks, job resumption, and shutdown tasks.
"""

import asyncio
import os
import shutil
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import FastAPI
from app.config import OUTPUT_DIR, UPLOAD_DIR
from app.core import (
    get_logger,
    run_startup_runtime_checks,
    save_video_info,
    create_video_info_from_result,
    load_script,
    parse_bool_env,
)
from app.models.status import JobStatus
from app.services.infrastructure.orchestration import get_job_manager
from app.services.infrastructure.storage import OutputCleanupService
from app.services.pipeline.assembly import VideoGenerator
from app.services.pipeline.assembly.ffmpeg import generate_thumbnail

logger = get_logger(__name__, service="lifecycle")


class StartupManager:
    def __init__(self, app: FastAPI):
        self.app = app
        self.job_manager = get_job_manager()
        self.video_generator = VideoGenerator(str(OUTPUT_DIR))
        self.cleanup_service = OutputCleanupService(OUTPUT_DIR, self.job_manager, upload_dir=UPLOAD_DIR)

    async def run_startup(self) -> None:
        """Handle startup tasks like resuming interrupted jobs."""
        
        strict_runtime = parse_bool_env(
            os.getenv("STARTUP_STRICT_RUNTIME_CHECKS"),
            default=os.getenv("ENV", "").lower() == "production",
        )
        runtime_report = run_startup_runtime_checks(
            output_dir=OUTPUT_DIR,
            upload_dir=UPLOAD_DIR,
            strict_tools=strict_runtime,
            strict_dirs=True,
        )
        self.app.state.runtime_report = runtime_report
        logger.info("Startup runtime checks complete", extra={"runtime_report": runtime_report})

        self.app.state.output_cleanup_task = None
        try:
            self.cleanup_service.run_once()
            self.app.state.output_cleanup_task = asyncio.create_task(self.cleanup_service.run_periodic())
        except Exception as exc:
            logger.error("Failed to initialize output cleanup", extra={"error": str(exc)}, exc_info=True)

        # Track jobs being resumed to avoid duplicate processing
        resuming_jobs = set()

        # Find and resume interrupted jobs
        interrupted_jobs = self.job_manager.get_interrupted_jobs()

        for job in interrupted_jobs:
            job_id = job.id

            if job_id in resuming_jobs:
                continue
            resuming_jobs.add(job_id)

            # Check what progress exists
            progress = self.video_generator.check_existing_progress(job_id)

            if progress["has_script"] and progress["completed_sections"]:
                logger.info(f"[Startup] Found interrupted job {job_id} with {len(progress['completed_sections'])}/{progress['total_sections']} sections")

                # Check if all sections are complete
                if len(progress["completed_sections"]) == progress["total_sections"] and progress["total_sections"] > 0:
                    # All sections done, just need to combine
                    logger.info(f"[Startup] Job {job_id} has all sections, attempting to combine...")
                    await self._try_combine_job(job_id, progress)
                else:
                    # Some sections incomplete - mark for manual resume
                    self.job_manager.update_job(
                        job_id,
                        JobStatus.FAILED,
                        message=f"Interrupted: {len(progress['completed_sections'])}/{progress['total_sections']} sections complete. Use resume to continue."
                    )
    
    async def run_shutdown(self) -> None:
        """Stop background services gracefully."""
        cleanup_task = getattr(self.app.state, "output_cleanup_task", None)
        if cleanup_task:
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass

    async def _try_combine_job(self, job_id: str, progress: Dict[str, Any]):
        """Try to combine completed sections into final video"""
        
        job_output_dir = OUTPUT_DIR / job_id
        sections_dir = job_output_dir / "sections"

        try:
            # Create concat list
            concat_list_path = job_output_dir / "concat_list.txt"
            script = progress["script"]
            sections = script.get("sections", [])

            added_videos = 0
            with open(concat_list_path, "w", encoding="utf-8") as f:
                for i, section in enumerate(sections):
                    section_id = section.get("id", f"section_{i}")
                    # Section directories are index-based in the pipeline, with section_id as legacy fallback.
                    candidate_dirs = [sections_dir / str(i), sections_dir / section_id]
                    section_path = next((p for p in candidate_dirs if p.exists() and p.is_dir()), None)
                    if not section_path:
                        continue

                    video_path = None
                    preferred = section_path / "final_section.mp4"
                    legacy_merged = sections_dir / f"merged_{i}.mp4"

                    if preferred.exists():
                        video_path = preferred
                    elif legacy_merged.exists():
                        video_path = legacy_merged
                    else:
                        mp4_files = sorted([p for p in section_path.iterdir() if p.suffix.lower() == ".mp4"])
                        if mp4_files:
                            video_path = mp4_files[0]

                    if video_path:
                        escaped = str(video_path).replace("'", "'\\''")
                        f.write(f"file '{escaped}'\n")
                        added_videos += 1

            if added_videos == 0:
                raise RuntimeError("No section videos found for startup combine")

            # Run ffmpeg
            final_video_path = job_output_dir / "final_video.mp4"
            cmd = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(concat_list_path), "-c", "copy", str(final_video_path)
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await process.wait()

            if final_video_path.exists():
                # Calculate total duration and chapters
                total_duration = sum(s.get("duration_seconds", 0) for s in sections)
                chapters = []
                current_time = 0
                for section in sections:
                    chapters.append({
                        "title": section.get("title", ""),
                        "start_time": current_time,
                        "duration": section.get("duration_seconds", 0)
                    })
                    current_time += section.get("duration_seconds", 0)

                # Generate thumbnail
                thumbnail_url = None
                thumb_path = job_output_dir / "thumbnail.jpg"
                if await generate_thumbnail(str(final_video_path), str(thumb_path), time=min(total_duration/2, 5.0)):
                    thumbnail_url = f"/outputs/{job_id}/thumbnail.jpg"

                video_result = {
                    "video_id": job_id,
                    "title": script.get("title", "Math Video"),
                    "duration": total_duration,
                    "chapters": chapters,
                    "download_url": f"/outputs/{job_id}/final_video.mp4",
                    "thumbnail_url": thumbnail_url
                }

                # Persist video_info.json for Gallery
                video_info = create_video_info_from_result(job_id, video_result)
                save_video_info(video_info)

                self.job_manager.update_job(
                    job_id,
                    JobStatus.COMPLETED,
                    100,
                    "Video generation complete!",
                    result=[video_result]
                )
                logger.info(f"[Startup] Job {job_id} combined and completed")
            else:
                self.job_manager.update_job(job_id, JobStatus.FAILED, message="Failed to combine section videos")

        except Exception as e:
            logger.error(f"[Startup] Error combining job {job_id}", extra={"error": str(e)}, exc_info=True)
            self.job_manager.update_job(job_id, JobStatus.FAILED, message=f"Failed to combine: {str(e)}")
        finally:
            try:
                if concat_list_path.exists():
                    concat_list_path.unlink()
            except Exception:
                pass
