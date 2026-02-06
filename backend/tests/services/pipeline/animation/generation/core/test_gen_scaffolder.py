
from app.services.pipeline.animation.generation.core.scaffolder import ManimScaffolder

def test_scaffolder_assemble():
    scaffolder = ManimScaffolder("MyScene")
    snippet = """
    c = Circle()
    self.play(Create(c))
    """
    full_code = scaffolder.assemble(snippet)
    
    assert "class MyScene(Scene):" in full_code
    assert "def construct(self):" in full_code
    assert "from manim import *" in full_code
    assert "c = Circle()" in full_code

def test_scaffolder_auto_imports():
    scaffolder = ManimScaffolder()
    # Snippet uses numpy
    snippet = "val = np.array([1, 2])"
    full_code = scaffolder.assemble(snippet)
    
    assert "import numpy as np" in full_code

def test_scaffolder_translate_error():
    scaffolder = ManimScaffolder()
    # Dummy assemble to set header_lines
    scaffolder.assemble("pass")
    
    line_in_full_file = scaffolder.header_lines + 1
    msg, line = scaffolder.translate_error(f"Error at line {line_in_full_file}", line_in_full_file)
    
    assert line == 1
    assert "line 1" in msg
