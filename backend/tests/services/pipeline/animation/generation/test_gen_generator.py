
import pytest
from pathlib import Path
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
    mock_orchestrator.generate = AsyncMock(return_value="manim_code")
    
    mock_deps["create_scene_file"].return_value = (
        "from manim import *\n"
        "class SectionSec1(Scene):\n"
        "    def construct(self):\n"
        "        pass\n"
    )
    generator.file_manager.prepare_scene_file.return_value = "code_path"
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
    assert "class SectionSec1(Scene)" in result["manim_code"]
    mock_orchestrator.generate.assert_called_once()
    mock_deps["render_scene"].assert_called_once()


@pytest.mark.asyncio
async def test_generate_animation_persists_choreography(generator, mock_deps):
    mock_orchestrator = generator.orchestrator

    async def _generate_with_plan(*args, **kwargs):
        callback = kwargs.get("on_choreography")
        if callback:
            callback({"version": "2.0"}, 0)
        return "manim_code"

    mock_orchestrator.generate = AsyncMock(side_effect=_generate_with_plan)
    generator.file_manager.save_choreography_plan.return_value = Path("/tmp/out/choreography_plan.json")
    mock_deps["create_scene_file"].return_value = (
        "from manim import *\n"
        "class SectionSec1(Scene):\n"
        "    def construct(self):\n"
        "        pass\n"
    )
    generator.file_manager.prepare_scene_file.return_value = "code_path"
    mock_deps["render_scene"].side_effect = AsyncMock(return_value="video.mp4")
    generator.vision_validator.verify_issues = AsyncMock(return_value=[])

    section = {"id": "sec1", "title": "Section 1"}
    result = await generator.generate_animation(
        section=section,
        output_dir="/tmp/out",
        section_index=1,
        audio_duration=10.0
    )

    generator.file_manager.save_choreography_plan.assert_called_once_with(
        output_dir="/tmp/out",
        plan={"version": "2.0"},
    )
    assert result["choreography_plan_path"] == "/tmp/out/choreography_plan.json"

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
async def test_process_code_and_render_rendering_failure(generator, mock_deps):
    mock_deps["create_scene_file"].return_value = (
        "from manim import *\n"
        "class SectionSec1(Scene):\n"
        "    def construct(self):\n"
        "        pass\n"
    )
    mock_deps["render_scene"].side_effect = AsyncMock(return_value=None) # Failed to render
    
    with pytest.raises(RenderingError):
        await generator.process_code_and_render(
            manim_code="code",
            section={"id": "sec1"},
            output_dir="/tmp",
            section_index=1
        )


@pytest.mark.asyncio
async def test_process_code_and_render_fails_on_multiple_scene_classes(generator, mock_deps):
    mock_deps["create_scene_file"].return_value = (
        "from manim import *\n"
        "class SceneA(Scene):\n"
        "    def construct(self):\n"
        "        pass\n"
        "class SceneB(Scene):\n"
        "    def construct(self):\n"
        "        pass\n"
    )

    with pytest.raises(RenderingError):
        await generator.process_code_and_render(
            manim_code="code",
            section={"id": "sec1"},
            output_dir="/tmp",
            section_index=1,
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
    msgs = await generator._run_vision_verification("vid.mp4", "/tmp", 1)
    
    # Assert
    assert len(msgs) == 1
    assert msgs[0] == "Overlap"
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
    await generator._run_vision_verification("vid.mp4", "/tmp", 1)
    
    # Assert
    mock_orchestrator.refiner.mark_as_real_issues.assert_not_called()
    mock_orchestrator.refiner.mark_as_false_positives.assert_called_once()
