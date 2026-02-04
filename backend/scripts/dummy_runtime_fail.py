from manim import *

class TestScene(Scene):
    def construct(self):
        # Runtime error: 1 / 0
        x = 1 / 0 
        c = Circle()
        self.play(Create(c))
