"""
Unit tests for ProgressTracker
Tests job progress tracking, resume logic, and state persistence
"""

import pytest
import json
from pathlib import Path
from app.services.video_generator.progress import (
    ProgressTracker,
    JobProgress
)


@pytest.fixture
def temp_output_dir(tmp_path):
    """Create temporary output directory"""
    return tmp_path / "jobs"


@pytest.fixture
def job_id():
    """Test job ID"""
    return "test-job-123"


@pytest.fixture
def tracker(job_id, temp_output_dir):
    """Create ProgressTracker instance"""
    return ProgressTracker(
        job_id=job_id,
        output_base_dir=temp_output_dir
    )


def test_tracker_initialization(tracker, job_id, temp_output_dir):
    """Test ProgressTracker initializes correctly"""
    assert tracker.job_id == job_id
    assert tracker.output_base_dir == temp_output_dir
    assert tracker.job_dir == temp_output_dir / job_id
    assert tracker.sections_dir == temp_output_dir / job_id / "sections"
    assert tracker.completed_sections == set()
    assert tracker.total_sections == 0


def test_check_existing_progress_no_job(tracker):
    """Test checking progress for non-existent job"""
    progress = tracker.check_existing_progress()

    assert isinstance(progress, JobProgress)
    assert progress.job_id == tracker.job_id
    assert not progress.has_script
    assert progress.script is None
    assert len(progress.completed_sections) == 0
    assert not progress.has_final_video
    assert progress.total_sections == 0


def test_check_existing_progress_with_script(tracker, tmp_path):
    """Test checking progress with existing script"""
    # Create job directory and script
    tracker.job_dir.mkdir(parents=True)

    script = {
        "title": "Test Video",
        "sections": [
            {"title": "Section 1"},
            {"title": "Section 2"},
            {"title": "Section 3"}
        ]
    }

    script_path = tracker.job_dir / "script.json"
    with open(script_path, "w") as f:
        json.dump(script, f)

    progress = tracker.check_existing_progress()

    assert progress.has_script
    assert progress.script == script
    assert progress.total_sections == 3


def test_check_existing_progress_with_final_video(tracker):
    """Test checking progress with final video"""
    tracker.job_dir.mkdir(parents=True)

    # Create empty final video file
    final_video = tracker.job_dir / "final_video.mp4"
    final_video.touch()

    progress = tracker.check_existing_progress()

    assert progress.has_final_video


def test_check_existing_progress_with_completed_sections(tracker):
    """Test checking progress with completed sections"""
    tracker.job_dir.mkdir(parents=True)
    tracker.sections_dir.mkdir(parents=True)

    # Create script
    script = {
        "sections": [
            {"title": "Section 1"},
            {"title": "Section 2"},
            {"title": "Section 3"}
        ]
    }

    script_path = tracker.job_dir / "script.json"
    with open(script_path, "w") as f:
        json.dump(script, f)

    # Create completed section indicators
    section_0_dir = tracker.sections_dir / "0"
    section_0_dir.mkdir()
    (tracker.sections_dir / "merged_0.mp4").touch()

    section_2_dir = tracker.sections_dir / "2"
    section_2_dir.mkdir()
    (section_2_dir / "final_section.mp4").touch()

    progress = tracker.check_existing_progress()

    assert progress.has_script
    assert progress.total_sections == 3
    assert progress.completed_sections == {0, 2}
    assert progress.is_resumable()


def test_job_progress_is_resumable():
    """Test JobProgress.is_resumable() logic"""
    # Not resumable - no script
    progress1 = JobProgress(
        job_id="test",
        has_script=False,
        script=None,
        completed_sections=set(),
        has_final_video=False,
        total_sections=0,
        sections_dir=Path("/tmp"),
        job_dir=Path("/tmp")
    )
    assert not progress1.is_resumable()

    # Not resumable - no completed sections
    progress2 = JobProgress(
        job_id="test",
        has_script=True,
        script={},
        completed_sections=set(),
        has_final_video=False,
        total_sections=3,
        sections_dir=Path("/tmp"),
        job_dir=Path("/tmp")
    )
    assert not progress2.is_resumable()

    # Not resumable - already has final video
    progress3 = JobProgress(
        job_id="test",
        has_script=True,
        script={},
        completed_sections={0, 1},
        has_final_video=True,
        total_sections=3,
        sections_dir=Path("/tmp"),
        job_dir=Path("/tmp")
    )
    assert not progress3.is_resumable()

    # Resumable - has script and completed sections, no final video
    progress4 = JobProgress(
        job_id="test",
        has_script=True,
        script={},
        completed_sections={0, 1},
        has_final_video=False,
        total_sections=3,
        sections_dir=Path("/tmp"),
        job_dir=Path("/tmp")
    )
    assert progress4.is_resumable()


