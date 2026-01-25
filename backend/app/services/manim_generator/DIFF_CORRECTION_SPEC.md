# Diff-Based Correction System Specification

## Overview
Replace full code regeneration with targeted diff-based fixes for faster, cheaper error correction.

## Current vs Proposed

### Current System
```
Error → Send Full Code (500-1000 tokens) → Receive Full Code (500-1000 tokens) → Replace
```
- Cost: ~2,000 tokens/attempt
- Speed: 10-30 seconds
- Max attempts: 1-3

### Proposed System
```
Error → Send Context (100-200 tokens) → Receive Fixes (50-150 tokens) → Apply Surgically
```
- Cost: ~200-300 tokens/attempt
- Speed: 2-5 seconds
- Max attempts: 5-10

## Implementation Components

### 1. Error Analysis Module (`error_analyzer.py`)

```python
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class ErrorContext:
    """Structured error information extracted from Manim stderr"""
    error_type: str  # "SyntaxError", "NameError", etc.
    error_message: str
    line_number: Optional[int]
    column_number: Optional[int]
    code_snippet: str  # ±5 lines around error
    full_traceback: str

def parse_manim_error(stderr: str, original_code: str) -> ErrorContext:
    """
    Parse Manim stderr to extract structured error information.
    
    Examples:
    - "NameError: name 'BOTTOM' is not defined" → {type: "NameError", message: "BOTTOM not defined"}
    - "SyntaxError: invalid syntax" with line number → {type: "SyntaxError", line: 45}
    """
    pass

def extract_code_context(code: str, line_number: int, context_lines: int = 5) -> str:
    """Extract relevant code snippet around error line"""
    pass
```

### 2. Fix Schema (`fix_schema.py`)

```python
from typing import List, Optional
from pydantic import BaseModel

class CodeFix(BaseModel):
    """Single search-replace fix"""
    search: str  # Exact text to find
    replace: str  # Exact replacement text
    line_hint: Optional[int] = None  # Optional line number hint
    reason: str  # Why this fix is needed
    confidence: float = 1.0  # 0.0-1.0 confidence score

class FixResponse(BaseModel):
    """Complete fix response from LLM"""
    fixes: List[CodeFix]
    analysis: str  # Brief explanation of the error
    requires_full_rewrite: bool = False  # Flag if diff won't work

# Gemini Structured Output Schema
FIX_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "fixes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "search": {"type": "string"},
                    "replace": {"type": "string"},
                    "line_hint": {"type": "integer"},
                    "reason": {"type": "string"},
                    "confidence": {"type": "number"}
                },
                "required": ["search", "replace", "reason"]
            }
        },
        "analysis": {"type": "string"},
        "requires_full_rewrite": {"type": "boolean"}
    },
    "required": ["fixes", "analysis"]
}
```

### 3. Fix Application Engine (`fix_applicator.py`)

```python
from typing import Optional, List, Tuple

class FixApplicationError(Exception):
    """Raised when a fix cannot be applied"""
    pass

class FixApplicator:
    """Applies search-replace fixes to code with validation"""
    
    def __init__(self, original_code: str):
        self.original_code = original_code
        self.current_code = original_code
        self.applied_fixes: List[CodeFix] = []
    
    def apply_fix(self, fix: CodeFix) -> bool:
        """
        Apply a single fix to current code.
        Returns True if successful, False if search string not found.
        """
        if fix.search not in self.current_code:
            # Try fuzzy matching with whitespace normalization
            if not self._try_fuzzy_apply(fix):
                return False
        
        # Count occurrences
        count = self.current_code.count(fix.search)
        if count == 0:
            return False
        elif count == 1:
            self.current_code = self.current_code.replace(fix.search, fix.replace, 1)
        else:
            # Multiple matches - use line hint if available
            if fix.line_hint:
                self.current_code = self._replace_at_line(fix)
            else:
                # Replace all occurrences
                self.current_code = self.current_code.replace(fix.search, fix.replace)
        
        self.applied_fixes.append(fix)
        return True
    
    def apply_all(self, fixes: List[CodeFix]) -> Tuple[str, List[CodeFix]]:
        """
        Apply all fixes in order.
        Returns (resulting_code, list_of_failed_fixes)
        """
        failed = []
        for fix in fixes:
            if not self.apply_fix(fix):
                failed.append(fix)
        
        return self.current_code, failed
    
    def validate_syntax(self) -> Optional[str]:
        """
        Check if current code has valid Python syntax.
        Returns None if valid, error message if invalid.
        """
        try:
            compile(self.current_code, "<string>", "exec")
            return None
        except SyntaxError as e:
            return str(e)
    
    def rollback(self):
        """Rollback to original code"""
        self.current_code = self.original_code
        self.applied_fixes = []
    
    def _try_fuzzy_apply(self, fix: CodeFix) -> bool:
        """Try applying fix with normalized whitespace"""
        # Normalize whitespace in search pattern
        import re
        search_normalized = re.sub(r'\s+', ' ', fix.search.strip())
        
        # Find matching lines
        for line_no, line in enumerate(self.current_code.split('\n')):
            line_normalized = re.sub(r'\s+', ' ', line.strip())
            if search_normalized in line_normalized:
                # Replace in original line preserving indentation
                indent = len(line) - len(line.lstrip())
                new_line = ' ' * indent + fix.replace
                lines = self.current_code.split('\n')
                lines[line_no] = new_line
                self.current_code = '\n'.join(lines)
                return True
        return False
    
    def _replace_at_line(self, fix: CodeFix) -> str:
        """Replace occurrence at specific line number"""
        lines = self.current_code.split('\n')
        if fix.line_hint and 0 <= fix.line_hint < len(lines):
            lines[fix.line_hint] = lines[fix.line_hint].replace(fix.search, fix.replace, 1)
        return '\n'.join(lines)
```

