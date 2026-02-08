"""
Integration tests for the Animation Pipeline.
Tests the full flow: Planning -> Code Generation -> Surgical Fixes.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from app.services.pipeline.animation.config import MAX_CLEAN_RETRIES
from app.services.pipeline.animation.generation.orchestrator import AnimationOrchestrator

@pytest.fixture
def mock_engine():
    engine = MagicMock()
    engine.cost_tracker = MagicMock()
    return engine

@pytest.fixture
def orchestrator(mock_engine):
    orch = AnimationOrchestrator(mock_engine)
    orch.choreographer = MagicMock()
    orch.implementer = MagicMock()
    orch.refiner = MagicMock()
    orch.choreographer.plan = AsyncMock()
    orch.implementer.implement = AsyncMock()
    orch.refiner.refine = AsyncMock()
    return orch

@pytest.mark.asyncio
async def test_orchestrator_full_flow(orchestrator):
    """Simulates a full integration flow: plan -> implement -> refine."""
    section = {
        "title": "Integration Test Topic",
        "narration": "This is a full flow test of the new animation pipeline.",
        "narration_segments": [
            {"start_time": 0, "duration": 3, "text": "This is a full flow test"},
            {"start_time": 3, "duration": 3, "text": "of the new animation pipeline."}
        ]
    }
    
    plan_response = "CHOREOGRAPHY PLAN: show text 'Integration Test'"
    broken_code = """
class Scene(Scene):
    def construct(self):
        text = Text("Broken"
        self.play(Write(text))
"""
    fixed_code = """
class Scene(Scene):
    def construct(self):
        text = Text("Fixed")
        self.play(Write(text))
"""
    orchestrator.choreographer.plan.return_value = plan_response
    orchestrator.implementer.implement.return_value = broken_code
    orchestrator.refiner.refine.return_value = (fixed_code, True)

    final_code = await orchestrator.generate(section, 6.0)

    assert orchestrator.choreographer.plan.call_count == 1
    assert orchestrator.implementer.implement.call_count == 1
    assert orchestrator.refiner.refine.call_count == 1
    assert "Fixed" in final_code
    assert "Broken" not in final_code
    assert "def construct(self):" in final_code

@pytest.mark.asyncio
async def test_orchestrator_failure_max_attempts(orchestrator):
    """Verifies that the orchestrator returns empty code if refinement never stabilizes."""
    section = {"title": "Stub", "narration": "Stub", "narration_segments": []}

    orchestrator.choreographer.plan.return_value = "PLAN"
    orchestrator.implementer.implement.return_value = "pass"
    orchestrator.refiner.refine.return_value = ("pass", False)

    code = await orchestrator.generate(section, 5.0)

    assert code == ""
    assert orchestrator.refiner.refine.call_count == MAX_CLEAN_RETRIES
