from manim import *
import sys

def check_visibility():
    txt = Text("Test")
    print(f"Initial: fill={txt.get_fill_opacity()}, stroke={txt.get_stroke_opacity()}")
    
    # Simulate FadeOut
    txt.set_opacity(0)
    print(f"After set_opacity(0): fill={txt.get_fill_opacity()}, stroke={txt.get_stroke_opacity()}")
    
    # Check submobjects
    if txt.submobjects:
        sub = txt.submobjects[0]
        print(f"Submobject: fill={sub.get_fill_opacity()}, stroke={sub.get_stroke_opacity()}")

if __name__ == "__main__":
    check_visibility()
