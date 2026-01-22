"""
Job Manager - Track video generation jobs with file-based persistence
"""

import os
import json
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Dict, Optional, Any, List
from datetime import datetime
from pathlib import Path


class JobStatus(Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    GENERATING_SCRIPT = "generating_script"
    CREATING_ANIMATIONS = "creating_animations"
    SYNTHESIZING_AUDIO = "synthesizing_audio"
    COMPOSING_VIDEO = "composing_video"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


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
            "updated_at": self.updated_at
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
            updated_at=data.get("updated_at", datetime.now().isoformat())
        )


class JobManager:
    """Manages video generation jobs with file-based persistence"""
    
    def __init__(self, storage_dir: str = None):
        self._jobs: Dict[str, Job] = {}
        self._storage_dir = Path(storage_dir) if storage_dir else Path(__file__).parent.parent.parent / "job_data"
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._load_jobs()
    
    def _load_jobs(self):
        """Load jobs from disk on startup"""
        for job_file in self._storage_dir.glob("*.json"):
            try:
                with open(job_file, "r") as f:
                    data = json.load(f)
                    job = Job.from_dict(data)
                    self._jobs[job.id] = job
            except Exception as e:
                print(f"Error loading job {job_file}: {e}")
    
    def get_interrupted_jobs(self) -> List[Job]:
        """Get jobs that were in progress when server stopped"""
        in_progress_statuses = [
            JobStatus.PENDING,
            JobStatus.ANALYZING,
            JobStatus.GENERATING_SCRIPT,
            JobStatus.CREATING_ANIMATIONS,
            JobStatus.SYNTHESIZING_AUDIO,
            JobStatus.COMPOSING_VIDEO
        ]
        return [job for job in self._jobs.values() if job.status in in_progress_statuses]
    
    def mark_interrupted_jobs_failed(self):
        """Mark all interrupted jobs as failed (call on startup if not resuming)"""
        for job in self.get_interrupted_jobs():
            job.status = JobStatus.FAILED
            job.message = "Job was interrupted by server restart"
            job.updated_at = datetime.now().isoformat()
            self._save_job(job)
    
    def _save_job(self, job: Job):
        """Save a job to disk"""
        job_file = self._storage_dir / f"{job.id}.json"
        try:
            with open(job_file, "w") as f:
                json.dump(job.to_dict(), f, indent=2)
        except Exception as e:
            print(f"Error saving job {job.id}: {e}")
    
    def create_job(self, job_id: str) -> Job:
        """Create a new job"""
        job = Job(id=job_id)
        self._jobs[job_id] = job
        self._save_job(job)
        return job
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID"""
        return self._jobs.get(job_id)
    
    def update_job(
        self,
        job_id: str,
        status: Optional[JobStatus] = None,
        progress: Optional[float] = None,
        message: Optional[str] = None,
        result: Optional[List[Any]] = None,
        error: Optional[str] = None
    ):
        """Update job status"""
        job = self._jobs.get(job_id)
        if not job:
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
    
    def delete_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Delete a job and return its data"""
        job = self._jobs.get(job_id)
        job_data = job.to_dict() if job else None
        
        if job_id in self._jobs:
            del self._jobs[job_id]
            job_file = self._storage_dir / f"{job_id}.json"
            if job_file.exists():
                job_file.unlink()
        
        return job_data
    
    def get_all_jobs(self) -> List[Job]:
        """Get all jobs"""
        return list(self._jobs.values())
    
    def list_all_jobs(self) -> List[Dict[str, Any]]:
        """List all jobs as dictionaries (for API responses)"""
        return [job.to_dict() for job in self._jobs.values()]


# Singleton instance - ensures all routes share the same job manager
_job_manager_instance: Optional[JobManager] = None


def get_job_manager() -> JobManager:
    """Get the shared JobManager instance (singleton pattern)"""
    global _job_manager_instance
    if _job_manager_instance is None:
        _job_manager_instance = JobManager()
    return _job_manager_instance
