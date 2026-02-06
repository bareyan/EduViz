
from app.services.pipeline.animation.generation.refinement.edit_applier import apply_edits_atomically

def test_apply_edits_success():
    code = "hello world"
    edits = [{"search_text": "world", "replacement_text": "python"}]
    
    new_code, stats = apply_edits_atomically(code, edits)
    assert new_code == "hello python"
    assert stats["successful"] == 1
    assert stats["failed"] == 0

def test_apply_edits_not_found():
    code = "hello world"
    edits = [{"search_text": "mars", "replacement_text": "python"}]
    
    new_code, stats = apply_edits_atomically(code, edits)
    assert new_code == "hello world"
    assert stats["successful"] == 0
    assert stats["failed"] == 1
    assert stats["failure_reasons"]["not_found"] == 1

def test_apply_edits_ambiguous():
    code = "hello world world"
    edits = [{"search_text": "world", "replacement_text": "python"}]
    
    new_code, stats = apply_edits_atomically(code, edits)
    assert new_code == "hello world world"
    assert stats["successful"] == 0
    assert stats["failed"] == 1
    assert stats["failure_reasons"]["ambiguous"] == 1
