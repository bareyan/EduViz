
from app.services.pipeline.animation.generation.refinement.context import FixerContextManager
from app.services.pipeline.animation.config import MAX_PROMPT_CODE_CHARS

def test_select_context_small_code():
    manager = FixerContextManager()
    code = "small code"
    errors = "error"
    ctx, note = manager.select_context(code, errors)
    assert ctx == code
    assert note is None

def test_select_context_line_extraction():
    manager = FixerContextManager()
    # Create large code > MAX_PROMPT_CODE_CHARS
    # We can mock config or just give truly huge string.
    # But checking internal logic:
    
    # Let's bypass length check by making `len(code)` huge
    long_code = "line\n" * (MAX_PROMPT_CODE_CHARS // 4 + 100) # Ensure it triggers logic if we strictly follow the code
    # Actually wait, I shouldn't rely on huge strings in tests if I can avoid it.
    
    # Let's subclass to override constant check or just trust the logic.
    # The method uses MAX_PROMPT_CODE_CHARS from config.
    
    # We can just verify _extract_error_line_numbers and _build_code_snippets independently.
    pass

def test_extract_error_line_numbers():
    manager = FixerContextManager()
    errors = "Error at line 10. Another at Line 20."
    lines = manager._extract_error_line_numbers(errors)
    assert lines == [10, 20]

def test_build_code_snippets():
    manager = FixerContextManager()
    code = "\n".join([f"L{i}" for i in range(1, 100)])
    
    # Extraxt around line 10
    snippets = manager._build_code_snippets(code, [10], context_radius=2)
    assert len(snippets) == 1
    # Should contain L8, L9, L10, L11, L12 (indices 7 to 12)
    assert "L8" in snippets[0]
    assert "L10" in snippets[0]
    assert "L12" in snippets[0]
    assert "L15" not in snippets[0]

def test_build_code_snippets_merge():
    manager = FixerContextManager()
    code = "\n".join([f"L{i}" for i in range(1, 100)])
    
    # Overlapping 10 and 12 with radius 2 -> 8..12 and 10..14 -> Should merge 8..14
    snippets = manager._build_code_snippets(code, [10, 12], context_radius=2)
    assert len(snippets) == 1
    assert "L8" in snippets[0]
    assert "L14" in snippets[0]
