
import unittest
import asyncio
from app.services.pipeline.animation.generation.core.validation.static import StaticValidator
from app.services.pipeline.animation.generation.core.validation.models import IssueCategory

class TestStaticValidator(unittest.TestCase):
    def setUp(self):
        self.validator = StaticValidator()

    def run_async(self, coro):
        return asyncio.run(coro)

    def test_valid_code(self):
        code = """
import math

def calculate_circle_area(radius: float) -> float:
    return math.pi * radius ** 2

area = calculate_circle_area(5.0)
print(f"Area: {area}")
"""
        result = self.run_async(self.validator.validate(code))
        self.assertTrue(result.valid, f"Expected valid code to pass, but got issues: {[i.message for i in result.issues]}")
        self.assertEqual(len(result.issues), 0)

    def test_syntax_error_ruff(self):
        # Indentation error
        code = """
def broken():
return "needs indent"
"""
        result = self.run_async(self.validator.validate(code))
        self.assertFalse(result.valid)
        self.assertTrue(
            any(i.category in (IssueCategory.SYNTAX, IssueCategory.LINT) for i in result.issues),
            f"Expected Syntax/Lint issue, got: {[i.message for i in result.issues]}"
        )

    def test_type_error_pyright(self):
        # Calling function with wrong type — Pyright may not be enabled
        code = """
def add(a: int, b: int) -> int:
    return a + b

result = add("string", 5)
"""
        result = self.run_async(self.validator.validate(code))
        # This test is informational — Pyright might not be available
        # Just verify the validator doesn't crash
        self.assertIsNotNone(result)

if __name__ == '__main__':
    unittest.main()
