"""
Tests for models/status module

Tests for JobStatus enum and related status utilities.
"""

import pytest
from app.models.status import (
    JobStatus,
    STATUS_TO_STAGE_MAP,
    get_stage_from_status,
)


class TestJobStatus:
    """Test suite for JobStatus enum"""

    def test_job_status_pending(self):
        """Test PENDING status value"""
        assert JobStatus.PENDING.value == "pending"

    def test_job_status_analyzing(self):
        """Test ANALYZING status value"""
        assert JobStatus.ANALYZING.value == "analyzing"

    def test_job_status_generating_script(self):
        """Test GENERATING_SCRIPT status value"""
        assert JobStatus.GENERATING_SCRIPT.value == "generating_script"

    def test_job_status_creating_animations(self):
        """Test CREATING_ANIMATIONS status value"""
        assert JobStatus.CREATING_ANIMATIONS.value == "creating_animations"

    def test_job_status_synthesizing_audio(self):
        """Test SYNTHESIZING_AUDIO status value"""
        assert JobStatus.SYNTHESIZING_AUDIO.value == "synthesizing_audio"

    def test_job_status_composing_video(self):
        """Test COMPOSING_VIDEO status value"""
        assert JobStatus.COMPOSING_VIDEO.value == "composing_video"

    def test_job_status_completed(self):
        """Test COMPLETED status value"""
        assert JobStatus.COMPLETED.value == "completed"

    def test_job_status_failed(self):
        """Test FAILED status value"""
        assert JobStatus.FAILED.value == "failed"

    def test_job_status_interrupted(self):
        """Test INTERRUPTED status value"""
        assert JobStatus.INTERRUPTED.value == "interrupted"


class TestJobStatusIsTerminal:
    """Test suite for JobStatus.is_terminal() method"""

    def test_completed_is_terminal(self):
        """Test COMPLETED is terminal"""
        assert JobStatus.COMPLETED.is_terminal() is True

    def test_failed_is_terminal(self):
        """Test FAILED is terminal"""
        assert JobStatus.FAILED.is_terminal() is True

    def test_pending_is_not_terminal(self):
        """Test PENDING is not terminal"""
        assert JobStatus.PENDING.is_terminal() is False

    def test_analyzing_is_not_terminal(self):
        """Test ANALYZING is not terminal"""
        assert JobStatus.ANALYZING.is_terminal() is False

    def test_creating_animations_is_not_terminal(self):
        """Test CREATING_ANIMATIONS is not terminal"""
        assert JobStatus.CREATING_ANIMATIONS.is_terminal() is False

    def test_interrupted_is_not_terminal(self):
        """Test INTERRUPTED is not terminal (can potentially resume)"""
        # INTERRUPTED is not in the terminal states per code
        assert JobStatus.INTERRUPTED.is_terminal() is False


class TestJobStatusIsInProgress:
    """Test suite for JobStatus.is_in_progress() method"""

    def test_analyzing_is_in_progress(self):
        """Test ANALYZING is in progress"""
        assert JobStatus.ANALYZING.is_in_progress() is True

    def test_generating_script_is_in_progress(self):
        """Test GENERATING_SCRIPT is in progress"""
        assert JobStatus.GENERATING_SCRIPT.is_in_progress() is True

    def test_creating_animations_is_in_progress(self):
        """Test CREATING_ANIMATIONS is in progress"""
        assert JobStatus.CREATING_ANIMATIONS.is_in_progress() is True

    def test_synthesizing_audio_is_in_progress(self):
        """Test SYNTHESIZING_AUDIO is in progress"""
        assert JobStatus.SYNTHESIZING_AUDIO.is_in_progress() is True

    def test_composing_video_is_in_progress(self):
        """Test COMPOSING_VIDEO is in progress"""
        assert JobStatus.COMPOSING_VIDEO.is_in_progress() is True

    def test_pending_is_not_in_progress(self):
        """Test PENDING is not in progress"""
        assert JobStatus.PENDING.is_in_progress() is False

    def test_completed_is_not_in_progress(self):
        """Test COMPLETED is not in progress"""
        assert JobStatus.COMPLETED.is_in_progress() is False

    def test_failed_is_not_in_progress(self):
        """Test FAILED is not in progress"""
        assert JobStatus.FAILED.is_in_progress() is False


class TestStatusToStageMap:
    """Test suite for STATUS_TO_STAGE_MAP"""

    def test_map_is_dict(self):
        """Test STATUS_TO_STAGE_MAP is a dictionary"""
        assert isinstance(STATUS_TO_STAGE_MAP, dict)

    def test_map_has_expected_keys(self):
        """Test map has expected status keys"""
        expected_keys = [
            "pending",
            "analyzing",
            "generating_script",
            "creating_animations",
            "synthesizing_audio",
            "composing_video",
            "completed",
            "failed",
        ]
        
        for key in expected_keys:
            assert key in STATUS_TO_STAGE_MAP, f"Missing key: {key}"

    def test_map_values_are_strings(self):
        """Test all map values are strings"""
        for status, stage in STATUS_TO_STAGE_MAP.items():
            assert isinstance(stage, str), f"Stage for {status} should be string"

    def test_analyzing_maps_to_analyzing(self):
        """Test analyzing status maps to analyzing stage"""
        assert STATUS_TO_STAGE_MAP["analyzing"] == "analyzing"

    def test_script_maps_to_script(self):
        """Test generating_script maps to script stage"""
        assert STATUS_TO_STAGE_MAP["generating_script"] == "script"

    def test_animations_maps_to_sections(self):
        """Test creating_animations maps to sections stage"""
        assert STATUS_TO_STAGE_MAP["creating_animations"] == "sections"

    def test_completed_maps_to_completed(self):
        """Test completed status maps to completed stage"""
        assert STATUS_TO_STAGE_MAP["completed"] == "completed"


class TestGetStageFromStatus:
    """Test suite for get_stage_from_status function"""

    def test_known_status(self):
        """Test getting stage for known status"""
        assert get_stage_from_status("pending") == "analyzing"
        assert get_stage_from_status("analyzing") == "analyzing"
        assert get_stage_from_status("generating_script") == "script"
        assert get_stage_from_status("creating_animations") == "sections"
        assert get_stage_from_status("completed") == "completed"
        assert get_stage_from_status("failed") == "failed"

    def test_unknown_status_returns_unknown(self):
        """Test unknown status returns 'unknown'"""
        result = get_stage_from_status("nonexistent_status")
        assert result == "unknown"

    def test_empty_string_returns_unknown(self):
        """Test empty string returns 'unknown'"""
        result = get_stage_from_status("")
        assert result == "unknown"

    def test_case_sensitivity(self):
        """Test status matching is case-sensitive"""
        # Uppercase should not match
        result = get_stage_from_status("PENDING")
        assert result == "unknown"

        result = get_stage_from_status("Analyzing")
        assert result == "unknown"


class TestJobStatusFromString:
    """Test suite for creating JobStatus from string"""

    def test_create_from_valid_string(self):
        """Test creating JobStatus from valid string"""
        status = JobStatus("pending")
        assert status == JobStatus.PENDING

        status = JobStatus("completed")
        assert status == JobStatus.COMPLETED

    def test_create_from_invalid_string(self):
        """Test creating JobStatus from invalid string raises ValueError"""
        with pytest.raises(ValueError):
            JobStatus("invalid_status")

    def test_all_status_values_are_valid(self):
        """Test all JobStatus values can be round-tripped"""
        for status in JobStatus:
            recreated = JobStatus(status.value)
            assert recreated == status
