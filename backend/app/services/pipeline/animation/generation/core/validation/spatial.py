"""
Spatial Check Injector
Injects AST-based checks into Manim Scene code to enforce safety and spatial constraints.
"""
import ast
import textwrap
import logging
from app.core import get_logger

logger = get_logger(__name__, component="spatial_injector")

# The code string to inject into the Scene class
# This method runs continuously via monkey-patching
INJECTED_METHOD = """
def _perform_spatial_checks(self):
    \"\"\"
    Injected safety check for visual constraints.
    Raises specific exceptions if constraints are violated.
    \"\"\"
    import sys
    
    # 1. SETUP: CHECK_INTERVAL
    SCREEN_X_LIMIT = 7.1
    SCREEN_Y_LIMIT = 4.0
    
    # Error accumulator
    spatial_errors = []

    # Helper: Flatten mobjects in draw order
    def get_flat_mobjects(mobjects):
        flat = []
        for m in mobjects:
            if m is None: continue
            # Add self
            flat.append(m)
            # Recurse if group (Manim's submobjects are usually drawing order)
            if hasattr(m, 'submobjects') and m.submobjects:
                flat.extend(get_flat_mobjects(m.submobjects))
        return flat

    # Helper for visibility
    def is_effectively_visible(m):
        try:
            # Check opacity
            if hasattr(m, 'get_fill_opacity'):
                val = m.get_fill_opacity()
                if val is not None and val == 0:
                    if hasattr(m, 'get_stroke_opacity'):
                        s_val = m.get_stroke_opacity()
                        if s_val is not None and s_val > 0:
                            return True
                    return False 
            return True
        except:
            return True

    # Helper for overlap (AABB)
    def is_overlapping(m1, m2):
        try:
            c1 = m1.get_center(); w1, h1 = m1.width, m1.height
            c2 = m2.get_center(); w2, h2 = m2.width, m2.height
            return (abs(c1[0] - c2[0]) * 2 < (w1 + w2)) and (abs(c1[1] - c2[1]) * 2 < (h1 + h2))
        except: return False

    # 1. FLATTEN SCENE
    # Limit total objects checked to prevent performance kill on massive networks
    # We only check first ~500 objects if scene is huge
    all_ordered = get_flat_mobjects(self.mobjects)
    if len(all_ordered) > 500:
        # Heuristic: Check specifically Texts and bigger objects, skip tiny dots?
        # For now, just slice (risky but necessary for performance)
        # Or randomly sample?
        # Let's keep it simple: Validate all for correctness, user complains if slow.
        pass

    # 2. BOUNDS CHECK
    for m in all_ordered:
        # Only check "leaf" or substantial objects, not groups themselves if they are just containers
        # But groups have bounding boxes too.
        # Bounds check is cheap.
        if not hasattr(m, 'get_center') or not hasattr(m, 'width'): continue
        if not is_effectively_visible(m): continue
        
        if m.width > 0.1 and m.height > 0.1: 
            x, y, z = m.get_center()
            w, h = m.width, m.height
            left, right = x - w/2, x + w/2
            top, bottom = y + h/2, y - h/2
            
            if (left < -SCREEN_X_LIMIT or right > SCREEN_X_LIMIT or 
                bottom < -SCREEN_Y_LIMIT or top > SCREEN_Y_LIMIT):
                spatial_errors.append(f"Spatial Error: Object '{type(m).__name__}' is out of bounds (X/Y limits). Center: ({x:.2f}, {y:.2f}).")

    # 3. OVERLAP CHECKS
    # Filter texts and objects from flat list (preserving order)
    texts_with_idx = []
    objects_with_idx = []
    
    for idx, m in enumerate(all_ordered):
        if not hasattr(m, 'get_center'): continue
        if not is_effectively_visible(m): continue
        
        is_text = "Text" in type(m).__name__ or hasattr(m, "text")
        if is_text:
            texts_with_idx.append((idx, m))
        elif isinstance(m, VMobject):
            objects_with_idx.append((idx, m))

    # A. Text on Text
    for i, (idx1, t1) in enumerate(texts_with_idx):
        for (idx2, t2) in texts_with_idx[i+1:]:
            if t1 is t2: continue
            if is_overlapping(t1, t2):
                txt1 = getattr(t1, 'text', str(t1))
                txt2 = getattr(t2, 'text', str(t2))
                # Truncate to 50 chars for readability
                txt1_display = txt1[:50] if len(txt1) > 50 else txt1
                txt2_display = txt2[:50] if len(txt2) > 50 else txt2
                spatial_errors.append(f"Text overlap: '{txt1_display}' overlaps '{txt2_display}'")

    # B. Object on Text (Z-Order Aware)
    # Only error if Object is drew AFTER Text (Higher Index) AND overlaps
    for (t_idx, t) in texts_with_idx:
        for (o_idx, o) in objects_with_idx:
            # Semantic check:
            # If Object is ON TOP (o_idx > t_idx) -> Potential obscuration
            if o_idx > t_idx:
                if is_overlapping(t, o):
                    # Filter out tiny overlaps or specific shapes?
                    if o.width > SCREEN_X_LIMIT: continue # Background rect
                    
                    # CRITICAL: Ignore if object is part of the text (e.g. a letter)
                    # or if text is part of the object (e.g. label on button)
                    is_related = False
                    try:
                        # Check if o is in t's family (common for Text -> VMobjectFromSVGPath)
                        if hasattr(t, 'submobjects') and o in t.get_family(): is_related = True
                        # Check if t is in o's family (Text on ButtonGroup)
                        elif hasattr(o, 'submobjects') and t in o.get_family(): is_related = True
                    except: pass
                    
                    if is_related: continue

                    txt = getattr(t, 'text', str(t))
                    txt_display = txt[:50] if len(txt) > 50 else txt
                    obj_name = type(o).__name__
                    
                    # Get object details for context
                    try:
                        o_center = o.get_center()
                        o_pos = f"at ({o_center[0]:.1f}, {o_center[1]:.1f})"
                        o_size = f"{o.width:.1f}×{o.height:.1f}"
                    except:
                        o_pos = "position unknown"
                        o_size = "size unknown"
                    
                    # Try to get color for additional context
                    color_info = ""
                    try:
                        if hasattr(o, 'get_color'):
                            color = o.get_color()
                            if color: color_info = f", color={color}"
                        elif hasattr(o, 'get_fill_color'):
                            color = o.get_fill_color()
                            if color: color_info = f", color={color}"
                    except: pass
                    
                    # Simplify common verbose names
                    if obj_name == "VMobjectFromSVGPath":
                        obj_name = "SVGShape"
                    
                    spatial_errors.append(f"{obj_name} ({o_size} {o_pos}{color_info}) covers text '{txt_display}'")

    # Report
    if spatial_errors:
             unique_errors = sorted(list(set(spatial_errors)))
             error_count = len(unique_errors)
             # Format with line breaks for readability if multiple errors
             if error_count == 1:
                 joined_errors = unique_errors[0]
             else:
                 joined_errors = "\n  • " + "\n  • ".join(unique_errors)
             # Truncate if too long
             if len(joined_errors) > 800: 
                 joined_errors = joined_errors[:800] + "\n  ..."
             sys.exit(f"Spatial validation failed ({error_count} issues):{joined_errors}")
"""

