"""
Output cleanup service.

Deletes expired output directories and stale job metadata to prevent
unbounded disk growth.
"""

import asyncio
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from app.core import get_logger
from app.models.status import JobStatus
from app.services.infrastructure.orchestration import JobManager

logger = get_logger(__name__, component="output_cleanup")


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, minimum: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return max(int(raw), minimum)
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float, minimum: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return max(float(raw), minimum)
    except (TypeError, ValueError):
        return default


class OutputCleanupService:
    """Cleanup old output artifacts and stale job records."""

    def __init__(self, output_dir: Path, job_manager: JobManager, upload_dir: Path | None = None):
        self.output_dir = Path(output_dir)
        self.upload_dir = Path(upload_dir) if upload_dir is not None else None
        self.job_manager = job_manager

        self.enabled = _env_bool("OUTPUT_CLEANUP_ENABLED", True)
        self.keep_only_final = _env_bool("OUTPUT_KEEP_ONLY_FINAL", True)
        self.completed_ttl_hours = _env_float("OUTPUT_RETENTION_HOURS", 168.0, 1.0)
        self.failed_ttl_hours = _env_float("FAILED_OUTPUT_RETENTION_HOURS", 48.0, 1.0)
        self.orphan_ttl_hours = _env_float("ORPHAN_OUTPUT_RETENTION_HOURS", 24.0, 1.0)
        self.metadata_ttl_hours = _env_float("JOB_METADATA_RETENTION_HOURS", 168.0, 1.0)
        self.max_deletions = _env_int("OUTPUT_CLEANUP_MAX_DELETIONS", 100, 1)
        self.interval_minutes = _env_int("OUTPUT_CLEANUP_INTERVAL_MINUTES", 60, 1)
        self.upload_cleanup_enabled = _env_bool("UPLOAD_CLEANUP_ENABLED", True)
        self.upload_retention_hours = _env_float("UPLOAD_RETENTION_HOURS", 168.0, 1.0)
        self.upload_max_deletions = _env_int("UPLOAD_CLEANUP_MAX_DELETIONS", 100, 1)

    @staticmethod
    def _hours_since(unix_ts: float, now_ts: float) -> float:
        return max(0.0, (now_ts - unix_ts) / 3600.0)

    @staticmethod
    def _parse_iso(ts: str) -> datetime | None:
        try:
            return datetime.fromisoformat(ts)
        except Exception:
            return None

    @staticmethod
    def _is_active_status(status: str) -> bool:
        return status in {
            JobStatus.PENDING.value,
            JobStatus.ANALYZING.value,
            JobStatus.GENERATING_SCRIPT.value,
            JobStatus.CREATING_ANIMATIONS.value,
            JobStatus.SYNTHESIZING_AUDIO.value,
            JobStatus.COMPOSING_VIDEO.value,
        }

    def _should_delete_output(self, status: str | None, age_hours: float) -> bool:
        if status is None:
            return age_hours >= self.orphan_ttl_hours
        if self._is_active_status(status):
            return False
        if status == JobStatus.COMPLETED.value:
            if self.keep_only_final:
                return False
            return age_hours >= self.completed_ttl_hours
        if status in {JobStatus.FAILED.value, JobStatus.INTERRUPTED.value}:
            return age_hours >= self.failed_ttl_hours
        return False

    @staticmethod
    def _prune_translation_dirs(translations_dir: Path) -> int:
        """
        Keep only final_video.mp4 in each translation language folder.
        """
        removed_count = 0
        if not translations_dir.exists() or not translations_dir.is_dir():
            return removed_count

        for lang_dir in translations_dir.iterdir():
            if not lang_dir.is_dir():
                lang_dir.unlink(missing_ok=True)
                removed_count += 1
                continue

            # Keep in-progress translation directories intact.
            # A translation is considered complete only when final_video.mp4 exists.
            if not (lang_dir / "final_video.mp4").exists():
                continue

            for entry in lang_dir.iterdir():
                if entry.name == "final_video.mp4":
                    continue
                if entry.is_dir():
                    shutil.rmtree(entry)
                    removed_count += 1
                else:
                    entry.unlink(missing_ok=True)
                    removed_count += 1

        return removed_count

    @classmethod
    def _prune_to_final_video(cls, output_path: Path) -> int:
        """
        Keep only final_video.mp4 (and translations/) in a completed job folder.
        """
        removed_count = 0
        keep_entries = {"final_video.mp4", "video_info.json", "error_info.json", "translations"}

        for entry in output_path.iterdir():
            if entry.name in keep_entries:
                if entry.name == "translations" and entry.is_dir():
                    removed_count += cls._prune_translation_dirs(entry)
                continue
            if entry.is_dir():
                shutil.rmtree(entry)
                removed_count += 1
            else:
                entry.unlink(missing_ok=True)
                removed_count += 1

        return removed_count

    def _cleanup_uploads(self, now_ts: float) -> Dict[str, int]:
        summary = {"deleted_uploads": 0, "upload_errors": 0}

        if not self.upload_cleanup_enabled or self.upload_dir is None:
            return summary

        if not self.upload_dir.exists():
            return summary

        deletions_left = self.upload_max_deletions
        for upload_file in sorted(self.upload_dir.iterdir(), key=lambda p: p.stat().st_mtime):
            if deletions_left <= 0:
                break
            if not upload_file.is_file():
                continue

            age_hours = self._hours_since(upload_file.stat().st_mtime, now_ts)
            if age_hours < self.upload_retention_hours:
                continue

            try:
                upload_file.unlink(missing_ok=True)
                summary["deleted_uploads"] += 1
                deletions_left -= 1
            except Exception as exc:
                logger.warning(
                    "Failed to remove upload file",
                    extra={"path": str(upload_file), "error": str(exc)},
                )
                summary["upload_errors"] += 1

        return summary

    def run_once(self) -> Dict[str, Any]:
        """Run one cleanup pass and return summary statistics."""
        summary = {
            "enabled": self.enabled,
            "keep_only_final": self.keep_only_final,
            "upload_cleanup_enabled": self.upload_cleanup_enabled,
            "deleted_output_dirs": 0,
            "pruned_artifacts": 0,
            "deleted_uploads": 0,
            "deleted_job_records": 0,
            "errors": 0,
        }

        if not self.enabled:
            return summary

        if not self.output_dir.exists():
            return summary

        now_ts = datetime.now().timestamp()
        jobs_by_id = {job["id"]: job for job in self.job_manager.list_all_jobs()}
        deletions_left = self.max_deletions

        output_dirs = [p for p in self.output_dir.iterdir() if p.is_dir()]
        output_dirs.sort(key=lambda p: p.stat().st_mtime)

        for output_path in output_dirs:
            if deletions_left <= 0:
                break

            job_id = output_path.name
            job = jobs_by_id.get(job_id)
            status = job.get("status") if job else None
            age_hours = self._hours_since(output_path.stat().st_mtime, now_ts)

            if (
                status is None
                and self.keep_only_final
                and (output_path / "final_video.mp4").exists()
            ):
                try:
                    summary["pruned_artifacts"] += self._prune_to_final_video(output_path)
                    deletions_left -= 1
                except Exception as exc:
                    logger.warning(
                        "Failed to prune orphan output directory with final video",
                        extra={"job_id": job_id, "path": str(output_path), "error": str(exc)},
                    )
                    summary["errors"] += 1
                continue

            if status == JobStatus.COMPLETED.value and self.keep_only_final:
                try:
                    summary["pruned_artifacts"] += self._prune_to_final_video(output_path)
                    deletions_left -= 1
                except Exception as exc:
                    logger.warning(
                        "Failed to prune completed output directory",
                        extra={"job_id": job_id, "path": str(output_path), "error": str(exc)},
                    )
                    summary["errors"] += 1
                continue

            if not self._should_delete_output(status, age_hours):
                continue

            try:
                shutil.rmtree(output_path)
                summary["deleted_output_dirs"] += 1
                deletions_left -= 1
            except Exception as exc:
                logger.warning(
                    "Failed to remove output directory",
                    extra={"job_id": job_id, "path": str(output_path), "error": str(exc)},
                )
                summary["errors"] += 1
                continue

            if job:
                self.job_manager.delete_job(job_id)
                summary["deleted_job_records"] += 1

        if deletions_left > 0:
            for job in self.job_manager.list_all_jobs():
                if deletions_left <= 0:
                    break

                job_id = job["id"]
                output_path = self.output_dir / job_id
                if output_path.exists():
                    continue

                status = job.get("status")
                if self._is_active_status(status):
                    continue

                updated_at = self._parse_iso(job.get("updated_at", ""))
                if not updated_at:
                    continue

                age_hours = self._hours_since(updated_at.timestamp(), now_ts)
                if age_hours < self.metadata_ttl_hours:
                    continue

                self.job_manager.delete_job(job_id)
                summary["deleted_job_records"] += 1
                deletions_left -= 1

        upload_summary = self._cleanup_uploads(now_ts)
        summary["deleted_uploads"] += upload_summary["deleted_uploads"]
        summary["errors"] += upload_summary["upload_errors"]

        logger.info("Output cleanup pass complete", extra=summary)
        return summary

    async def run_periodic(self) -> None:
        """Run cleanup in a periodic background loop."""
        if not self.enabled:
            logger.info("Output cleanup disabled by environment")
            return

        interval_seconds = self.interval_minutes * 60
        while True:
            try:
                self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("Output cleanup loop failed", extra={"error": str(exc)}, exc_info=True)
            await asyncio.sleep(interval_seconds)
