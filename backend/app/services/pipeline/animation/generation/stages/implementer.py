"""
Implementer Stage

Responsible for converting choreography plan into Manim code.

Single Responsibility: Generate implementation code from plan
"""

from typing import Dict, Any, Optional

from app.core import get_logger
from app.services.infrastructure.llm import PromptingEngine, PromptConfig

from ...config import BASE_GENERATION_TEMPERATURE, IMPLEMENTATION_MAX_OUTPUT_TOKENS
from ...prompts import IMPLEMENTER_SYSTEM, FULL_IMPLEMENTATION_USER
from ..core import clean_code, ImplementationError
from ..formatters import CodeFormatter


logger = get_logger(__name__, component="animation_implementer")


class Implementer:
    """Generates Manim implementation from choreography plan."""
    
    def __init__(self, engine: PromptingEngine):
        """Initialize implementer with engine.
        
        Args:
            engine: Prompting engine for code generation
        """
        self.engine = engine
        self.formatter = CodeFormatter()
    
    async def implement(
        self,
        section: Dict[str, Any],
        plan: str,
        duration: float,
        context: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None
    ) -> str:
        """Generate Manim code implementation.
        
        Args:
            section: Section dictionary
            plan: Choreography plan text
            duration: Target animation duration
            context: Optional context
            temperature: Optional temperature override for retries
            
        Returns:
            Clean Manim code string
            
        Raises:
            ImplementationError: If code generation fails
        """
        section_data = (
            section.get("section_data")
            or section.get("visual_data")
            or section.get("metadata")
        )
        pattern_focus = (
            "- For any tabular/grid numeric data, use MathTable or MobjectTable (not MathTex array environments).\n"
            "- Reference highlights by table structure (get_rows/get_columns/get_cell), never by manual width-divisors and hardcoded shifts.\n"
            "- Build table headers as separate labels in a VGroup and arrange them across columns.\n"
            "- Do not compress 5+ column labels into one dense MathTex expression.\n"
            "- Do not add decorative Line separators on top of MathTable/Table grids.\n"
            "- Keep row labels anchored with next_to(table, LEFT, buff=0.3).\n"
            "- Scale large table/group structures with scale_to_fit_width(11) before positioning.\n"
            "- Use stroke-only SurroundingRectangle for highlights over numbers/text."
        )
        prompt = FULL_IMPLEMENTATION_USER.format(
            plan=plan,
            segment_timings=self.formatter.summarize_segments(section),
            total_duration=duration,
            section_id_title=self.formatter.derive_class_name(section),
            section_data=self.formatter.serialize_for_prompt(section_data),
            theme_info=section.get("theme_info", "3b1b dark educational style"),
            patterns=pattern_focus,
        )
        
        config = PromptConfig(
            enable_thinking=True,
            timeout=300.0,
            temperature=temperature or BASE_GENERATION_TEMPERATURE,
            max_output_tokens=IMPLEMENTATION_MAX_OUTPUT_TOKENS
        )
        
        result = await self.engine.generate(
            prompt=prompt,
            system_prompt=IMPLEMENTER_SYSTEM.template,
            config=config,
            context=dict(context or {}, stage="implementation")
        )
        
        if not result.get("success") or not result.get("response"):
            error_msg = result.get("error", "Unknown error")
            logger.error(f"Implementation failed: {error_msg}")
            raise ImplementationError(f"Code generation failed: {error_msg}")
        
        code = clean_code(result["response"])
        logger.info(f"Generated implementation ({len(code)} chars)")
        
        return code
