"""
Tests for app.services.use_cases.generation_use_case
"""

import pytest
import uuid
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import HTTPException, BackgroundTasks
from app.services.use_cases.generation_use_case import GenerationUseCase
from app.models import GenerationRequest
from app.services.infrastructure.orchestration import JobStatus


class TestGenerationUseCase:
    """Test GenerationUseCase orchestration."""

    @pytest.fixture
    def use_case(self):
        with patch("app.services.use_cases.generation_use_case.get_job_manager") as mock_get_mgr:
            self.job_manager = MagicMock()
            mock_get_mgr.return_value = self.job_manager
            return GenerationUseCase()

    def test_validate_pipeline_success(self, use_case):
        with patch("app.services.use_cases.generation_use_case.AVAILABLE_PIPELINES", ["p1", "default"]):
            assert use_case._validate_pipeline("p1") == "p1"
            assert use_case._validate_pipeline(None) == "default"

    def test_validate_pipeline_failure(self, use_case):
        with patch("app.services.use_cases.generation_use_case.AVAILABLE_PIPELINES", ["default"]):
            with pytest.raises(HTTPException) as exc:
                use_case._validate_pipeline("unknown")
            assert exc.value.status_code == 400

    def test_select_job_new(self, use_case):
        job_id, resume = use_case._select_job(None)
        assert len(job_id) > 0
        assert resume is False
        self.job_manager.create_job.assert_called_once()

    def test_select_job_resume(self, use_case):
        existing_id = "job-123"
        self.job_manager.get_job.return_value = MagicMock(id=existing_id)
        
        job_id, resume = use_case._select_job(existing_id)
        assert job_id == existing_id
        assert resume is True
        self.job_manager.update_job.assert_called_with(existing_id, JobStatus.ANALYZING, 0, "Resuming generation...")

    def test_start_generation(self, use_case):
        request = GenerationRequest(
            file_id="file-1", 
            pipeline="default", 
            analysis_id="anal-1", 
            selected_topics=[]
        )
        background_tasks = MagicMock(spec=BackgroundTasks)
        
        with patch("app.services.use_cases.generation_use_case.AVAILABLE_PIPELINES", ["default"]), \
             patch("app.services.use_cases.generation_use_case.find_uploaded_file", return_value="/path/file.pdf"), \
             patch("app.services.use_cases.generation_use_case.VideoGenerator") as mock_vg_class:
            
            response = use_case.start_generation(request, background_tasks)
            
            assert response.job_id is not None
            assert response.status == "pending"
            background_tasks.add_task.assert_called_once()
            # Verify VideoGenerator was instantiated
            mock_vg_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_generation_success(self, use_case):
        """Test the inner run_generation logic."""
        # This is tricky because run_generation is an inner async function.
        # We can test it by extracting it or by triggering start_generation and capturing the task.
        # For now, let's test specific logic like the progress callback.
        
        callback_factory = use_case._get_progress_callback("job-abc")
        callback = callback_factory
        
        # Test stage "script" (0-10%)
        callback({"stage": "script", "progress": 50, "message": "Thinking"})
        self.job_manager.update_job.assert_called_with(
            "job-abc", JobStatus.GENERATING_SCRIPT, 5.0, "Thinking"
        )
        
        # Test stage "sections" (10-90%)
        callback({"stage": "sections", "progress": 50, "message": "Rendering"})
        self.job_manager.update_job.assert_called_with(
            "job-abc", JobStatus.CREATING_ANIMATIONS, 50.0, "Rendering" # 10 + 0.8*50 = 50
        )

    def test_get_resume_info_not_found(self, use_case):
        self.job_manager.get_job.return_value = None
        with pytest.raises(HTTPException) as exc:
            use_case.get_resume_info("none")
        assert exc.value.status_code == 404

    def test_get_resume_info_data(self, use_case):
        job = MagicMock(status=JobStatus.FAILED)
        self.job_manager.get_job.return_value = job
        
        with patch("app.services.use_cases.generation_use_case.VideoGenerator") as mock_vg_class:
            mock_vg = mock_vg_class.return_value
            mock_vg.check_existing_progress.return_value = {
                "has_script": True,
                "has_final_video": False,
                "completed_sections": [1, 2],
                "total_sections": 5
            }
            
            info = use_case.get_resume_info("job-1")
            assert info.can_resume is True
            assert info.completed_sections == 2
            assert info.total_sections == 5
