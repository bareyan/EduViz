"""
Job Manager - Track video generation jobs with file-based persistence.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Optional

from app.config import JOB_DATA_DIR
from app.models.status import JobStatus


def _env_int(name: str, default: int, minimum: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return max(int(raw), minimum)
    except (TypeError, ValueError):
        return default


ACTIVE_STATUSES = {
    JobStatus.PENDING,
    JobStatus.ANALYZING,
    JobStatus.GENERATING_SCRIPT,
    JobStatus.CREATING_ANIMATIONS,
    JobStatus.SYNTHESIZING_AUDIO,
    JobStatus.COMPOSING_VIDEO,
}


@dataclass
class Job:
    id: str
    status: JobStatus = JobStatus.PENDING
    progress: float = 0.0
    message: str = "Job created"
    result: Optional[List[Any]] = None
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status.value,
            "progress": self.progress,
            "message": self.message,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Job":
        return cls(
            id=data["id"],
            status=JobStatus(data["status"]),
            progress=data.get("progress", 0.0),
            message=data.get("message", ""),
            result=data.get("result"),
            error=data.get("error"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
        )


class JobManager:
    """Manages video generation jobs with disk-first persistence and bounded RAM cache."""

    def __init__(self, storage_dir: Optional[str] = None, cache_limit: Optional[int] = None):
        self._storage_dir = Path(storage_dir) if storage_dir else JOB_DATA_DIR
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._cache_limit = cache_limit if cache_limit is not None else _env_int("JOB_MANAGER_CACHE_LIMIT", 200, 25)

        self._jobs: Dict[str, Job] = {}
        self._known_job_ids: set[str] = set()
        self._lock = RLock()

        self._index_jobs()

    def _index_jobs(self) -> None:
        """Build an index of known jobs from disk without loading full payloads."""
        with self._lock:
            self._known_job_ids = {job_file.stem for job_file in self._storage_dir.glob("*.json")}

    def _job_file(self, job_id: str) -> Path:
        return self._storage_dir / f"{job_id}.json"

    def _load_job_from_disk(self, job_id: str) -> Optional[Job]:
        job_file = self._job_file(job_id)
        if not job_file.exists():
            return None
        try:
            with open(job_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Job.from_dict(data)
        except Exception as e:
            print(f"Error loading job {job_file}: {e}")
            return None

    @staticmethod
    def _is_active_status(status: JobStatus) -> bool:
        return status in ACTIVE_STATUSES

    @staticmethod
    def _sort_key_updated(job: Job) -> datetime:
        try:
            return datetime.fromisoformat(job.updated_at)
        except Exception:
            return datetime.min

    def _prune_cache(self) -> None:
        if len(self._jobs) <= self._cache_limit:
            return

        evictable_ids = [
            job_id
            for job_id, job in self._jobs.items()
            if not self._is_active_status(job.status)
        ]
        evictable_ids.sort(key=lambda j: self._sort_key_updated(self._jobs[j]))

        while len(self._jobs) > self._cache_limit and evictable_ids:
            stale_id = evictable_ids.pop(0)
            self._jobs.pop(stale_id, None)

    def _cache_job(self, job: Job) -> None:
        self._jobs[job.id] = job
        self._prune_cache()

    def _save_job(self, job: Job) -> None:
        """Save a job to disk."""
        job_file = self._job_file(job.id)
        try:
            with open(job_file, "w", encoding="utf-8") as f:
                json.dump(job.to_dict(), f, indent=2, ensure_ascii=False)
            self._known_job_ids.add(job.id)
        except Exception as e:
            print(f"Error saving job {job.id}: {e}")

    def get_interrupted_jobs(self) -> List[Job]:
        """Get jobs that were in progress when server stopped."""
        with self._lock:
            interrupted: List[Job] = []
            for job_id in list(self._known_job_ids):
                job = self._jobs.get(job_id) or self._load_job_from_disk(job_id)
                if not job:
                    continue
                if job.status in ACTIVE_STATUSES:
                    interrupted.append(job)
                    self._cache_job(job)
            return interrupted

    def mark_interrupted_jobs_failed(self) -> None:
        """Mark all interrupted jobs as failed."""
        for job in self.get_interrupted_jobs():
            job.status = JobStatus.FAILED
            job.message = "Job was interrupted by server restart"
            job.updated_at = datetime.now().isoformat()
            with self._lock:
                self._save_job(job)
                self._cache_job(job)

    def create_job(self, job_id: str) -> Job:
        """Create a new job."""
        with self._lock:
            job = Job(id=job_id)
            self._save_job(job)
            self._cache_job(job)
            return job

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        with self._lock:
            cached = self._jobs.get(job_id)
            if cached:
                return cached

            if job_id not in self._known_job_ids:
                return None

            job = self._load_job_from_disk(job_id)
            if not job:
                self._known_job_ids.discard(job_id)
                return None

            if self._is_active_status(job.status) or len(self._jobs) < self._cache_limit:
                self._cache_job(job)
            return job

    def update_job(
        self,
        job_id: str,
        status: Optional[JobStatus] = None,
        progress: Optional[float] = None,
        message: Optional[str] = None,
        result: Optional[List[Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """Update job status."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                if job_id not in self._known_job_ids:
                    return
                job = self._load_job_from_disk(job_id)
                if not job:
                    self._known_job_ids.discard(job_id)
                    return

            if status is not None:
                job.status = status
            if progress is not None:
                job.progress = progress
            if message is not None:
                job.message = message
            if result is not None:
                job.result = result
            if error is not None:
                job.error = error

            job.updated_at = datetime.now().isoformat()
            self._save_job(job)
            self._cache_job(job)

    def delete_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Delete a job and return its data."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job and job_id in self._known_job_ids:
                job = self._load_job_from_disk(job_id)

            job_data = job.to_dict() if job else None

            self._jobs.pop(job_id, None)
            self._known_job_ids.discard(job_id)

            job_file = self._job_file(job_id)
            if job_file.exists():
                job_file.unlink()

            return job_data

    def get_all_jobs(self) -> List[Job]:
        """Get all jobs from persistent storage."""
        with self._lock:
            job_ids = sorted(self._known_job_ids)

        all_jobs: List[Job] = []
        for job_id in job_ids:
            job = self.get_job(job_id)
            if job:
                all_jobs.append(job)
        return all_jobs

    def list_all_jobs(self) -> List[Dict[str, Any]]:
        """List all jobs as dictionaries."""
        return [job.to_dict() for job in self.get_all_jobs()]


_job_manager_instance: Optional[JobManager] = None


def get_job_manager() -> JobManager:
    """Get the shared JobManager instance (singleton pattern)."""
    global _job_manager_instance
    if _job_manager_instance is None:
        _job_manager_instance = JobManager()
    return _job_manager_instance
