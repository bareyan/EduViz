
import pytest
from unittest.mock import AsyncMock, Mock, patch

from app.services.pipeline.animation.generation.generator import ManimGenerator
from app.services.pipeline.animation.generation.core import (
    ImplementationError,
    RefinementError,
    RenderingError
)

@pytest.fixture
def mock_deps():
    with patch("app.services.pipeline.animation.generation.generator.AnimationOrchestrator") as MockOrch, \
         patch("app.services.pipeline.animation.generation.generator.AnimationFileManager") as MockFM, \
         patch("app.services.pipeline.animation.generation.generator.PromptingEngine") as MockPE, \
         patch("app.services.pipeline.animation.generation.generator.VisionValidator") as MockVV, \
         patch("app.services.pipeline.animation.generation.generator.CostTracker") as MockCT, \
         patch("app.services.pipeline.animation.generation.generator.create_scene_file") as MockCreateScene, \
         patch("app.services.pipeline.animation.generation.generator.render_scene") as MockRenderScene, \
         patch("app.services.pipeline.animation.generation.generator.write_status") as MockWriteStatus:
        
        yield {
            "orchestrator_cls": MockOrch,
            "file_manager_cls": MockFM,
            "prompt_engine_cls": MockPE,
            "vision_validator_cls": MockVV,
            "cost_tracker_cls": MockCT,
            "create_scene_file": MockCreateScene,
            "render_scene": MockRenderScene,
            "write_status": MockWriteStatus
        }

@pytest.fixture
def generator(mock_deps):
    return ManimGenerator(pipeline_name="test_pipeline")

@pytest.mark.asyncio
async def test_generate_animation_success(generator, mock_deps):
    # Setup
    mock_orchestrator = generator.orchestrator
    async def _mock_generate(*args, **kwargs):
        on_plan = kwargs.get("on_choreography_plan")
        if on_plan:
            on_plan('{"steps": []}', 0)
        return "manim_code"
    mock_orchestrator.generate = AsyncMock(side_effect=_mock_generate)
    
    mock_deps["create_scene_file"].return_value = "full_code"
    generator.file_manager.prepare_scene_file.return_value = "code_path"
    generator.file_manager.prepare_choreography_plan_file.return_value = "/tmp/out/choreography_plan.json"
    mock_deps["render_scene"].side_effect = AsyncMock(return_value="video.mp4")
    generator.vision_validator.verify_issues = AsyncMock(return_value=[])
    
    # Execute
    section = {"id": "sec1", "title": "Section 1"}
    result = await generator.generate_animation(
        section=section,
        output_dir="/tmp/out",
        section_index=1,
        audio_duration=10.0
    )
    
    # Assert
    assert result["video_path"] == "video.mp4"
    assert result["manim_code"] == "full_code"
    assert result["choreography_plan_path"] == "/tmp/out/choreography_plan.json"
    mock_orchestrator.generate.assert_called_once()
    mock_deps["render_scene"].assert_called_once()
    generator.file_manager.prepare_choreography_plan_file.assert_called_once()

@pytest.mark.asyncio
async def test_generate_animation_orchestrator_failure(generator, mock_deps):
    mock_orchestrator = generator.orchestrator
    mock_orchestrator.generate = AsyncMock(return_value="") # Failed to generate
    
    section = {"id": "sec1"}
    with pytest.raises(ImplementationError):
        await generator.generate_animation(
            section=section,
            output_dir="/tmp/out",
            section_index=1,
            audio_duration=10.0
        )


@pytest.mark.asyncio
async def test_generate_animation_passes_explicit_theme_info(generator, mock_deps):
    mock_orchestrator = generator.orchestrator
    mock_orchestrator.generate = AsyncMock(return_value="manim_code")
    mock_deps["create_scene_file"].return_value = "full_code"
    generator.file_manager.prepare_scene_file.return_value = "code_path"
    mock_deps["render_scene"].side_effect = AsyncMock(return_value="video.mp4")
    generator.vision_validator.verify_issues = AsyncMock(return_value=[])

    section = {"id": "sec1", "title": "Section 1"}
    await generator.generate_animation(
        section=section,
        output_dir="/tmp/out",
        section_index=1,
        audio_duration=10.0,
        style="clean",
    )

    called_section = mock_orchestrator.generate.call_args[0][0]
    assert called_section["style"] == "clean"
    assert "background=#FFFFFF" in called_section["theme_info"]

