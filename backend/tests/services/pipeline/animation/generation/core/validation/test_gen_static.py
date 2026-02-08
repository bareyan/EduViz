
import pytest
from unittest.mock import AsyncMock, patch, Mock
import shutil
from app.services.pipeline.animation.generation.core.validation.static import StaticValidator, ValidationResult
from app.services.pipeline.animation.generation.core.validation.models import IssueCategory, IssueSeverity

@pytest.fixture
def static_validator():
    # Mock shutil.which to pretend ruff exists
    with patch("shutil.which", return_value="ruff"):
        return StaticValidator()

@pytest.mark.asyncio
async def test_validate_forbidden_imports(static_validator):
    code = "import os\nprint('bad')"
    
    # We mock _run_ruff to return empty list so we only test AST checks
    with patch.object(static_validator, "_run_ruff", new_callable=AsyncMock) as mock_ruff:
        mock_ruff.return_value = []
        
        result = await static_validator.validate(code)
        
        assert result.valid is False
        assert any(i.category == IssueCategory.SECURITY and "Forbidden import: os" in i.message for i in result.issues)

@pytest.mark.asyncio
async def test_validate_forbidden_builtins(static_validator):
    code = "eval('print(1)')"
    
    with patch.object(static_validator, "_run_ruff", new_callable=AsyncMock) as mock_ruff:
        mock_ruff.return_value = []
        
        result = await static_validator.validate(code)
        
        assert result.valid is False
        assert any(i.category == IssueCategory.SECURITY and "Forbidden builtin: eval" in i.message for i in result.issues)

@pytest.mark.asyncio
async def test_validate_syntax_error(static_validator):
    code = "print('forgot closing paren"
    
    res = await static_validator.validate(code)
    
    assert res.valid is False
    assert any(i.category == IssueCategory.SYNTAX for i in res.issues)

@pytest.mark.asyncio
async def test_validate_ruff_errors(static_validator):
    code = "print(undefined_var)"
    
    with patch.object(static_validator, "_run_ruff", new_callable=AsyncMock) as mock_ruff:
        # Simulate ruff undefined name error
        mock_ruff.return_value = [{
            "code": "F821",
            "message": "Undefined name 'undefined_var'",
            "location": {"row": 1}
        }]
        
        result = await static_validator.validate(code)
        
        assert result.valid is False
        assert any(i.category == IssueCategory.LINT and "F821" in i.message for i in result.issues)
