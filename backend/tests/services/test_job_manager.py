
import pytest
import shutil
from pathlib import Path
from app.services.infrastructure.orchestration import JobManager, Job, JobStatus

@pytest.fixture
def job_manager(tmp_path):
    # Use a temp directory for storage
    storage_dir = tmp_path / "job_data"
    manager = JobManager(str(storage_dir))
    return manager

def test_create_job(job_manager):
    job = job_manager.create_job("job_1")
    assert job.id == "job_1"
    assert job.status == JobStatus.PENDING
    
    # Check persistence
    loaded = job_manager.get_job("job_1")
    assert loaded is not None
    assert loaded.id == "job_1"

def test_update_job(job_manager):
    job = job_manager.create_job("job_1")
    
    job_manager.update_job(
        "job_1", 
        status=JobStatus.COMPLETED,
        progress=1.0, 
        message="Done"
    )
    
    updated = job_manager.get_job("job_1")
    assert updated.status == JobStatus.COMPLETED
    assert updated.progress == 1.0
    assert updated.message == "Done"

def test_interrupted_jobs(job_manager):
    # active job
    job1 = job_manager.create_job("j1")
    job1.status = JobStatus.ANALYZING
    job_manager._save_job(job1)
    
    # completed job
    job2 = job_manager.create_job("j2")
    job2.status = JobStatus.COMPLETED
    job_manager._save_job(job2)
    
    # Reload logic via new manager instance
    # But here we can just use the method directly
    interrupted = job_manager.get_interrupted_jobs()
    assert len(interrupted) == 1
    assert interrupted[0].id == "j1"
    
    job_manager.mark_interrupted_jobs_failed()
    
    job1_updated = job_manager.get_job("j1")
    assert job1_updated.status == JobStatus.FAILED
    
    job2_updated = job_manager.get_job("j2")
    assert job2_updated.status == JobStatus.COMPLETED

def test_delete_job(job_manager):
    job = job_manager.create_job("del_job")
    data = job_manager.delete_job("del_job")
    
    assert data["id"] == "del_job"
    assert job_manager.get_job("del_job") is None
