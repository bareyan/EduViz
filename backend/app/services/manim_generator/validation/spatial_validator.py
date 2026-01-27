"""
Spatial layout validation for Manim code

Validates that objects don't overlap and stay within screen bounds.
Single Responsibility: Check spatial positioning and layout only.

Manim coordinate system:
- Screen dimensions: roughly -7 to 7 horizontally, -4 to 4 vertically
- Objects use .move_to(), .shift(), .to_edge(), .next_to() for positioning
"""

import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field


@dataclass
class SpatialIssue:
    """A spatial layout issue"""
    line_number: int
    severity: str  # "error" or "warning"
    message: str
    code_snippet: str


@dataclass
class SpatialValidationResult:
    """Result of spatial validation"""
    valid: bool
    errors: List[SpatialIssue] = field(default_factory=list)
    warnings: List[SpatialIssue] = field(default_factory=list)
    
    @property
    def has_issues(self) -> bool:
        """Check if there are any errors or warnings"""
        return len(self.errors) > 0 or len(self.warnings) > 0


class SpatialValidator:
    """
    Validates spatial layout of Manim objects.
    
    Checks:
    - Objects with hardcoded coordinates within screen bounds
    - Multiple Text objects at the same position (overlap)
    - Objects positioned too close together
    - Very large objects that might overflow
    """
    
    # Screen boundaries (approximate, with safety margin)
    X_MIN = -6.5
    X_MAX = 6.5
    Y_MIN = -3.5
    Y_MAX = 3.5
    
    # Minimum spacing between objects
    MIN_SPACING = 0.5
    
    # Maximum safe font size to width ratio
    CHARS_PER_UNIT = 10  # Approximate characters per screen unit at default font size
    
    def validate(self, code: str) -> SpatialValidationResult:
        """
        Validate spatial layout of Manim code.
        
        Args:
            code: Manim Python code to validate
            
        Returns:
            SpatialValidationResult with spatial issues
        """
        errors = []
        warnings = []
        
        # Extract all positioned objects
        positioned_objects = self._extract_positioned_objects(code)
        
        # Check for out-of-bounds coordinates
        out_of_bounds = self._check_bounds(positioned_objects)
        errors.extend(out_of_bounds)
        
        # Check for overlapping objects
        overlaps = self._check_overlaps(positioned_objects)
        warnings.extend(overlaps)
        
        # Check for oversized text
        oversized = self._check_text_overflow(code)
        warnings.extend(oversized)
        
        # Check for multiple objects at same position without proper spacing
        same_position = self._check_same_position(code)
        warnings.extend(same_position)
        
        return SpatialValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def _extract_positioned_objects(self, code: str) -> List[Dict]:
        """Extract objects with explicit coordinate positioning"""
        objects = []
        lines = code.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            # Look for .move_to([x, y, z]) or .move_to([x, y])
            move_to_match = re.search(r'\.move_to\(\[([+-]?\d+\.?\d*),\s*([+-]?\d+\.?\d*)(?:,\s*[+-]?\d+\.?\d*)?\]\)', line)
            if move_to_match:
                x, y = float(move_to_match.group(1)), float(move_to_match.group(2))
                objects.append({
                    'line': line_num,
                    'x': x,
                    'y': y,
                    'method': 'move_to',
                    'code': line.strip()
                })
            
            # Look for .shift([x, y, z]) or .shift([x, y])
            shift_match = re.search(r'\.shift\(\[([+-]?\d+\.?\d*),\s*([+-]?\d+\.?\d*)(?:,\s*[+-]?\d+\.?\d*)?\]\)', line)
            if shift_match:
                x, y = float(shift_match.group(1)), float(shift_match.group(2))
                objects.append({
                    'line': line_num,
                    'x': x,
                    'y': y,
                    'method': 'shift',
                    'code': line.strip()
                })
        
        return objects
    
    def _check_bounds(self, objects: List[Dict]) -> List[SpatialIssue]:
        """Check if coordinates are within screen bounds"""
        issues = []
        
        for obj in objects:
            x, y = obj['x'], obj['y']
            
            if x < self.X_MIN or x > self.X_MAX:
                issues.append(SpatialIssue(
                    line_number=obj['line'],
                    severity='error',
                    message=f"X coordinate {x} is out of screen bounds ({self.X_MIN} to {self.X_MAX})",
                    code_snippet=obj['code']
                ))
            
            if y < self.Y_MIN or y > self.Y_MAX:
                issues.append(SpatialIssue(
                    line_number=obj['line'],
                    severity='error',
                    message=f"Y coordinate {y} is out of screen bounds ({self.Y_MIN} to {self.Y_MAX})",
                    code_snippet=obj['code']
                ))
        
        return issues
    
    def _check_overlaps(self, objects: List[Dict]) -> List[SpatialIssue]:
        """Check for objects positioned too close together"""
        issues = []
        
        for i, obj1 in enumerate(objects):
            for obj2 in objects[i+1:]:
                distance = ((obj1['x'] - obj2['x'])**2 + (obj1['y'] - obj2['y'])**2)**0.5
                
                if distance < self.MIN_SPACING:
                    issues.append(SpatialIssue(
                        line_number=obj1['line'],
                        severity='warning',
                        message=f"Object at ({obj1['x']}, {obj1['y']}) is very close to object at ({obj2['x']}, {obj2['y']}) - distance: {distance:.2f} (min: {self.MIN_SPACING})",
                        code_snippet=f"{obj1['code']} | {obj2['code']}"
                    ))
        
        return issues
    
    def _check_text_overflow(self, code: str) -> List[SpatialIssue]:
        """Check for text that might overflow screen bounds"""
        issues = []
        lines = code.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            # Find Text objects
            text_match = re.search(r'Text\(["\']([^"\']+)["\'](?:.*font_size\s*=\s*(\d+))?', line)
            if text_match:
                text_content = text_match.group(1)
                font_size = int(text_match.group(2)) if text_match.group(2) else 24
                
                # Estimate width (rough approximation)
                # Font size 24 ≈ 1 unit width per 10 characters
                scale_factor = font_size / 24.0
                estimated_width = len(text_content) / (self.CHARS_PER_UNIT / scale_factor)
                
                # Check if text is centered (default) and too wide
                if estimated_width > 12:  # More than screen width
                    issues.append(SpatialIssue(
                        line_number=line_num,
                        severity='warning',
                        message=f"Text might overflow: '{text_content[:30]}...' estimated width {estimated_width:.1f} units (screen width ~13 units)",
                        code_snippet=line.strip()
                    ))
        
        return issues
    
    def _check_same_position(self, code: str) -> List[SpatialIssue]:
        """Check for multiple objects at the exact same position"""
        issues = []
        lines = code.split('\n')
        
        # Track positions of Text objects that don't have explicit positioning
        unpositioned_texts = []
        
        for line_num, line in enumerate(lines, 1):
            # Find Text objects without positioning
            if 'Text(' in line and 'move_to' not in line and 'shift' not in line and 'next_to' not in line and 'to_edge' not in line:
                text_match = re.search(r'Text\(["\']([^"\']+)["\']', line)
                if text_match:
                    unpositioned_texts.append({
                        'line': line_num,
                        'text': text_match.group(1)[:30],
                        'code': line.strip()
                    })
        
        # If multiple unpositioned Text objects, warn about potential overlap
        if len(unpositioned_texts) > 1:
            lines_list = [str(t['line']) for t in unpositioned_texts]
            issues.append(SpatialIssue(
                line_number=unpositioned_texts[0]['line'],
                severity='warning',
                message=f"Multiple unpositioned Text objects (lines {', '.join(lines_list)}) - they will overlap at screen center. Use .move_to() or .next_to() to position them.",
                code_snippet=f"Found {len(unpositioned_texts)} unpositioned Text objects"
            ))
        
        return issues


def format_spatial_issues(result: SpatialValidationResult) -> str:
    """
    Format spatial validation issues for display.
    
    Args:
        result: Validation result
        
    Returns:
        Formatted string with all issues
    """
    if not result.has_issues:
        return "No spatial layout issues found"
    
    output = []
    
    if result.errors:
        output.append("ERRORS:")
        for error in result.errors:
            output.append(f"  Line {error.line_number}: {error.message}")
            output.append(f"    Code: {error.code_snippet}")
    
    if result.warnings:
        output.append("\nWARNINGS:")
        for warning in result.warnings:
            output.append(f"  Line {warning.line_number}: {warning.message}")
            output.append(f"    Code: {warning.code_snippet}")
    
    return "\n".join(output)