def test_job_progress_get_remaining_sections():
    """Test getting remaining sections"""
    progress = JobProgress(
        job_id="test",
        has_script=True,
        script={},
        completed_sections={0, 2, 4},
        has_final_video=False,
        total_sections=6,
        sections_dir=Path("/tmp"),
        job_dir=Path("/tmp")
    )

    remaining = progress.get_remaining_sections()
    assert remaining == [1, 3, 5]


def test_job_progress_completion_percentage():
    """Test completion percentage calculation"""
    progress = JobProgress(
        job_id="test",
        has_script=True,
        script={},
        completed_sections={0, 1, 2},
        has_final_video=False,
        total_sections=10,
        sections_dir=Path("/tmp"),
        job_dir=Path("/tmp")
    )

    assert progress.completion_percentage() == 30.0

    # Test zero sections
    progress_zero = JobProgress(
        job_id="test",
        has_script=False,
        script=None,
        completed_sections=set(),
        has_final_video=False,
        total_sections=0,
        sections_dir=Path("/tmp"),
        job_dir=Path("/tmp")
    )
    assert progress_zero.completion_percentage() == 0.0


def test_mark_section_complete(tracker):
    """Test marking sections as complete"""
    assert len(tracker.completed_sections) == 0

    tracker.mark_section_complete(0)
    assert 0 in tracker.completed_sections

    tracker.mark_section_complete(2)
    tracker.mark_section_complete(5)
    assert tracker.completed_sections == {0, 2, 5}


def test_is_section_complete(tracker):
    """Test checking if section is complete"""
    tracker.mark_section_complete(0)
    tracker.mark_section_complete(2)

    assert tracker.is_section_complete(0)
    assert not tracker.is_section_complete(1)
    assert tracker.is_section_complete(2)


def test_report_stage_progress(tracker):
    """Test progress reporting"""
    callback_data = []

    def callback(data):
        callback_data.append(data)

    tracker_with_callback = ProgressTracker(
        job_id="test",
        output_base_dir=tracker.output_base_dir,
        progress_callback=callback
    )

    tracker_with_callback.report_stage_progress(
        stage="analysis",
        progress=50,
        message="Analyzing..."
    )

    assert len(callback_data) == 1
    assert callback_data[0]["stage"] == "analysis"
    assert callback_data[0]["progress"] == 50
    assert callback_data[0]["message"] == "Analyzing..."


def test_report_section_progress(tracker):
    """Test section progress reporting"""
    callback_data = []

    def callback(data):
        callback_data.append(data)

    tracker.progress_callback = callback
    tracker.report_section_progress(
        completed_count=3,
        total_count=10,
        is_cached=False
    )

    assert len(callback_data) == 1
    assert callback_data[0]["stage"] == "sections"
    assert callback_data[0]["progress"] == 30
    assert "3/10" in callback_data[0]["message"]


def test_save_and_load_script(tracker):
    """Test script persistence"""
    tracker.job_dir.mkdir(parents=True)

    script = {
        "title": "Test Video",
        "sections": [
            {"title": "Section 1", "narration": "Hello"},
            {"title": "Section 2", "narration": "World"}
        ]
    }

    # Save script
    tracker.save_script(script)

    # Verify file exists
    script_path = tracker.job_dir / "script.json"
    assert script_path.exists()

    # Load script
    loaded_script = tracker.load_script()
    assert loaded_script == script


def test_load_script_not_found(tracker):
    """Test loading non-existent script"""
    with pytest.raises(FileNotFoundError):
        tracker.load_script()


def test_get_summary(tracker):
    """Test getting progress summary"""
    tracker.total_sections = 10
    tracker.mark_section_complete(0)
    tracker.mark_section_complete(1)
    tracker.mark_section_complete(2)

    summary = tracker.get_summary()

    assert summary["job_id"] == tracker.job_id
    assert summary["completed_sections"] == 3
    assert summary["total_sections"] == 10
    assert summary["completion_percentage"] == 30.0
    assert not summary["is_complete"]

    # Test complete job
    for i in range(3, 10):
        tracker.mark_section_complete(i)

    summary_complete = tracker.get_summary()
    assert summary_complete["is_complete"]
