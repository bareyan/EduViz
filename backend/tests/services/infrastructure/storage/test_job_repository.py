"""
Tests for app.services.infrastructure.storage.job_repository

Tests the JobRepository abstraction and its FileBasedJobRepository implementation.
"""

import pytest
from unittest.mock import MagicMock, patch
from app.services.infrastructure.storage.job_repository import (
    JobRecord,
    FileBasedJobRepository,
    JobRepository
)
from app.services.infrastructure.orchestration.job_manager import JobStatus


class TestJobRecord:
    """Test JobRecord dataclass."""

    def test_job_record_init(self):
        """Test basic initialization."""
        record = JobRecord(
            id="test-id",
            status="pending",
            progress=0.0,
            message="Starting",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z"
        )
        assert record.id == "test-id"
        assert record.status == "pending"
        assert record.progress == 0.0
        assert record.result is None
        assert record.error is None

    def test_job_record_with_optional(self):
        """Test initialization with optional fields."""
        record = JobRecord(
            id="test-id",
            status="completed",
            progress=100.0,
            message="Done",
            created_at="now",
            updated_at="now",
            result=[{"url": "file.mp4"}],
            error="None"
        )
        assert record.result == [{"url": "file.mp4"}]
        assert record.error == "None"


class TestFileBasedJobRepository:
    """Test FileBasedJobRepository implementation."""

    @pytest.fixture
    def mock_job_manager(self):
        """Mock the JobManager returned by get_job_manager."""
        with patch("app.services.infrastructure.storage.job_repository.get_job_manager") as mock_get:
            mock_mgr = MagicMock()
            mock_get.return_value = mock_mgr
            yield mock_mgr

    @pytest.fixture
    def repository(self, mock_job_manager):
        """Create repository with mocked manager."""
        return FileBasedJobRepository()

    def test_create_job(self, repository, mock_job_manager):
        """Test creating a job."""
        mock_job = MagicMock()
        mock_job.id = "job-1"
        mock_job.status = JobStatus.PENDING
        mock_job.progress = 0.0
        mock_job.message = "Created"
        mock_job.result = None
        mock_job.error = None
        mock_job.created_at = "2024-01-01"
        mock_job.updated_at = "2024-01-01"
        
        mock_job_manager.create_job.return_value = mock_job
        
        record = repository.create("job-1")
        
        mock_job_manager.create_job.assert_called_once_with("job-1")
        assert isinstance(record, JobRecord)
        assert record.id == "job-1"
        assert record.status == "pending"

    def test_get_job(self, repository, mock_job_manager):
        """Test retrieving a job."""
        mock_job = MagicMock()
        mock_job.id = "job-1"
        mock_job.status = JobStatus.COMPLETED
        mock_job.progress = 100.0
        mock_job.message = "Done"
        mock_job.result = ["data"]
        mock_job.error = None
        mock_job.created_at = "2024-01-01"
        mock_job.updated_at = "2024-01-01"
        
        mock_job_manager.get_job.return_value = mock_job
        
        record = repository.get("job-1")
        
        mock_job_manager.get_job.assert_called_with("job-1")
        assert record.status == "completed"
        assert record.result == ["data"]

    def test_get_job_not_found(self, repository, mock_job_manager):
        """Test retrieving non-existent job."""
        mock_job_manager.get_job.return_value = None
        assert repository.get("none") is None

    def test_update_job(self, repository, mock_job_manager):
        """Test updating a job."""
        # Setup get_job to return a mocked job after update
        mock_job = MagicMock()
        mock_job.id = "job-1"
        mock_job.status = JobStatus.ANALYZING
        mock_job.progress = 25.0
        mock_job.message = "Working"
        mock_job.result = None
        mock_job.error = None
        mock_job.created_at = "2024-01-01"
        mock_job.updated_at = "2024-01-01"
        mock_job_manager.get_job.return_value = mock_job
        
        record = repository.update("job-1", status="analyzing", progress=25.0, message="Working")
        
        mock_job_manager.update_job.assert_called_once_with(
            "job-1", JobStatus.ANALYZING, 25.0, "Working", None, None
        )
        assert record.status == "analyzing"
        assert record.progress == 25.0

    def test_list_all(self, repository, mock_job_manager):
        """Test listing all jobs."""
        mock_job_manager.list_all_jobs.return_value = [{"id": "j1"}, {"id": "j2"}]
        
        m1 = MagicMock(id="j1")
        m2 = MagicMock(id="j2")
        # Configure get_job to return different mocks for different IDs
        mock_job_manager.get_job.side_effect = lambda x: m1 if x == "j1" else m2
        
        records = repository.list_all()
        
        assert len(records) == 2
        assert records[0].id == "j1"
        assert records[1].id == "j2"

    def test_list_completed(self, repository, mock_job_manager):
        """Test listing only completed jobs."""
        mock_job_manager.list_all_jobs.return_value = [
            {"id": "j1", "status": "completed"},
            {"id": "j2", "status": "failed"}
        ]
        
        m1 = MagicMock(id="j1", status=JobStatus.COMPLETED)
        mock_job_manager.get_job.side_effect = lambda x: m1 if x == "j1" else None
        
        records = repository.list_completed()
        
        assert len(records) == 1
        assert records[0].id == "j1"

    def test_delete_job(self, repository, mock_job_manager):
        """Test deleting a job."""
        mock_job_manager.delete_job.return_value = MagicMock()
        assert repository.delete("j1") is True
        
        mock_job_manager.delete_job.return_value = None
        assert repository.delete("j2") is False

    def test_abtract_instantiation_fails(self):
        """Verify JobRepository cannot be instantiated directly."""
        with pytest.raises(TypeError):
            JobRepository()