### 4. Diff Correction Prompt

```python
# In prompts.py

DIFF_CORRECTION_SYSTEM_INSTRUCTION = """You are an expert Manim debugger. 
Analyze the error and provide MINIMAL targeted fixes as search-replace pairs.
DO NOT regenerate the entire code. Only fix the specific error.

Return ONLY valid JSON in this format:
{
  "analysis": "Brief explanation of the error",
  "fixes": [
    {
      "search": "exact text to find (including indentation)",
      "replace": "exact replacement text (including indentation)",
      "line_hint": 45,
      "reason": "Why this fix is needed",
      "confidence": 0.95
    }
  ],
  "requires_full_rewrite": false
}

CRITICAL RULES:
1. 'search' must be EXACT text from the code (copy-paste)
2. Include proper indentation in search/replace
3. If error needs multiple fixes, include all in 'fixes' array
4. Set requires_full_rewrite=true ONLY if diff-based fix won't work
5. Keep fixes MINIMAL - don't change working code
"""

def build_diff_correction_prompt(error_context: ErrorContext, section: dict) -> str:
    """Build prompt for diff-based correction"""
    
    return f"""Fix this Manim error with minimal targeted changes.

ERROR DETAILS:
Type: {error_context.error_type}
Message: {error_context.error_message}
Line: {error_context.line_number or 'Unknown'}

CODE CONTEXT (±5 lines around error):
```python
{error_context.code_snippet}
```

SECTION INFO:
Duration: {section.get('target_duration', 'Unknown')}s
Content: {section.get('narration', '')[:200]}...

COMMON MANIM FIXES:
- BOTTOM → DOWN (BOTTOM doesn't exist)
- TOP → UP (TOP doesn't exist)
- blue → BLUE (colors must be uppercase)
- r"\\frac" → r"\\\\frac" (MathTex needs double backslash)
- FadeOut(obj) → Must add object first with self.add(obj)

Analyze the error and provide JSON with targeted fixes.
If the code is fundamentally wrong and needs a full rewrite, set requires_full_rewrite=true.
"""
```

### 5. Integration with Renderer

```python
# In renderer.py - New function

async def correct_manim_code_diff(
    generator: "ManimGenerator",
    original_code: str,
    error_message: str,
    section: Dict[str, Any],
    attempt: int = 0
) -> Optional[str]:
    """
    Diff-based code correction - returns targeted fixes.
    Falls back to full regeneration if diff approach fails.
    """
    from google.genai import types
    from .error_analyzer import parse_manim_error
    from .fix_applicator import FixApplicator
    from .fix_schema import FIX_RESPONSE_SCHEMA, FixResponse
    from .prompts import DIFF_CORRECTION_SYSTEM_INSTRUCTION, build_diff_correction_prompt
    
    # Parse error to extract context
    error_context = parse_manim_error(error_message, original_code)
    
    # Build targeted prompt
    prompt = build_diff_correction_prompt(error_context, section)
    
    # Request structured JSON output
    config = types.GenerateContentConfig(
        system_instruction=DIFF_CORRECTION_SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=FIX_RESPONSE_SCHEMA,
        temperature=0.1,
        max_output_tokens=2048
    )
    
    try:
        response = await asyncio.to_thread(
            generator.client.models.generate_content,
            model=generator.CORRECTION_MODEL,
            contents=prompt,
            config=config
        )
        
        generator.cost_tracker.track_usage(response, generator.CORRECTION_MODEL)
        
        # Parse response
        fix_response = FixResponse.parse_raw(response.text)
        
        # Check if full rewrite is needed
        if fix_response.requires_full_rewrite:
            print(f"[DiffCorrection] LLM recommends full rewrite, falling back...")
            return await correct_manim_code_full(generator, original_code, error_message, section, attempt)
        
        # Apply fixes
        applicator = FixApplicator(original_code)
        fixed_code, failed_fixes = applicator.apply_all(fix_response.fixes)
        
        # Validate syntax
        syntax_error = applicator.validate_syntax()
        if syntax_error:
            print(f"[DiffCorrection] Syntax error after applying fixes: {syntax_error}")
            # Retry with full regeneration
            return await correct_manim_code_full(generator, original_code, error_message, section, attempt)
        
        if failed_fixes:
            print(f"[DiffCorrection] ⚠️ {len(failed_fixes)} fixes failed to apply")
            for fix in failed_fixes:
                print(f"  - Failed: {fix.reason}")
        
        print(f"[DiffCorrection] ✓ Applied {len(applicator.applied_fixes)} fixes successfully")
        return fixed_code
        
    except Exception as e:
        print(f"[DiffCorrection] Error: {e}, falling back to full regeneration")
        return await correct_manim_code_full(generator, original_code, error_message, section, attempt)


# Update existing function to use diff-based approach
async def correct_manim_code(
    generator: "ManimGenerator",
    original_code: str,
    error_message: str,
    section: Dict[str, Any],
    attempt: int = 0
) -> Optional[str]:
    """
    Smart correction: Try diff-based first (fast), fallback to full regen (slow).
    """
    USE_DIFF_CORRECTIONS = getattr(generator, 'USE_DIFF_CORRECTIONS', True)
    
    if USE_DIFF_CORRECTIONS and attempt < 5:
        # Try diff-based correction (cheap, fast)
        result = await correct_manim_code_diff(generator, original_code, error_message, section, attempt)
        if result:
            return result
    
    # Fallback to full regeneration
    return await correct_manim_code_full(generator, original_code, error_message, section, attempt)
```