INJECTED_SETUP = """
# --- INJECTED SETUP: Continuous Validation ---
# Monkey-patch play and wait to run checks
self._original_play = self.play
self._original_wait = self.wait

def _monitored_play(*args, **kwargs):
    self._perform_spatial_checks()
    self._original_play(*args, **kwargs)
    self._perform_spatial_checks()
    
def _monitored_wait(*args, **kwargs):
    self._perform_spatial_checks()
    self._original_wait(*args, **kwargs)
    self._perform_spatial_checks()
    
self.play = _monitored_play
self.wait = _monitored_wait
# ---------------------------------------------
"""

class SpatialCheckInjector:
    """
    Injects spatial checks into Manim code using AST.
    """
    def inject(self, code: str) -> str:
        try:
            tree = ast.parse(code)
            
            # Find the Scene class
            scene_class = None
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    # Check if inherits from "Scene"
                    # We look for a base class named 'Scene'
                    is_scene = any(base.id == 'Scene' for base in node.bases if isinstance(base, ast.Name))
                    if is_scene:
                        scene_class = node
                        break
            
            if not scene_class:
                # Fallback: Just pick the first class if no "Scene" detected (e.g. specialized subclass)
                first_class = next((n for n in tree.body if isinstance(n, ast.ClassDef)), None)
                if first_class:
                    scene_class = first_class
                else:
                    return code # No classes at all

            # 1. Add _perform_spatial_checks method to class
            method_tree = ast.parse(textwrap.dedent(INJECTED_METHOD))
            check_func = method_tree.body[0]
            scene_class.body.append(check_func)
            
            # 2. Add setup logic to start of construct()
            construct_method = None
            for node in scene_class.body:
                if isinstance(node, ast.FunctionDef) and node.name == 'construct':
                    construct_method = node
                    break
                    
            if construct_method:
                setup_tree = ast.parse(textwrap.dedent(INJECTED_SETUP))
                
                # Insert at logical beginning (skipping docstring)
                insert_idx = 0
                if (construct_method.body and 
                    isinstance(construct_method.body[0], ast.Expr) and 
                    isinstance(construct_method.body[0].value, ast.Constant) and 
                    isinstance(construct_method.body[0].value.value, str)):
                    insert_idx = 1
                
                # Prepend setup statements
                construct_method.body[insert_idx:insert_idx] = setup_tree.body
                
                # 3. Append call to End of construct (to catch static setup)
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
                construct_method.body.append(check_call)
            
            # Unparse back to string
            if hasattr(ast, 'unparse'):
                return ast.unparse(tree)
            else:
                return code # Fallback

        except Exception as e:
            logger.error(f"Failed to inject spatial checks: {e}")
            return code
