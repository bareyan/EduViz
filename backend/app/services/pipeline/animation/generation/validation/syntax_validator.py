"""
Python syntax validation

Validates Python code syntax using AST parsing.
Single Responsibility: Check Python syntax correctness only.
"""

import ast
from typing import Optional
from dataclasses import dataclass


@dataclass
class SyntaxValidationResult:
    """Result of syntax validation"""
    valid: bool
    error_message: Optional[str] = None
    line_number: Optional[int] = None
    error_type: Optional[str] = None
    column: Optional[int] = None


class PythonSyntaxValidator:
    """Validates Python code syntax using AST parsing"""
    
    def validate(self, code: str) -> SyntaxValidationResult:
        """
        Validate Python syntax of code.
        
        Args:
            code: Python code string to validate
            
        Returns:
            SyntaxValidationResult with validation status and error details
        """
        if not code or not code.strip():
            return SyntaxValidationResult(
                valid=False,
                error_message="Code is empty",
                error_type="EmptyCodeError"
            )
        
        try:
            ast.parse(code)
            return SyntaxValidationResult(valid=True)
            
        except SyntaxError as e:
            return SyntaxValidationResult(
                valid=False,
                error_message=f"Line {e.lineno}: {e.msg}",
                line_number=e.lineno,
                column=e.offset,
                error_type="SyntaxError"
            )
            
        except Exception as e:
            return SyntaxValidationResult(
                valid=False,
                error_message=str(e),
                error_type=type(e).__name__
            )
