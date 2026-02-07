"""
Tests for app.services.pipeline.assembly.video_generator
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.services.pipeline.assembly.video_generator import VideoGenerator


@pytest.mark.asyncio
class TestVideoGenerator:
    """Test the main pipeline orchestrator."""

    @pytest.fixture
    def generator(self, tmp_path):
        # Patch all sub-services
        with patch("app.services.pipeline.assembly.video_generator.MaterialAnalyzer"), \
             patch("app.services.pipeline.assembly.video_generator.ScriptGenerator"), \
             patch("app.services.pipeline.assembly.video_generator.ManimGenerator"), \
             patch("app.services.pipeline.assembly.video_generator.TTSEngine"), \
             patch("app.services.pipeline.assembly.video_generator.VideoProcessor"), \
             patch("app.services.pipeline.assembly.video_generator.ProgressTracker"), \
             patch("app.services.pipeline.assembly.video_generator.SectionOrchestrator"):
            
            gen = VideoGenerator(output_base_dir=str(tmp_path))
            
            # Setup common mocks
            gen.script_generator.generate_script = AsyncMock(return_value={
                "script": {
                    "sections": [{"title": "S1", "narration": "Hello"}]
                }
            })
            
            return gen

    async def test_generate_video_success(self, generator, tmp_path):
        """Test full pipeline orchestration success."""
        job_id = "job-123"
        
        # Patch internal helper for parallel processing
        # Actually it uses SectionOrchestrator
        with patch.object(generator, "_generate_script", AsyncMock(return_value={"sections": [{"title": "S1"}]})), \
             patch("app.services.pipeline.assembly.video_generator.SectionOrchestrator") as mock_orch_class:
            
            mock_orch = mock_orch_class.return_value
            mock_orch.process_sections_parallel = AsyncMock(return_value=[{}])
            mock_orch.aggregate_results = MagicMock(return_value=(["v1.mp4"], ["a1.mp3"], [{"duration": 5.0}]))
            
            # Mock processor
            generator.video_processor.combine_sections = AsyncMock()
            
            # Mock cleanup
            generator._cleanup_intermediate_files = AsyncMock()
            
            result = await generator.generate_video(
                job_id=job_id,
                material_path="source.pdf"
            )
            
            assert result["status"] == "completed"
            assert result["job_id"] == job_id
            assert "video_path" in result
            generator.video_processor.combine_sections.assert_called_once()

    async def test_generate_video_resume(self, generator, tmp_path):
        """Test resuming from existing script."""
        job_id = "resume-123"
        
        # Mock tracker to report existing script
        with patch("app.services.pipeline.assembly.video_generator.ProgressTracker") as mock_tracker_class:
            mock_tracker = mock_tracker_class.return_value
            mock_tracker.check_existing_progress.return_value = MagicMock(
                has_final_video=False,
                has_script=True,
                script={"sections": []}
            )
            mock_tracker.load_script.return_value = {"sections": [{"title": "S1"}]}
            
            # Mock orchestrator and other bits to avoid failures
            with patch("app.services.pipeline.assembly.video_generator.SectionOrchestrator") as mock_orch_class:
                mock_orch = mock_orch_class.return_value
                mock_orch.process_sections_parallel = AsyncMock(return_value=[])
                mock_orch.aggregate_results = MagicMock(return_value=([], [], []))
                
                # Should fail at combine if no videos, but we check if _generate_script was NOT called
                generator._generate_script = AsyncMock()
                
                await generator.generate_video(job_id=job_id, resume=True)
                
                generator._generate_script.assert_not_called()
                mock_tracker.load_script.assert_called_once()

    async def test_cleanup_keeps_only_final_and_translations(self, generator, tmp_path):
        """Completed jobs should keep only final video artifacts."""
        job_dir = tmp_path / "job-keep-final"
        sections_dir = job_dir / "sections"
        sections_dir.mkdir(parents=True)

        (job_dir / "final_video.mp4").write_text("video")
        (job_dir / "script.json").write_text("{}")
        (job_dir / "concat_list.txt").write_text("tmp")
        (sections_dir / "0").mkdir(parents=True)
        (sections_dir / "0" / "scene.py").write_text("code")
        (job_dir / "translations").mkdir()

        await generator._cleanup_intermediate_files(sections_dir)

        assert (job_dir / "final_video.mp4").exists()
        assert (job_dir / "translations").exists()
        assert not (job_dir / "sections").exists()
        assert not (job_dir / "script.json").exists()
        assert not (job_dir / "concat_list.txt").exists()

    async def test_generate_script_forwards_focus_and_context(self, generator):
        """Script generation should receive content focus and document context."""
        tracker = MagicMock()
        tracker.report_stage_progress = MagicMock()

        generator.script_generator.generate_script = AsyncMock(return_value={"script": {"sections": []}})

        await generator._generate_script(
            job_id="job-ctx",
            material_path="source.pdf",
            topic={"title": "Picked Topic"},
            language="en",
            video_mode="comprehensive",
            content_focus="theory",
            document_context="series",
            tracker=tracker,
            artifacts_dir="artifacts",
        )

        kwargs = generator.script_generator.generate_script.await_args.kwargs
        assert kwargs["content_focus"] == "theory"
        assert kwargs["document_context"] == "series"
