# Manim Code Validation System - Architecture Documentation

## Overview

This package provides a modular, testable validation system for Manim code generation.
It follows Google's engineering best practices: strong SRP (Single Responsibility Principle),
DRY (Don't Repeat Yourself), comprehensive testing, and clean architecture.

## Architecture

### Validators (validation/)

Each validator has a single, focused responsibility:

1. **PythonSyntaxValidator** (`syntax_validator.py`)
   - Responsibility: Validate Python syntax using AST parsing
   - Input: Python code string
   - Output: SyntaxValidationResult with error details
   - No Manim-specific logic

2. **ManimStructureValidator** (`manim_validator.py`)
   - Responsibility: Check Manim-specific code structure and patterns
   - Validates: Scene class, construct method, font sizes, text lengths
   - Output: ManimValidationResult with errors and warnings
   - Independent of syntax validation

3. **ManimImportsValidator** (`imports_validator.py`)
   - Responsibility: Validate import statements
   - Checks: Missing imports, unused imports, wildcard imports
   - Output: ImportsValidationResult
   - Independent of syntax and structure

4. **SpatialValidator** (`spatial_validator.py`)
   - Responsibility: Validate spatial layout and positioning
   - Checks: Out-of-bounds coordinates, overlapping objects, text overflow, unpositioned texts
   - Bounds: X (-6.5 to 6.5), Y (-3.5 to 3.5) for standard Manim screen
   - Output: SpatialValidationResult with spatial errors and warnings
   - Independent of other validators

5. **CodeValidator** (`code_validator.py`)
   - Responsibility: Orchestrate all validators
   - Aggregates results from all four validators
   - Short-circuits on syntax errors (no point checking structure if syntax invalid)
   - Provides unified interface and dict conversion

### Function Calling Tools (tools.py)

**Integration with ManimGenerator**: The tools are now fully integrated into the code generation pipeline!

- **ToolExecutor**: Executes function calling tools and delegates to validators
- **Tools**: 
  - `validate_code`: Check syntax, structure, imports, and spatial layout
  - `apply_fix`: Apply search/replace corrections
  - `finalize_code`: Mark code as complete (only when valid)
- **MANIM_TOOLS**: Tool definitions for Gemini function calling API
- **Integrated into generator.py**: `_generate_with_tools()` method uses iterative validation

### How It Works (Integrated Pipeline)

1. **Visual Script Generation** (Shot 1): Generate storyboard/visual plan
2. **Tool-Based Code Generation** (Shot 2): 
   - Model generates code
   - Automatically calls `validate_code` tool
   - If validation fails, model calls `apply_fix` to correct issues
   - Repeats validation/correction cycle
   - Calls `finalize_code` when all checks pass
3. **Fallback**: If tool-based generation fails, falls back to single-shot with manual validation
- Delegates validation to the CodeValidator
- Handles search/replace operations
- Clean separation between tool execution and validation logic

## Design Principles

### Single Responsibility Principle (SRP)
- Each validator has ONE job
- Each validator is independent and can be tested in isolation
- Changes to one validator don't affect others

### DRY (Don't Repeat Yourself)
- Common validation logic is encapsulated in reusable classes
- No duplicated validation code across the codebase
- Configuration constants are centralized

### Testability
- Each validator has comprehensive unit tests
- Tests cover valid cases, error cases, and edge cases
- 51 tests with 100% pass rate
- Tests are isolated and fast (<1 second)

### Clean Architecture
- Clear separation of concerns
- Validators don't depend on tools
- Tools depend on validators (one-way dependency)
- Easy to extend with new validators

## Usage Examples

### Basic Validation with Spatial Checks

```python
from app.services.manim_generator.validation import CodeValidator

validator = CodeValidator()

code = """
from manim import *

class MyScene(Scene):
    def construct(self):
        text = Text("Hello").move_to([10, 0, 0])  # Out of bounds!
        self.play(Write(text))
"""

result = validator.validate(code)

if result.valid:
    print("Code is valid!")
else:
    print(result.get_error_summary())
    
# Check individual validators
print(f"Syntax Valid: {result.syntax.valid}")
print(f"Structure Valid: {result.structure.valid}")
print(f"Imports Valid: {result.imports.valid}")
print(f"Spatial Valid: {result.spatial.valid}")

# Access spatial issues
for error in result.spatial.errors:
    print(f"Line {error.line_number}: {error.message}")
```

### Using Individual Validators

```python
from app.services.manim_generator.validation import (
    PythonSyntaxValidator,
    ManimStructureValidator
)

# Just check syntax
syntax_validator = PythonSyntaxValidator()
syntax_result = syntax_validator.validate(code)

# Just check Manim structure
structure_validator = ManimStructureValidator()
structure_result = structure_validator.validate(code)
```

### Tool Execution

```python
from app.services.manim_generator.tools import ToolExecutor

executor = ToolExecutor()

# Validate code
result = executor.execute("validate_code", {"code": code})

# Apply a fix
result = executor.execute("apply_fix", {
    "code": code,
    "search": "old_text",
    "replace": "new_text",
    "reason": "Fix typo"
})

# Finalize (validates before accepting)
result = executor.execute("finalize_code", {"code": final_code})
```

## Future Enhancements

### Potential New Validators
1. **PerformanceValidator**: Check for performance anti-patterns
2. **AccessibilityValidator**: Validate color contrast, text size
3. **MathValidator**: Validate LaTeX syntax in MathTex
4. **TimingValidator**: Check animation timing against audio duration

### Enhanced Tool Support
1. **suggest_fix**: LLM suggests fixes without applying
2. **batch_validate**: Validate multiple code snippets
3. **compare_versions**: Compare before/after code

## Testing

Run all validation tests:
```bash
pytest tests/services/test_*_validator.py -v
pytest tests/services/test_manim_tools.py -v
```

Run with coverage:
```bash
pytest tests/services/ --cov=app.services.manim_generator.validation --cov-report=html
```

## Performance

- Syntax validation: ~1ms per code snippet
- Structure validation: ~2ms per code snippet
- Import validation: ~1ms per code snippet
- Total validation time: <5ms for typical code

All validators are synchronous and run in sequence (fast-fail on syntax errors).

## Error Handling

All validators:
- Never raise exceptions (return error results instead)
- Provide detailed error messages with line numbers
- Distinguish between errors (blocking) and warnings (informational)

## Dependencies

- Python 3.12+
- Built-in `ast` module (no external deps for syntax validation)
- No AI/LLM dependencies (validators are deterministic)

## Maintenance

- Each validator is independently maintainable
- Tests serve as documentation and regression prevention
- Configuration constants are clearly documented
- Type hints throughout for better IDE support