@pytest.mark.asyncio
async def test_process_code_and_render_rendering_failure(generator, mock_deps):
    mock_deps["create_scene_file"].return_value = "full_code"
    mock_deps["render_scene"].side_effect = AsyncMock(return_value=None) # Failed to render
    
    with pytest.raises(RenderingError):
        await generator.process_code_and_render(
            manim_code="code",
            section={"id": "sec1"},
            output_dir="/tmp",
            section_index=1
        )

@pytest.mark.asyncio
async def test_run_vision_verification(generator, mock_deps):
    # Setup Vision QC
    mock_orchestrator = generator.orchestrator
    # Mock refiner inside orchestrator
    mock_orchestrator.refiner = Mock()
    
    issue = Mock()
    issue.whitelist_key = "key1"
    issue.message = "Overlap"
    issue.category = Mock()
    issue.category.value = "text_overlap"
    issue.severity = Mock()
    issue.severity.value = "warning"
    issue.confidence = Mock()
    issue.confidence.value = "low"
    
    mock_orchestrator.refiner.get_pending_uncertain_issues.return_value = [issue]
    
    generator.vision_validator.verify_issues = AsyncMock(return_value=[issue])
    
    # Execute
    msgs, confirmed = await generator._run_vision_verification("vid.mp4", "/tmp", 1)
    
    # Assert
    assert len(msgs) == 1
    assert msgs[0] == "Overlap"
    assert confirmed == [issue]
    mock_orchestrator.refiner.mark_as_real_issues.assert_called_once()
    mock_orchestrator.refiner.mark_as_false_positives.assert_not_called()

@pytest.mark.asyncio
async def test_run_vision_verification_false_positives(generator, mock_deps):
    # Setup Vision QC - returns empty confirmed list
    mock_orchestrator = generator.orchestrator
    mock_orchestrator.refiner = Mock()
    
    issue = Mock()
    issue.whitelist_key = "key1"
    issue.message = "False alarm"
    issue.category = Mock()
    issue.category.value = "text_overlap"
    issue.severity = Mock()
    issue.severity.value = "warning"
    issue.confidence = Mock()
    issue.confidence.value = "low"
    
    mock_orchestrator.refiner.get_pending_uncertain_issues.return_value = [issue]
    
    generator.vision_validator.verify_issues = AsyncMock(return_value=[]) # None confirmed
    
    # Execute
    msgs, confirmed = await generator._run_vision_verification("vid.mp4", "/tmp", 1)
    
    # Assert
    assert msgs == []
    assert confirmed == []
    mock_orchestrator.refiner.mark_as_real_issues.assert_not_called()
    mock_orchestrator.refiner.mark_as_false_positives.assert_called_once()


@pytest.mark.asyncio
async def test_process_code_and_render_rerenders_after_visual_qc_confirmed_issue(generator, mock_deps):
    mock_deps["create_scene_file"].return_value = "full_code"
    mock_deps["render_scene"].side_effect = AsyncMock(side_effect=["video_1.mp4", "video_2.mp4"])
    generator.file_manager.prepare_scene_file.return_value = "code_path"

    issue = Mock()
    generator._run_vision_verification = AsyncMock(side_effect=[(["Overlap"], [issue]), ([], [])])

    mock_refiner = Mock()
    mock_refiner.apply_issues = AsyncMock(return_value=("fixed_full_code", {"deterministic": 1, "llm": 0}))
    generator.orchestrator.refiner = mock_refiner

    result = await generator.process_code_and_render(
        manim_code="code",
        section={"id": "sec1", "title": "Section 1"},
        output_dir="/tmp",
        section_index=1
    )

    assert result["video_path"] == "video_2.mp4"
    assert result["manim_code"] == "fixed_full_code"
    assert mock_deps["render_scene"].call_count == 2
    generator.orchestrator.refiner.apply_issues.assert_called_once()