### 6. Configuration Updates

```python
# In config/models.py

@dataclass
class ModelConfig:
    """Configuration for a single model"""
    model_name: str
    thinking_level: Optional[ThinkingLevel] = None
    description: str = ""
    max_correction_attempts: int = 2
    use_diff_corrections: bool = True  # NEW: Enable diff-based fixes
    diff_attempt_limit: int = 5  # NEW: Max diff attempts before full regen


# Update Manim generation config
manim_generation: ModelConfig = field(default_factory=lambda: ModelConfig(
    model_name="gemini-3-flash-preview",
    thinking_level=ThinkingLevel.MEDIUM,
    description="Generate Manim animation code",
    max_correction_attempts=7,  # INCREASED from 1
    use_diff_corrections=True,  # NEW
    diff_attempt_limit=5  # NEW
))
```

## Testing Strategy

### Unit Tests
1. **Error Parser Tests**
   - Various Manim error formats
   - Edge cases (no line numbers, truncated errors)

2. **Fix Applicator Tests**
   - Single fix application
   - Multiple non-conflicting fixes
   - Multiple overlapping fixes
   - Fuzzy matching
   - Syntax validation

3. **Integration Tests**
   - End-to-end correction flow
   - Fallback to full regeneration
   - Cost tracking

### A/B Testing
- Run 50% of corrections with diff-based, 50% with full regen
- Compare success rates, costs, speeds
- Gradually increase diff-based percentage

## Metrics to Track

1. **Success Rate**: % of errors fixed on first attempt
2. **Token Usage**: Average tokens per correction
3. **Speed**: Average correction time
4. **Attempt Distribution**: How many attempts typically needed
5. **Fallback Rate**: How often do we fallback to full regen
6. **Error Type Distribution**: Which errors are most common

## Rollout Plan

### Week 1-2: Development
- Implement core components
- Write unit tests
- Manual testing with known errors

### Week 3: Staging Deployment
- Deploy with feature flag OFF by default
- Enable for internal testing
- Monitor error rates

### Week 4: Gradual Rollout
- Enable for 10% of corrections
- Monitor metrics
- Increase to 50% if successful
- Full rollout if metrics good

### Week 5: Optimization
- Analyze error patterns
- Add template fixes for common errors
- Tune retry limits based on data

## Expected Outcomes

### Immediate Benefits (Week 4)
- 5-10x reduction in correction tokens
- 5-6x faster correction speed
- Can afford 5-7 attempts vs current 1-3

### Long-term Benefits (Month 2-3)
- Higher overall success rate (fewer fallback scenes)
- Lower per-video generation cost
- Faster video generation pipeline
- Better user experience (fewer "Section X" placeholder videos)

### Potential Issues
- Initial learning curve for LLM to generate good diffs
- Some errors still need full regeneration
- Edge cases where fuzzy matching fails

## Success Criteria

✅ **Must Have:**
- 80%+ of errors fixable with diff approach
- <5 second average correction time
- <300 tokens average per correction
- No regression in success rate

✅ **Nice to Have:**
- 90%+ of errors fixable with diff approach
- <3 second average correction time
- Template-based fixes for common errors
- Learning system for error patterns
