"""
LIVE Integration tests for the Animation Pipeline.
Uses the REAL Gemini API - costs tokens/money.

Run with:
    pytest tests/integration/pipeline/test_animation_flow_live.py -v -s

Requires GEMINI_API_KEY environment variable.
"""

import pytest
import os

# Load .env file if it exists
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env'), override=True)

# Skip entire module if no API key
pytestmark = pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY not set - skipping live LLM tests"
)


@pytest.fixture
def real_animator():
    """Create a real Animator with live LLM and validator."""
    from app.services.infrastructure.llm import PromptingEngine, CostTracker
    from app.services.pipeline.animation.generation.processors import Animator
    from app.services.pipeline.animation.generation.validation import CodeValidator
    
    cost_tracker = CostTracker()
    engine = PromptingEngine("animation_implementation", cost_tracker)
    validator = CodeValidator()
    
    animator = Animator(engine, validator, max_fix_attempts=2)
    yield animator
    
    # Print cost summary after test
    print("\n--- LLM Cost Summary ---")
    cost_tracker.print_summary()


@pytest.mark.asyncio
async def test_live_animation_generation(real_animator):
    """
    LIVE TEST: Generates a simple animation using the real Gemini API.
    
    This tests the full pipeline:
    1. Choreography planning
    2. Full code generation
    3. Validation (and potential surgical fixes)
    """
    section = {
        "title": "Simple Circle Animation",
        "narration": "Let's draw a simple circle and make it pulse.",
        "narration_segments": [
            {"start_time": 0, "duration": 2.5, "text": "Let's draw a simple circle"},
            {"start_time": 2.5, "duration": 2.5, "text": "and make it pulse."}
        ]
    }
    
    # Run the full pipeline
    code = await real_animator.animate(section, duration=5.0)
    
    # --- Assertions ---
    
    # 1. Code should not be empty
    assert code is not None
    assert len(code) > 50, "Generated code is too short"
    
    # 2. Code should have core Manim structure elements
    # We only check for body content, not full scene wrapper (that's added by generator.py)
    assert "self.play" in code or "self.wait" in code, "Code should contain animation commands"
    
    # 3. Print code for manual inspection
    print("\n--- Generated Manim Code ---")
    print(code)
    print("--- End of Code ---\n")
