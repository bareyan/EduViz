"""
Job repository - Abstract data access for jobs.

Implements the Repository pattern to decouple job data access from business logic.
This abstraction enables:
    - Easy testing with mock repositories
    - Future migration to database without changing routes
    - Consistent job data handling across the application

The FileBasedJobRepository uses the existing JobManager as the underlying
implementation, but other implementations (e.g., DatabaseJobRepository) can
be swapped in without affecting the rest of the application.

Classes:
    JobRecord: Data model for job information
    JobRepository: Abstract interface for job data access
    FileBasedJobRepository: File-based implementation using JobManager
"""

from abc import ABC, abstractmethod
from typing import Any, List, Optional
from dataclasses import dataclass

from app.services.infrastructure.orchestration.job_manager import JobStatus, get_job_manager


@dataclass
class JobRecord:
    """
    Data model representing a job's state and metadata.
    
    Attributes:
        id: Unique job identifier
        status: Current job status (pending, analyzing, completed, failed, etc.)
        progress: Progress as percentage (0-100)
        message: Human-readable status message
        created_at: ISO timestamp of job creation
        updated_at: ISO timestamp of last update
        result: Result data if job completed successfully
        error: Error message if job failed
    """
    id: str
    status: str
    progress: float
    message: str
    created_at: str
    updated_at: str
    result: Optional[List[Any]] = None
    error: Optional[str] = None


class JobRepository(ABC):
    """
    Abstract repository for job data access.
    
    Defines the interface that all job repository implementations must follow.
    This abstraction decouples the application from the underlying data storage.
    """

    @abstractmethod
    def create(self, job_id: str) -> JobRecord:
        """
        Create a new job.
        
        Args:
            job_id: Unique identifier for the job
            
        Returns:
            JobRecord representing the newly created job
        """
        pass

    @abstractmethod
    def get(self, job_id: str) -> Optional[JobRecord]:
        """
        Retrieve a job by ID.
        
        Args:
            job_id: Unique job identifier
            
        Returns:
            JobRecord if found, None otherwise
        """
        pass

    @abstractmethod
    def update(
        self,
        job_id: str,
        status: Optional[str] = None,
        progress: Optional[float] = None,
        message: Optional[str] = None,
        result: Optional[List[Any]] = None,
        error: Optional[str] = None,
    ) -> JobRecord:
        """
        Update a job's status and/or progress.
        
        Args:
            job_id: Unique job identifier
            status: New status if provided
            progress: New progress percentage if provided
            message: New status message if provided
            result: Result data if provided
            error: Error message if provided
            
        Returns:
            Updated JobRecord
        """
        pass

    @abstractmethod
    def list_all(self) -> List[JobRecord]:
        """
        List all jobs in the system.
        
        Returns:
            List of all JobRecords
        """
        pass

    @abstractmethod
    def list_completed(self) -> List[JobRecord]:
        """
        List only completed jobs.
        
        Returns:
            List of completed JobRecords
        """
        pass

    @abstractmethod
    def delete(self, job_id: str) -> bool:
        """
        Delete a job.
        
        Args:
            job_id: Unique job identifier
            
        Returns:
            True if job was deleted, False if not found
        """
        pass


class FileBasedJobRepository(JobRepository):
    """
    File-based job repository using JobManager.
    
    This implementation stores job data in files using the existing JobManager.
    Can be replaced with DatabaseJobRepository for production use.
    
    Implementation notes:
        - Uses JobManager as the underlying storage mechanism
        - Converts JobManager.Job objects to JobRecord data models
        - All operations are synchronous (could be made async)
    """

    def __init__(self):
        """Initialize the repository with the global JobManager instance."""
        self.job_manager = get_job_manager()

    def create(self, job_id: str) -> JobRecord:
        """Create a new job and return its record."""
        job = self.job_manager.create_job(job_id)
        return self._to_record(job)

    def get(self, job_id: str) -> Optional[JobRecord]:
        """Retrieve a job record by ID."""
        job = self.job_manager.get_job(job_id)
        return self._to_record(job) if job else None

    def update(
        self,
        job_id: str,
        status: Optional[str] = None,
        progress: Optional[float] = None,
        message: Optional[str] = None,
        result: Optional[List[Any]] = None,
        error: Optional[str] = None,
    ) -> JobRecord:
        """Update a job's status and return the updated record."""
        status_enum = JobStatus(status) if status else None
        self.job_manager.update_job(job_id, status_enum, progress, message, result, error)
        job = self.job_manager.get_job(job_id)
        return self._to_record(job)

    def list_all(self) -> List[JobRecord]:
        """Retrieve all jobs in the system."""
        jobs = self.job_manager.list_all_jobs()
        return [self._to_record(self.job_manager.get_job(j["id"])) for j in jobs]

    def list_completed(self) -> List[JobRecord]:
        """Retrieve only completed jobs."""
        jobs = self.job_manager.list_all_jobs()
        return [
            self._to_record(self.job_manager.get_job(j["id"]))
            for j in jobs
            if j.get("status") == "completed"
        ]

    def delete(self, job_id: str) -> bool:
        """Delete a job and return success status."""
        return self.job_manager.delete_job(job_id) is not None

    def _to_record(self, job) -> Optional[JobRecord]:
        """
        Convert a JobManager Job object to a JobRecord data model.
        
        Args:
            job: JobManager.Job object
            
        Returns:
            JobRecord if job is not None, None otherwise
        """
        if not job:
            return None
        return JobRecord(
            id=job.id,
            status=job.status.value,
            progress=job.progress,
            message=job.message,
            result=job.result,
            error=job.error,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
