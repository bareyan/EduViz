
from manim import *
import sys

class VerifyCleanTheme(Scene):
    def construct(self):
        # Simulate the injection code from config.py
        self.camera.background_color = "#FFFFFF"
        VMobject.set_default(color="#111111")
        # Override geometry defaults that ignore VMobject default
        Circle.set_default(color="#111111")
        Square.set_default(color="#111111")
        Triangle.set_default(color="#111111")
        Dot.set_default(color="#111111")
        Line.set_default(color="#111111")
        Arrow.set_default(color="#111111")
        NumberPlane.set_default(axis_config={"color": "#111111"})
        Axes.set_default(axis_config={"color": "#111111"})
        
        # Create objects without explicit color to test defaults
        msg = f"Testing VMobject.set_default(color='#111111')"
        print(msg)
        
        # 1. Basic Line (Should be black)
        l = Line(LEFT, RIGHT)
        
        # 2. Circle (Should be black)
        c = Circle()
        
        # 3. Axes (Should be black)
        ax = Axes()
        
        # Check colors
        # Manim colors are arrays, convert to hex or just print
        print(f"Line color: {l.get_color()}")
        print(f"Circle color: {c.get_color()}")
        # Axes is a group. Check distinct colors in it.
        ax_colors = {m.get_color() for m in ax.get_family()}
        print(f"Axes sub-colors: {ax_colors}")
        
        # We expect #111111 (Hex) -> Manim Color
        # Let's just create a control object
        control = VMobject(color="#111111")
        target_color = control.get_color()
        
        if l.get_color() != target_color:
            print("FAIL: Line does not match target color")
            # sys.exit(1) # Don't crash, just report
        else:
            print("PASS: Line matches default")

        if c.get_color() != target_color:
            print("FAIL: Circle does not match target color")
        else:
            print("PASS: Circle matches default")
            
        # For Axes, it might be more complex since it has tips etc.
        # But if NONE of them match, it's a fail.
        if target_color not in ax_colors:
             print("WARNING: Axes does not contain default color elements!")
             print(f"Target: {target_color}")
             print(f"Found: {ax_colors}")
        else:
             print("PASS: Axes contains default color elements")

        self.add(l, c, ax)
