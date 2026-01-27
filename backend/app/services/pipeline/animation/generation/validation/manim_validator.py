"""
Manim structure validation

Validates Manim-specific code structure and patterns.
Single Responsibility: Check Manim code structure, not syntax.
"""

import re
from typing import List
from dataclasses import dataclass, field


@dataclass
class ManimValidationResult:
    """Result of Manim structure validation"""
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class ManimStructureValidator:
    """Validates Manim-specific code structure"""
    
    # Configuration
    MAX_FONT_SIZE = 48
    RECOMMENDED_FONT_SIZE = 36
    MAX_TEXT_LENGTH = 60
    
    def validate(self, code: str) -> ManimValidationResult:
        """
        Validate Manim code structure and patterns.
        
        Args:
            code: Manim Python code to validate
            
        Returns:
            ManimValidationResult with errors and warnings
        """
        errors = []
        warnings = []
        
        # Run all validation checks
        errors.extend(self._check_scene_class(code))
        errors.extend(self._check_construct_method(code))
        warnings.extend(self._check_background_color(code))
        warnings.extend(self._check_font_sizes(code))
        warnings.extend(self._check_text_lengths(code))
        warnings.extend(self._check_wait_calls(code))
        
        return ManimValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def _check_scene_class(self, code: str) -> List[str]:
        """Check if code defines a Scene class"""
        if "class" not in code or "Scene" not in code:
            return ["Code must define a class inheriting from Scene"]
        return []
    
    def _check_construct_method(self, code: str) -> List[str]:
        """Check if Scene has construct method"""
        if "def construct(self)" not in code:
            return ["Scene class must have a construct(self) method"]
        return []
    
    def _check_background_color(self, code: str) -> List[str]:
        """Check for background_color setting (should be pre-configured)"""
        if "background_color" in code.lower():
            return ["Don't set background_color - it's pre-configured in the scene"]
        return []
    
    def _check_font_sizes(self, code: str) -> List[str]:
        """Check for excessive font sizes"""
        warnings = []
        font_size_pattern = r'font_size\s*=\s*(\d+)'
        
        for match in re.finditer(font_size_pattern, code):
            size = int(match.group(1))
            if size > self.MAX_FONT_SIZE:
                warnings.append(
                    f"Font size {size} exceeds maximum {self.MAX_FONT_SIZE} "
                    f"(recommended: {self.RECOMMENDED_FONT_SIZE})"
                )
            elif size > self.RECOMMENDED_FONT_SIZE:
                warnings.append(
                    f"Font size {size} is large "
                    f"(recommended: {self.RECOMMENDED_FONT_SIZE} or less)"
                )
        
        return warnings
    
    def _check_text_lengths(self, code: str) -> List[str]:
        """Check for overly long text strings"""
        warnings = []
        
        for i, line in enumerate(code.split('\n'), 1):
            text_match = re.search(r'Text\(["\']([^"\']+)["\']', line)
            if text_match:
                text_content = text_match.group(1)
                if len(text_content) > self.MAX_TEXT_LENGTH:
                    warnings.append(
                        f"Line {i}: Text content too long ({len(text_content)} chars > "
                        f"{self.MAX_TEXT_LENGTH}) - consider splitting"
                    )
        
        return warnings
    
    def _check_wait_calls(self, code: str) -> List[str]:
        """Check for missing wait() calls after animations"""
        if "self.play(" in code and "self.wait(" not in code:
            return ["Consider adding self.wait() calls after animations for pacing"]
        return []
