"""
Manim Scene Builder - Creates 3Blue1Brown style animations
"""

import os
import asyncio
import tempfile
import textwrap
from typing import List, Dict, Any, Optional

# Animation configuration
MANIM_CONFIG = {
    "background_color": "#1a1a2e",  # Dark blue/black like 3b1b
    "text_color": "#ffffff",
    "accent_color": "#3b82f6",  # Blue accent
    "secondary_color": "#22c55e",  # Green
    "tertiary_color": "#f59e0b",  # Orange
    "quality": "production_quality",  # or "low_quality" for faster renders
}


class ManimSceneBuilder:
    """Builds Manim scenes from animation specifications"""
    
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
    
    async def build_scene(
        self,
        animations: List[Dict[str, Any]],
        output_path: str,
        target_duration: float,
        style: str = "3b1b"
    ):
        """Build a complete Manim scene from animation specs"""
        
        # Generate Python code for the Manim scene
        scene_code = self._generate_scene_code(animations, target_duration, style)
        
        # Write scene to temporary file
        scene_file = os.path.join(self.temp_dir, "scene.py")
        with open(scene_file, "w") as f:
            f.write(scene_code)
        
        # Render with Manim
        await self._render_scene(scene_file, output_path)
    
    def _generate_scene_code(
        self,
        animations: List[Dict[str, Any]],
        target_duration: float,
        style: str
    ) -> str:
        """Generate Manim Python code for the scene"""
        
        # Calculate timing for each animation
        num_animations = max(len(animations), 1)
        time_per_animation = target_duration / num_animations
        
        # Build animation code
        animation_code = self._build_animation_code(animations, time_per_animation)
        
        scene_code = f'''#!/usr/bin/env python3
"""
Auto-generated Manim scene for educational video
"""

from manim import *
import numpy as np

# Configure style
config.background_color = "{MANIM_CONFIG['background_color']}"

class GeneratedScene(Scene):
    """Generated educational scene"""
    
    def construct(self):
        # Set up colors
        self.accent = "{MANIM_CONFIG['accent_color']}"
        self.secondary = "{MANIM_CONFIG['secondary_color']}"
        self.tertiary = "{MANIM_CONFIG['tertiary_color']}"
        
        # Run animations
{textwrap.indent(animation_code, "        ")}
        
        # End with a pause
        self.wait(0.5)
'''
        
        return scene_code
    
    def _build_animation_code(
        self,
        animations: List[Dict[str, Any]],
        time_per_animation: float
    ) -> str:
        """Build the animation code section"""
        
        if not animations:
            return "self.wait(1)"
        
        code_lines = []
        
        for i, anim in enumerate(animations):
            anim_type = anim.get("type", "text")
            code = self._generate_single_animation(anim, time_per_animation, i)
            code_lines.append(f"# Animation {i + 1}: {anim_type}")
            code_lines.append(code)
            code_lines.append("")
        
        return "\n".join(code_lines)
    
    def _generate_single_animation(
        self,
        anim: Dict[str, Any],
        duration: float,
        index: int
    ) -> str:
        """Generate code for a single animation"""
        
        anim_type = anim.get("type", "text")
        
        generators = {
            "text": self._gen_text_animation,
            "equation": self._gen_equation_animation,
            "graph": self._gen_graph_animation,
            "shape": self._gen_shape_animation,
            "numberline": self._gen_numberline_animation,
            "vector": self._gen_vector_animation,
            "matrix": self._gen_matrix_animation,
            "diagram": self._gen_diagram_animation,
            "code": self._gen_code_animation,
        }
        
        generator = generators.get(anim_type, self._gen_text_animation)
        return generator(anim, duration, index)
    
    def _gen_text_animation(self, anim: Dict, duration: float, idx: int) -> str:
        """Generate text animation"""
        
        content = anim.get("content", "").replace('"', '\\"')
        style = anim.get("style", "normal")
        
        if style == "title":
            return f'''
text_{idx} = Text("{content}", font_size=72, color=WHITE)
self.play(Write(text_{idx}), run_time={min(duration * 0.6, 2)})
self.wait({max(duration * 0.4, 0.5)})
self.play(FadeOut(text_{idx}), run_time=0.5)
'''
        elif style == "subtitle":
            return f'''
text_{idx} = Text("{content}", font_size=48, color=GRAY_A)
self.play(FadeIn(text_{idx}), run_time={min(duration * 0.5, 1)})
self.wait({max(duration * 0.5, 0.5)})
self.play(FadeOut(text_{idx}), run_time=0.5)
'''
        else:
            return f'''
text_{idx} = Text("{content}", font_size=36, color=WHITE)
self.play(Write(text_{idx}), run_time={min(duration * 0.7, 2)})
self.wait({max(duration * 0.3, 0.5)})
'''
    
    def _gen_equation_animation(self, anim: Dict, duration: float, idx: int) -> str:
        """Generate LaTeX equation animation"""
        
        latex = anim.get("latex", "x = y").replace("\\", "\\\\")
        animation_type = anim.get("animation", "write")
        
        if animation_type == "transform":
            return f'''
eq_{idx} = MathTex(r"{latex}", font_size=56)
self.play(Write(eq_{idx}), run_time={min(duration * 0.6, 2)})
self.wait({max(duration * 0.4, 0.5)})
'''
        else:
            return f'''
eq_{idx} = MathTex(r"{latex}", font_size=56)
eq_{idx}.set_color_by_gradient(BLUE, GREEN)
self.play(Write(eq_{idx}), run_time={min(duration * 0.6, 2)})
self.wait({max(duration * 0.4, 0.5)})
'''
    
    def _gen_graph_animation(self, anim: Dict, duration: float, idx: int) -> str:
        """Generate function graph animation"""
        
        func = anim.get("function", "x**2")
        x_range = anim.get("range", [-3, 3])
        
        # Sanitize function for Python eval
        safe_func = func.replace("^", "**").replace("sin", "np.sin").replace("cos", "np.cos")
        safe_func = safe_func.replace("tan", "np.tan").replace("exp", "np.exp").replace("log", "np.log")
        
        return f'''
axes_{idx} = Axes(
    x_range=[{x_range[0]}, {x_range[1]}, 1],
    y_range=[-5, 5, 1],
    x_length=10,
    y_length=6,
    axis_config={{"color": BLUE_D}},
    tips=False
)
axes_labels_{idx} = axes_{idx}.get_axis_labels(x_label="x", y_label="y")

graph_{idx} = axes_{idx}.plot(lambda x: {safe_func}, color=YELLOW)

self.play(Create(axes_{idx}), Write(axes_labels_{idx}), run_time={min(duration * 0.3, 1)})
self.play(Create(graph_{idx}), run_time={min(duration * 0.5, 2)})
self.wait({max(duration * 0.2, 0.5)})
self.play(FadeOut(axes_{idx}, axes_labels_{idx}, graph_{idx}), run_time=0.5)
'''
    
    def _gen_shape_animation(self, anim: Dict, duration: float, idx: int) -> str:
        """Generate geometric shape animation"""
        
        shape = anim.get("shape", "circle")
        action = anim.get("action", "create")
        
        shape_code = {
            "circle": f"Circle(radius=2, color=BLUE)",
            "square": f"Square(side_length=3, color=GREEN)",
            "triangle": f"Triangle(color=YELLOW)",
            "rectangle": f"Rectangle(width=4, height=2, color=RED)",
        }.get(shape, "Circle(radius=2, color=BLUE)")
        
        if action == "transform_to_square":
            return f'''
shape_{idx} = {shape_code}
target_{idx} = Square(side_length=3, color=GREEN)
self.play(Create(shape_{idx}), run_time={min(duration * 0.3, 1)})
self.play(Transform(shape_{idx}, target_{idx}), run_time={min(duration * 0.5, 2)})
self.wait({max(duration * 0.2, 0.5)})
self.play(FadeOut(shape_{idx}), run_time=0.5)
'''
        else:
            return f'''
shape_{idx} = {shape_code}
self.play(Create(shape_{idx}), run_time={min(duration * 0.6, 2)})
self.wait({max(duration * 0.4, 0.5)})
self.play(FadeOut(shape_{idx}), run_time=0.5)
'''
    
    def _gen_numberline_animation(self, anim: Dict, duration: float, idx: int) -> str:
        """Generate number line animation"""
        
        range_vals = anim.get("range", [-5, 5])
        highlight = anim.get("highlight", [])
        
        code = f'''
line_{idx} = NumberLine(
    x_range=[{range_vals[0]}, {range_vals[1]}, 1],
    length=10,
    color=BLUE,
    include_numbers=True,
    label_direction=DOWN
)
self.play(Create(line_{idx}), run_time={min(duration * 0.4, 1.5)})
'''
        
        if highlight and len(highlight) >= 2:
            code += f'''
dot_start_{idx} = Dot(line_{idx}.n2p({highlight[0]}), color=YELLOW)
dot_end_{idx} = Dot(line_{idx}.n2p({highlight[1]}), color=YELLOW)
brace_{idx} = Brace(Line(line_{idx}.n2p({highlight[0]}), line_{idx}.n2p({highlight[1]})), UP)
self.play(Create(dot_start_{idx}), Create(dot_end_{idx}), run_time=0.5)
self.play(Create(brace_{idx}), run_time=0.5)
self.wait({max(duration * 0.3, 0.5)})
self.play(FadeOut(line_{idx}, dot_start_{idx}, dot_end_{idx}, brace_{idx}), run_time=0.5)
'''
        else:
            code += f'''
self.wait({max(duration * 0.4, 0.5)})
self.play(FadeOut(line_{idx}), run_time=0.5)
'''
        
        return code
    
    def _gen_vector_animation(self, anim: Dict, duration: float, idx: int) -> str:
        """Generate vector animation"""
        
        coords = anim.get("coords", [2, 1])
        
        return f'''
plane_{idx} = NumberPlane(
    x_range=[-4, 4, 1],
    y_range=[-3, 3, 1],
    background_line_style={{"stroke_opacity": 0.4}}
)
vector_{idx} = Arrow(ORIGIN, [{coords[0]}, {coords[1]}, 0], buff=0, color=YELLOW)
label_{idx} = MathTex(r"\\vec{{v}}", color=YELLOW).next_to(vector_{idx}, UP)

self.play(Create(plane_{idx}), run_time={min(duration * 0.3, 1)})
self.play(GrowArrow(vector_{idx}), Write(label_{idx}), run_time={min(duration * 0.4, 1.5)})
self.wait({max(duration * 0.3, 0.5)})
self.play(FadeOut(plane_{idx}, vector_{idx}, label_{idx}), run_time=0.5)
'''
    
    def _gen_matrix_animation(self, anim: Dict, duration: float, idx: int) -> str:
        """Generate matrix animation"""
        
        matrix = anim.get("matrix", [[1, 2], [3, 4]])
        matrix_str = str(matrix)
        
        return f'''
matrix_{idx} = Matrix({matrix_str}, left_bracket="[", right_bracket="]")
matrix_{idx}.set_color(BLUE)
self.play(Write(matrix_{idx}), run_time={min(duration * 0.6, 2)})
self.wait({max(duration * 0.4, 0.5)})
self.play(FadeOut(matrix_{idx}), run_time=0.5)
'''
    
    def _gen_diagram_animation(self, anim: Dict, duration: float, idx: int) -> str:
        """Generate a diagram (generic visual)"""
        
        # Create a simple diagram with shapes
        return f'''
# Diagram with connected shapes
shapes_{idx} = VGroup(
    Circle(radius=0.5, color=BLUE).shift(LEFT * 3),
    Circle(radius=0.5, color=GREEN).shift(RIGHT * 3),
    Circle(radius=0.5, color=YELLOW).shift(UP * 2)
)
arrows_{idx} = VGroup(
    Arrow(shapes_{idx}[0].get_right(), shapes_{idx}[1].get_left(), color=WHITE),
    Arrow(shapes_{idx}[2].get_bottom(), shapes_{idx}[0].get_top() + RIGHT * 0.3, color=WHITE),
    Arrow(shapes_{idx}[2].get_bottom(), shapes_{idx}[1].get_top() + LEFT * 0.3, color=WHITE)
)

self.play(Create(shapes_{idx}), run_time={min(duration * 0.4, 1.5)})
self.play(Create(arrows_{idx}), run_time={min(duration * 0.4, 1.5)})
self.wait({max(duration * 0.2, 0.5)})
self.play(FadeOut(shapes_{idx}, arrows_{idx}), run_time=0.5)
'''
    
    def _gen_code_animation(self, anim: Dict, duration: float, idx: int) -> str:
        """Generate code display animation"""
        
        code_content = anim.get("code", "print('Hello')").replace('"', '\\"')
        language = anim.get("language", "python")
        
        return f'''
code_{idx} = Code(
    code=\"\"\"{code_content}\"\"\",
    tab_width=4,
    background="window",
    language="{language}",
    font="Monospace",
    style="monokai"
)
self.play(Create(code_{idx}), run_time={min(duration * 0.6, 2)})
self.wait({max(duration * 0.4, 0.5)})
self.play(FadeOut(code_{idx}), run_time=0.5)
'''
    
    async def _render_scene(self, scene_file: str, output_path: str):
        """Render the Manim scene to video"""
        
        # Determine output directory and filename
        output_dir = os.path.dirname(output_path)
        output_name = os.path.splitext(os.path.basename(output_path))[0]
        
        # Build manim command
        cmd = [
            "manim",
            "-qm",  # Medium quality for reasonable render time
            "--format", "mp4",
            "-o", output_name,
            scene_file,
            "GeneratedScene"
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=output_dir
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                print(f"Manim render failed: {stderr.decode()}")
                # Create a placeholder video
                await self._create_placeholder_video(output_path)
            else:
                # Move rendered file to expected location
                rendered_path = os.path.join(
                    output_dir, "media", "videos", "scene", "720p30",
                    f"{output_name}.mp4"
                )
                if os.path.exists(rendered_path):
                    os.rename(rendered_path, output_path)
                    
        except FileNotFoundError:
            print("Manim not found, creating placeholder video")
            await self._create_placeholder_video(output_path)
    
    async def _create_placeholder_video(self, output_path: str, duration: float = 5.0):
        """Create a placeholder video when Manim is not available"""
        
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c=0x1a1a2e:s=1920x1080:d={duration}",
            "-f", "lavfi",
            "-i", f"anullsrc=r=44100:cl=stereo:d={duration}",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-shortest",
            output_path
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
        except Exception as e:
            print(f"Failed to create placeholder video: {e}")
            # Last resort: create empty file
            with open(output_path, 'wb') as f:
                pass
