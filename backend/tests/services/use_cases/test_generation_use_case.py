"""
Tests for app.services.use_cases.generation_use_case
"""

import pytest
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
        assert use_case._validate_pipeline("p1") == "default"
        assert use_case._validate_pipeline(None) == "default"

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
        
        with patch("app.services.use_cases.generation_use_case.find_uploaded_file", return_value="/path/file.pdf"), \
             patch("app.services.use_cases.generation_use_case.VideoGenerator") as mock_vg_class:
            
            response = use_case.start_generation(request, background_tasks)
            
            assert response.job_id is not None
            assert response.status == "pending"
            background_tasks.add_task.assert_called_once()
            # Verify VideoGenerator was instantiated
            mock_vg_class.assert_called_once()

    def test_start_generation_resume_without_file_when_script_exists(self, use_case):
        existing_id = "job-123"
        self.job_manager.get_job.return_value = MagicMock(id=existing_id)

        request = GenerationRequest(
            file_id="missing-file",
            pipeline="default",
            analysis_id="anal-1",
            selected_topics=[],
            resume_job_id=existing_id,
        )
        background_tasks = MagicMock(spec=BackgroundTasks)

        with patch("app.services.use_cases.generation_use_case.find_uploaded_file", side_effect=HTTPException(status_code=404, detail="missing")), \
             patch("app.services.use_cases.generation_use_case.VideoGenerator") as mock_vg_class:
            mock_vg_class.return_value.check_existing_progress.return_value = {"has_script": True}

            response = use_case.start_generation(request, background_tasks)

            assert response.status == "resuming"
            background_tasks.add_task.assert_called_once()

    def test_start_generation_resume_without_file_and_script_raises(self, use_case):
        existing_id = "job-456"
        self.job_manager.get_job.return_value = MagicMock(id=existing_id)

        request = GenerationRequest(
            file_id="missing-file",
            pipeline="default",
            analysis_id="anal-1",
            selected_topics=[],
            resume_job_id=existing_id,
        )
        background_tasks = MagicMock(spec=BackgroundTasks)

        with patch("app.services.use_cases.generation_use_case.find_uploaded_file", side_effect=HTTPException(status_code=404, detail="missing")), \
             patch("app.services.use_cases.generation_use_case.VideoGenerator") as mock_vg_class:
            mock_vg_class.return_value.check_existing_progress.return_value = {"has_script": False}

            with pytest.raises(HTTPException) as exc:
                use_case.start_generation(request, background_tasks)

            assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_run_generation_execution_success(self, use_case):
        """Test the actual execution of the background task (success case)."""
        request = GenerationRequest(
            file_id="file-1", 
            pipeline="default", 
            analysis_id="anal-1", 
            selected_topics=[]
        )
        background_tasks = BackgroundTasks()
        
        # Setup mocks
        with patch("app.services.use_cases.generation_use_case.find_uploaded_file", return_value="/path/file.pdf"), \
             patch("app.services.use_cases.generation_use_case.VideoGenerator") as mock_vg_class:
            
            mock_vg = mock_vg_class.return_value
            mock_vg.generate_video = AsyncMock(return_value={
                "status": "completed",
                "script": {"title": "Test Video"},
                "total_duration": 120,
                "chapters": [],
                "output_path": "/out/vid.mp4"
            })
            
            # Start generation to queue the task
            response = use_case.start_generation(request, background_tasks)
            job_id = response.job_id
            
            # Extract and run the background task
            task_func = background_tasks.tasks[0].func
            await task_func()
            
            # Verify success update
            self.job_manager.update_job.assert_called_with(
                job_id,
                JobStatus.COMPLETED,
                100,
                "Video generated successfully!",
                result=[{
                    "video_id": job_id,
                    "title": "Test Video",
                    "duration": 120,
                    "chapters": [],
                    "download_url": f"/outputs/{job_id}/final_video.mp4",
                    "thumbnail_url": None,
                }]
            )

    @pytest.mark.asyncio
    async def test_run_generation_passes_focus_and_context(self, use_case):
        request = GenerationRequest(
            file_id="file-1",
            pipeline="default",
            analysis_id="anal-1",
            selected_topics=[],
            content_focus="practice",
            document_context="series",
        )
        background_tasks = BackgroundTasks()

        with patch("app.services.use_cases.generation_use_case.find_uploaded_file", return_value="/path/file.pdf"), \
             patch("app.services.use_cases.generation_use_case.VideoGenerator") as mock_vg_class:
            mock_vg = mock_vg_class.return_value
            mock_vg.generate_video = AsyncMock(return_value={"status": "failed", "error": "x"})

            use_case.start_generation(request, background_tasks)
            task_func = background_tasks.tasks[0].func
            await task_func()

            kwargs = mock_vg.generate_video.await_args.kwargs
            assert kwargs["content_focus"] == "practice"
            assert kwargs["document_context"] == "series"

    @pytest.mark.asyncio
    async def test_run_generation_execution_failure(self, use_case):
        """Test the actual execution of the background task (failure case)."""
        request = GenerationRequest(
            file_id="file-1", 
            pipeline="default",
            analysis_id="dummy-analysis",
            selected_topics=[]
        )
        background_tasks = BackgroundTasks()
        
        with patch("app.services.use_cases.generation_use_case.find_uploaded_file", return_value="/path/file.pdf"), \
             patch("app.services.use_cases.generation_use_case.VideoGenerator") as mock_vg_class:
            
            mock_vg = mock_vg_class.return_value
            # simulate error
            mock_vg.generate_video = AsyncMock(return_value={
                "status": "failed",
                "error": "Pipeline exploded"
            })
            
            use_case.start_generation(request, background_tasks)
            task_func = background_tasks.tasks[0].func
            await task_func()
            
            # Verify failure update
            # Note: assert_called_with might fail if other updates happened before, 
            # so we check the last call or specific call args
            call_args = self.job_manager.update_job.call_args
            assert call_args[0][1] == JobStatus.FAILED
            assert call_args[0][3] == "Pipeline exploded"

    @pytest.mark.asyncio
    async def test_progress_callback_logic(self, use_case):
        """Test the progress calculation logic."""
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
