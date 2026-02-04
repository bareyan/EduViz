import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parents[1])) # Add backend root

from app.services.pipeline.animation.generation.core.validation.static import StaticValidator
import asyncio

bad_code = """
from manim import *

class TestScene(Scene):
    def construct(self):
        surface_axes = Axes(x_range=[-2, 2], y_range=[-1, 3])
        # This caused the error: TypeError: Mobject.__getattr__.<locals>.getter() ...
        bowl = surface_axes.get_graph(lambda x: 0.5 * x**2, color=TEAL) 
        self.add(surface_axes, bowl)
"""

async def check():
    val = StaticValidator()
    result = await val.validate(bad_code)
    print(f"Valid: {result.valid}")
    for err in result.errors:
        print(f"Error: {err}")

if __name__ == "__main__":
    asyncio.run(check())
