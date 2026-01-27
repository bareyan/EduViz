"""
Correction Tools - Tool-based code correction

Uses Gemini function calling for structured, reliable fixes.
Replaces the old text-based SEARCH/REPLACE approach with proper tool calls.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from .schemas import SEARCH_REPLACE_SCHEMA, ANALYSIS_SCHEMA
from .context import get_manim_reference


@dataclass
class CorrectionResult:
    """Result from code correction tool"""
    success: bool
    code: Optional[str] = None
    fixes_applied: int = 0
    error: Optional[str] = None
    details: Optional[List[str]] = None


class CorrectionToolHandler:
    """
    Handles code correction using tool calling.
    
    Flow:
    1. Analyze error
    2. Generate fixes using search/replace tool
    3. Apply fixes
    4. Validate result
    """
    
    def __init__(self, engine, validator):
        """
        Args:
            engine: PromptingEngine instance
            validator: CodeValidator instance
        """
        self.engine = engine
        self.validator = validator
    
    def get_tools(self, types_module) -> List[Any]:
        """
        Get Gemini tool declarations for correction.
        
        Args:
            types_module: Gemini types module
            
        Returns:
            List of Tool declarations for Gemini API
        """
        return [
            types_module.Tool(
                function_declarations=[
                    types_module.FunctionDeclaration(
                        name="apply_fixes",
                        description="Apply search/replace fixes to correct code errors",
                        parameters=SEARCH_REPLACE_SCHEMA
                    ),
                    types_module.FunctionDeclaration(
                        name="analyze_error",
                        description="Analyze a code error to determine root cause",
                        parameters=ANALYSIS_SCHEMA
                    ),
                ]
            )
        ]
    
    async def correct(
        self,
        code: str,
        error_message: str,
        section: Optional[Dict[str, Any]] = None,
        attempt: int = 0
    ) -> CorrectionResult:
        """
        Correct code errors using tool-based approach.
        
        Args:
            code: Current code with errors
            error_message: Error message from Manim
            section: Section context (optional)
            attempt: Current attempt number
            
        Returns:
            CorrectionResult with fixed code or error
        """
        from app.services.prompting_engine import PromptConfig
        
        # Build correction prompt
        prompt = self._build_correction_prompt(code, error_message, section)
        system_prompt = self._build_system_prompt()
        
        config = PromptConfig(
            temperature=0.1 + (attempt * 0.1),  # Increase randomness on retries
            max_output_tokens=2048,
            timeout=60,
            response_format="json"
        )
        
        try:
            response = await self.engine.generate(
                prompt=prompt,
                config=config,
                system_prompt=system_prompt,
                response_schema=SEARCH_REPLACE_SCHEMA
            )
            
            if not response or not response.get("success"):
                return CorrectionResult(success=False, error="Empty or failed response from LLM")
            
            # Parse response
            import json
            result = response.get("parsed_json")
            if result is None:
                response_text = response.get("response", "")
                result = json.loads(response_text) if response_text else {}
            
            fixes = result.get("fixes", [])
            
            if not fixes:
                return CorrectionResult(
                    success=False,
                    error="No fixes suggested",
                    code=code
                )
            
            # Apply fixes
            new_code, applied, details = self._apply_fixes(code, fixes)
            
            if applied == 0:
                return CorrectionResult(
                    success=False,
                    error="No fixes could be applied (search text not found)",
                    code=code,
                    details=details
                )
            
            # Validate result
            validation = self.validator.validate_code(new_code)
            
            if validation["valid"]:
                return CorrectionResult(
                    success=True,
                    code=new_code,
                    fixes_applied=applied,
                    details=details
                )
            else:
                # Fixes applied but still invalid - might need another round
                return CorrectionResult(
                    success=False,
                    code=new_code,
                    fixes_applied=applied,
                    error=f"Still has errors: {validation.get('error', 'Unknown')}",
                    details=details
                )
                
        except Exception as e:
            return CorrectionResult(
                success=False,
                error=f"Correction failed: {str(e)}",
                code=code
            )
    
    def _apply_fixes(self, code: str, fixes: List[Dict]) -> tuple:
        """
        Apply search/replace fixes to code.
        
        Returns:
            Tuple of (new_code, fixes_applied_count, details_list)
        """
        new_code = code
        applied = 0
        details = []
        
        for fix in fixes:
            search = fix.get("search", "")
            replace = fix.get("replace", "")
            reason = fix.get("reason", "")
            
            if not search:
                details.append(f"WARN Skipped: empty search text")
                continue
            
            if search in new_code:
                # Check uniqueness
                count = new_code.count(search)
                if count == 1:
                    new_code = new_code.replace(search, replace)
                    applied += 1
                    details.append(f"OK Applied: {reason}" if reason else f"OK Applied fix")
                else:
                    details.append(f"WARN Skipped: search text appears {count} times (must be unique)")
            else:
                details.append(f"FAIL Not found: search text not in code")
        
        return new_code, applied, details
    
    def _build_correction_prompt(
        self,
        code: str,
        error_message: str,
        section: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build the correction prompt"""
        context = ""
        if section:
            context = f"""
SECTION CONTEXT:
- Title: {section.get('title', 'Unknown')}
- Duration: {section.get('target_duration', 30)} seconds
"""
        
        return f"""Fix this Manim code error.

ERROR:
{error_message}

{context}

CURRENT CODE:
```python
{code}
```

Analyze the error and provide fixes using the apply_fixes tool.
Each fix must have:
- search: EXACT text from the code (copy-paste, preserve whitespace)
- replace: Fixed replacement text
- reason: Brief explanation

Common fixes:
- BOTTOM → DOWN, TOP → UP (no BOTTOM/TOP constants)
- Color names must be UPPERCASE (blue → BLUE)
- run_time must be > 0 (use max(0.1, value))
- self.wait() must be > 0
"""
    
    def _build_system_prompt(self) -> str:
        """Build system prompt for correction"""
        return f"""You fix Manim code errors using precise search/replace operations.

{get_manim_reference()}

RULES:
1. Find the EXACT text causing the error (copy-paste from code)
2. Include enough context to make the search unique
3. Fix the ROOT CAUSE, not symptoms
4. Preserve indentation exactly
5. Multiple fixes allowed for multiple issues
"""


def create_correction_tools(engine, validator) -> CorrectionToolHandler:
    """Create correction tool handler"""
    return CorrectionToolHandler(engine, validator)
