import os
import time
from pathlib import Path

from app.models.status import JobStatus
from app.services.infrastructure.orchestration.job_manager import JobManager
from app.services.infrastructure.storage.output_cleanup import OutputCleanupService


def _set_old_mtime(path: Path, hours_ago: float) -> None:
    ts = time.time() - (hours_ago * 3600)
    os.utime(path, (ts, ts))


def test_cleanup_prunes_completed_output_to_final_video_only(tmp_path, monkeypatch):
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    job_data_dir = tmp_path / "job_data"
    job_manager = JobManager(storage_dir=str(job_data_dir), cache_limit=10)

    job_id = "completed-job"
    job_manager.create_job(job_id)
    job_manager.update_job(job_id, status=JobStatus.COMPLETED, progress=100)

    job_output = output_dir / job_id
    job_output.mkdir()
    (job_output / "final_video.mp4").write_text("video")
    (job_output / "script.json").write_text("{}")
    (job_output / "temp.txt").write_text("tmp")
    (job_output / "sections").mkdir()
    (job_output / "translations").mkdir()
    (job_output / "translations" / "es").mkdir()
    (job_output / "translations" / "es" / "final_video.mp4").write_text("translated")
    (job_output / "translations" / "es" / "script.json").write_text("{}")
    (job_output / "translations" / "es" / "section_0").mkdir()
    _set_old_mtime(job_output, hours_ago=2)

    monkeypatch.setenv("OUTPUT_CLEANUP_ENABLED", "true")
    monkeypatch.setenv("OUTPUT_KEEP_ONLY_FINAL", "true")
    monkeypatch.setenv("OUTPUT_RETENTION_HOURS", "1")
    monkeypatch.setenv("FAILED_OUTPUT_RETENTION_HOURS", "1")
    monkeypatch.setenv("ORPHAN_OUTPUT_RETENTION_HOURS", "1")
    monkeypatch.setenv("JOB_METADATA_RETENTION_HOURS", "1")

    service = OutputCleanupService(output_dir=output_dir, job_manager=job_manager)
    summary = service.run_once()

    assert summary["deleted_output_dirs"] == 0
    assert summary["deleted_job_records"] == 0
    assert summary["pruned_artifacts"] >= 2
    assert (job_output / "final_video.mp4").exists()
    assert (job_output / "translations").exists()
    assert (job_output / "translations" / "es" / "final_video.mp4").exists()
    assert not (job_output / "translations" / "es" / "script.json").exists()
    assert not (job_output / "translations" / "es" / "section_0").exists()
    assert not (job_output / "sections").exists()
    assert not (job_output / "script.json").exists()
    assert job_manager.get_job(job_id) is not None


def test_cleanup_keeps_active_job_outputs(tmp_path, monkeypatch):
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    job_data_dir = tmp_path / "job_data"
    job_manager = JobManager(storage_dir=str(job_data_dir), cache_limit=10)

    job_id = "active-job"
    job_manager.create_job(job_id)
    job_manager.update_job(job_id, status=JobStatus.CREATING_ANIMATIONS, progress=50)

    job_output = output_dir / job_id
    job_output.mkdir()
    _set_old_mtime(job_output, hours_ago=48)

    monkeypatch.setenv("OUTPUT_CLEANUP_ENABLED", "true")
    monkeypatch.setenv("OUTPUT_KEEP_ONLY_FINAL", "true")
    monkeypatch.setenv("OUTPUT_RETENTION_HOURS", "1")
    monkeypatch.setenv("FAILED_OUTPUT_RETENTION_HOURS", "1")
    monkeypatch.setenv("ORPHAN_OUTPUT_RETENTION_HOURS", "1")
    monkeypatch.setenv("JOB_METADATA_RETENTION_HOURS", "1")

    service = OutputCleanupService(output_dir=output_dir, job_manager=job_manager)
    summary = service.run_once()

    assert summary["deleted_output_dirs"] == 0
    assert summary["deleted_job_records"] == 0
    assert job_output.exists()
    assert job_manager.get_job(job_id) is not None


def test_cleanup_deletes_old_orphan_output(tmp_path, monkeypatch):
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    job_data_dir = tmp_path / "job_data"
    job_manager = JobManager(storage_dir=str(job_data_dir), cache_limit=10)

    orphan_output = output_dir / "orphan-job"
    orphan_output.mkdir()
    _set_old_mtime(orphan_output, hours_ago=12)

    monkeypatch.setenv("OUTPUT_CLEANUP_ENABLED", "true")
    monkeypatch.setenv("OUTPUT_KEEP_ONLY_FINAL", "true")
    monkeypatch.setenv("ORPHAN_OUTPUT_RETENTION_HOURS", "1")

    service = OutputCleanupService(output_dir=output_dir, job_manager=job_manager)
    summary = service.run_once()

    assert summary["deleted_output_dirs"] == 1
    assert not orphan_output.exists()


def test_cleanup_deletes_old_upload_files(tmp_path, monkeypatch):
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir()
    job_data_dir = tmp_path / "job_data"
    job_manager = JobManager(storage_dir=str(job_data_dir), cache_limit=10)

    old_upload = uploads_dir / "old.pdf"
    old_upload.write_text("x")
    _set_old_mtime(old_upload, hours_ago=24)

    fresh_upload = uploads_dir / "fresh.pdf"
    fresh_upload.write_text("x")
    _set_old_mtime(fresh_upload, hours_ago=1)

    monkeypatch.setenv("OUTPUT_CLEANUP_ENABLED", "true")
    monkeypatch.setenv("UPLOAD_CLEANUP_ENABLED", "true")
    monkeypatch.setenv("UPLOAD_RETENTION_HOURS", "4")
    monkeypatch.setenv("UPLOAD_CLEANUP_MAX_DELETIONS", "10")

    service = OutputCleanupService(
        output_dir=output_dir,
        job_manager=job_manager,
        upload_dir=uploads_dir,
    )
    summary = service.run_once()

    assert summary["deleted_uploads"] == 1
    assert not old_upload.exists()
    assert fresh_upload.exists()
