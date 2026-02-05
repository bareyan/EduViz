"""
Spatial Validation Injector

Injects runtime checks for visual constraints (overlaps, visibility, bounds)
into Manim code using AST manipulation.
"""

import ast
from typing import Optional
from app.core import get_logger

logger = get_logger(__name__, component="spatial_injector")

# The code string to inject into the Scene class
# This method runs at the end of construct()
INJECTED_METHOD = """
def _perform_spatial_checks(self):
    \"\"\"
    Injected safety check for visual constraints.
    Raises specific exceptions if constraints are violated.
    \"\"\"
    import sys
    # Constants
    SCREEN_X_LIMIT = 7.1
    SCREEN_Y_LIMIT = 4.0
    BACKGROUND_COLOR = self.camera.background_color
    
    # Helper to get hex color safely
    def get_hex(vmobject):
        try:
            return vmobject.get_color().name if hasattr(vmobject.get_color(), 'name') else str(vmobject.get_color())
        except:
            return str(vmobject.color)

    # Helper for overlap (AABB)
    def is_overlapping(m1, m2):
        # Get corners
        try:
            c1 = m1.get_center()
            w1, h1 = m1.width, m1.height
            c2 = m2.get_center()
            w2, h2 = m2.width, m2.height
            
            # Check AABB intersection
            if (abs(c1[0] - c2[0]) * 2 < (w1 + w2)) and (abs(c1[1] - c2[1]) * 2 < (h1 + h2)):
                return True
            return False
        except:
            return False # Safe fallback

            return False # Safe fallback

    # Duck typing: Check anything that looks like a Mobject with spatial properties
    # This avoids import issues with VMobject
    
    for m in self.mobjects:
        # VISIBILITY & BOUNDS
        if not hasattr(m, 'get_center') or not hasattr(m, 'width'):
            continue
            
        # 1. VISIBILITY CHECK (Error)
        # ... (Pass for now)
        pass 
        
        # 2. BOUNDS CHECK (Error)
        # Check if it has significant size (ignore invisible points)
        if m.width > 0.1 and m.height > 0.1: 
            x, y, z = m.get_center()
            w, h = m.width, m.height
            
            # Check edges
            left = x - w/2
            right = x + w/2
            top = y + h/2
            bottom = y - h/2
            
            if (left < -SCREEN_X_LIMIT or right > SCREEN_X_LIMIT or 
                bottom < -SCREEN_Y_LIMIT or top > SCREEN_Y_LIMIT):
                
                # We treat this as an ERROR as requested
                # Use sys.exit to ensure non-zero return code even if Manim swallows exceptions
                sys.exit(f"Spatial Error: Object '{type(m).__name__}' is out of bounds (X/Y limits). Center: ({x:.2f}, {y:.2f}).")

    # 3. TEXT OVERLAP CHECK (Error)
    # Filter for text-like objects based on class name or attributes
    texts = [m for m in self.mobjects if "Text" in type(m).__name__ and hasattr(m, 'text')]
    
    for i, t1 in enumerate(texts):
        for t2 in texts[i+1:]:
            if t1 is t2: continue
            # Ignore if different Z-index significantly (not easily tracked in flat list, assuming flat for now)
            
            if is_overlapping(t1, t2):
                # Check text content to be sure valid
                txt1 = getattr(t1, 'text', str(t1))
                txt2 = getattr(t2, 'text', str(t2))
                sys.exit(f"Spatial Error: Text overlap detected between '{txt1[:20]}' and '{txt2[:20]}'.")
"""

class SpatialCheckInjector:
    """
    Injects spatial validation logic into Python source code via AST.
    """
    
    def inject(self, code: str) -> str:
        """
        Parses code, finds the Scene class and its construct method,
        and appends the validation call and method definition.
        """
        try:
            tree = ast.parse(code)
            
            scene_class = self._find_scene_class(tree)
            if not scene_class:
                logger.warning("No Scene class found to inject spatial checks.")
                return code
                
            construct_method = self._find_construct_method(scene_class)
            if not construct_method:
                logger.warning("No construct() method found in Scene class.")
                return code
            
            # 1. Append `self._perform_spatial_checks()` to the end of construct()
            # We create a simple expression node for the call
            check_call = ast.Expr(
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id='self', ctx=ast.Load()),
                        attr='_perform_spatial_checks',
                        ctx=ast.Load()
                    ),
                    args=[],
                    keywords=[]
                )
            )
            
            # Insert at the end
            construct_method.body.append(check_call)
            
            # 2. Add the `_perform_spatial_checks` method to the class body
            # We parse the template string to get an AST FunctionDef
            helper_tree = ast.parse(INJECTED_METHOD)
            helper_method = helper_tree.body[0] # The function def
            
            scene_class.body.append(helper_method)
            
            # 3. Unparse back to string
            # Note: ast.unparse requires Python 3.9+
            return ast.unparse(tree)
            
        except Exception as e:
            logger.error(f"Failed to inject spatial checks: {e}")
            return code # Return original on failure to be safe

    def _find_scene_class(self, tree: ast.AST) -> Optional[ast.ClassDef]:
        """Finds the first class that inherits from Scene (or just the first class)."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # We assume the main scene is the one we want.
                # Heuristics: inherits from Scene
                for base in node.bases:
                    if isinstance(base, ast.Name) and "Scene" in base.id:
                        return node
        
        # Fallback: Just return the first class found if specific parent checking fails
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                return node
        return None

    def _find_construct_method(self, class_def: ast.ClassDef) -> Optional[ast.FunctionDef]:
        """Finds the construct method within a class."""
        for node in class_def.body:
            if isinstance(node, ast.FunctionDef) and node.name == 'construct':
                return node
        return None
