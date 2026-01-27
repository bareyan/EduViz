"""
Manim imports validation

Validates that Manim imports are correct and complete.
Single Responsibility: Check import statements only.
"""

import re
from typing import Set, List
from dataclasses import dataclass, field


@dataclass
class ImportsValidationResult:
    """Result of imports validation"""
    valid: bool
    missing_imports: List[str] = field(default_factory=list)
    unused_imports: List[str] = field(default_factory=list)
    has_wildcard: bool = False


class ManimImportsValidator:
    """Validates Manim import statements"""
    
    # Common Manim classes that are frequently used
    COMMON_CLASSES = {
        'Scene', 'Text', 'MathTex', 'Tex', 'VGroup',
        'Write', 'FadeIn', 'FadeOut', 'Create', 'Uncreate',
        'Transform', 'ReplacementTransform', 'Indicate',
        'Circle', 'Square', 'Rectangle', 'Arrow', 'Line', 'Dot',
        'Axes', 'NumberPlane', 'Graph',
        'BLUE', 'RED', 'GREEN', 'YELLOW', 'WHITE', 'BLACK',
        'ORANGE', 'PURPLE', 'PINK', 'TEAL',
        'UP', 'DOWN', 'LEFT', 'RIGHT', 'ORIGIN',
        'PI', 'TAU', 'DEGREES'
    }
    
    def validate(self, code: str) -> ImportsValidationResult:
        """
        Validate Manim imports.
        
        Args:
            code: Manim Python code to validate
            
        Returns:
            ImportsValidationResult with missing/unused imports
        """
        # Check for wildcard import first
        if 'from manim import *' in code:
            return ImportsValidationResult(
                valid=True,
                has_wildcard=True
            )
        
        used_classes = self._extract_used_classes(code)
        imported_classes = self._extract_imported_classes(code)
        
        missing = used_classes - imported_classes
        unused = imported_classes - used_classes
        
        return ImportsValidationResult(
            valid=len(missing) == 0,
            missing_imports=sorted(list(missing)),
            unused_imports=sorted(list(unused))
        )
    
    def _extract_used_classes(self, code: str) -> Set[str]:
        """Extract class names that are actually used in the code"""
        used = set()
        
        for cls in self.COMMON_CLASSES:
            # Check various usage patterns
            if self._is_class_used(code, cls):
                used.add(cls)
        
        return used
    
    def _is_class_used(self, code: str, class_name: str) -> bool:
        """Check if a class name is used in the code"""
        patterns = [
            f"{class_name}(",           # Direct instantiation
            f" {class_name} ",           # Standalone reference
            f"[{class_name}]",          # In list
            f"({class_name})",          # In tuple/parens
            f",{class_name},",          # In sequence
            f"={class_name}",           # Assignment
        ]
        
        for pattern in patterns:
            if pattern in code:
                return True
        
        # Check if it ends with the class name
        if code.rstrip().endswith(class_name):
            return True
        
        return False
    
    def _extract_imported_classes(self, code: str) -> Set[str]:
        """Extract class names from import statements"""
        imported = set()
        import_pattern = r'from manim import (.+)'
        
        for match in re.finditer(import_pattern, code):
            imports_str = match.group(1)
            for item in imports_str.split(','):
                # Handle "import X as Y" syntax
                item = item.strip().split(' as ')[0].strip()
                if item and item != '*':
                    imported.add(item)
        
        return imported
