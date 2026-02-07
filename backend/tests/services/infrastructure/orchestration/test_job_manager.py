"""
Tests for app.services.infrastructure.orchestration.job_manager

Tests job tracking and file-based persistence.
"""

import json
import pytest
from app.services.infrastructure.orchestration.job_manager import Job, JobManager, JobStatus


class TestJob:
    """Test the Job data model."""

    def test_job_to_dict(self):
        """Test conversion to dictionary."""
        job = Job(id="test-1", status=JobStatus.COMPLETED, progress=100.0)
        d = job.to_dict()
        assert d["id"] == "test-1"
        assert d["status"] == "completed"
        assert d["progress"] == 100.0
        assert "created_at" in d
        assert "updated_at" in d

    def test_job_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "id": "test-2",
            "status": "failed",
            "progress": 50.0,
            "message": "Error encountered",
            "error": "Timeout"
        }
        job = Job.from_dict(data)
        assert job.id == "test-2"
        assert job.status == JobStatus.FAILED
        assert job.progress == 50.0
        assert job.error == "Timeout"


class TestJobManager:
    """Test the JobManager with file persistence."""

    @pytest.fixture
    def temp_job_dir(self, tmp_path):
        """Create a temporary directory for job data."""
        return tmp_path / "job_data"

    @pytest.fixture
    def manager(self, temp_job_dir):
        """Initialize JobManager with temporary directory."""
        return JobManager(storage_dir=str(temp_job_dir))

    def test_create_job_persists_to_disk(self, manager, temp_job_dir):
        """Verify that creating a job creates a file."""
        manager.create_job("job-abc")
        job_file = temp_job_dir / "job-abc.json"
        
        assert job_file.exists()
        with open(job_file, "r") as f:
            data = json.load(f)
            assert data["id"] == "job-abc"
            assert data["status"] == "pending"

    def test_update_job_updates_disk(self, manager, temp_job_dir):
        """Verify that updating a job updates the file."""
        manager.create_job("job-123")
        manager.update_job("job-123", status=JobStatus.COMPLETED, progress=100.0)
        
        job_file = temp_job_dir / "job-123.json"
        with open(job_file, "r") as f:
            data = json.load(f)
            assert data["status"] == "completed"
            assert data["progress"] == 100.0

    def test_delete_job_removes_from_disk(self, manager, temp_job_dir):
        """Verify that deleting a job removes the file."""
        manager.create_job("to-delete")
        job_file = temp_job_dir / "to-delete.json"
        assert job_file.exists()
        
        manager.delete_job("to-delete")
        assert not job_file.exists()
        assert manager.get_job("to-delete") is None

    def test_load_jobs_on_startup(self, temp_job_dir):
        """Verify that existing job files are loaded on manager initialization."""
        # Pre-create a job file
        job_data = {
            "id": "existing-job",
            "status": "completed",
            "progress": 100.0,
            "message": "Done",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00"
        }
        temp_job_dir.mkdir(parents=True, exist_ok=True)
        with open(temp_job_dir / "existing-job.json", "w") as f:
            json.dump(job_data, f)
            
        # Initialize new manager
        manager = JobManager(storage_dir=str(temp_job_dir))
        job = manager.get_job("existing-job")
        
        assert job is not None
        assert job.status == JobStatus.COMPLETED
        assert job.id == "existing-job"

    def test_get_interrupted_jobs(self, manager):
        """Test filtering of interrupted jobs."""
        manager.create_job("pending-job")
        manager.update_job("pending-job", status=JobStatus.PENDING)
        
        manager.create_job("done-job")
        manager.update_job("done-job", status=JobStatus.COMPLETED)
        
        interrupted = manager.get_interrupted_jobs()
        assert len(interrupted) >= 1
        ids = [j.id for j in interrupted]
        assert "pending-job" in ids
        assert "done-job" not in ids

    def test_mark_interrupted_jobs_failed(self, manager):
        """Test bulk failing of interrupted jobs."""
        manager.create_job("halted-job")
        manager.update_job("halted-job", status=JobStatus.ANALYZING)
        
        manager.mark_interrupted_jobs_failed()
        
        job = manager.get_job("halted-job")
        assert job.status == JobStatus.FAILED
        assert "interrupted" in job.message.lower()

    def test_list_all_jobs(self, manager):
        """Test listing jobs as dicts."""
        manager.create_job("j1")
        manager.create_job("j2")
        
        job_list = manager.list_all_jobs()
        assert len(job_list) == 2
        assert any(j["id"] == "j1" for j in job_list)
        assert any(j["id"] == "j2" for j in job_list)

    def test_load_jobs_handles_corrupt_file(self, temp_job_dir, capsys):
        """Test that corrupt JSON files don't crash the manager."""
        temp_job_dir.mkdir(parents=True, exist_ok=True)
        with open(temp_job_dir / "corrupt.json", "w") as f:
            f.write("not json")
            
        manager = JobManager(storage_dir=str(temp_job_dir))
        # Should have captured error output or at least not crashed
        # manager._jobs should be empty
        assert len(manager.get_all_jobs()) == 0
        captured = capsys.readouterr()
        assert "Error loading job" in captured.out

    def test_cache_is_bounded_for_terminal_jobs(self, temp_job_dir):
        """Completed jobs should not grow in-memory cache without bound."""
        manager = JobManager(storage_dir=str(temp_job_dir), cache_limit=25)

        for i in range(80):
            job_id = f"job-{i}"
            manager.create_job(job_id)
            manager.update_job(job_id, status=JobStatus.COMPLETED, progress=100.0)

        # Access all records from disk-backed listing
        jobs = manager.list_all_jobs()
        assert len(jobs) == 80

        # Cache should stay bounded by cache_limit for terminal jobs
        assert len(manager._jobs) <= 25
