
import os
import subprocess
import sys
from pathlib import Path

# Theme configuration extracted from backend/app/services/pipeline/animation/config.py
THEME_SETUP_CODES = {
    "3b1b": '        self.camera.background_color = "#171717"\n',
    "clean": '        self.camera.background_color = "#FFFFFF"\n',
    "dracula": '        self.camera.background_color = "#282A36"\n',
    "nord": '        self.camera.background_color = "#2E3440"\n',
}

THEME_TEXT_DEFAULT_CODES = {
    "3b1b": (
        '        Text.set_default(color="#FFFFFF")\n'
        '        Tex.set_default(color="#FFFFFF")\n'
        '        MathTex.set_default(color="#FFFFFF")\n'
    ),
    "clean": (
        '        Text.set_default(color="#111111")\n'
        '        Tex.set_default(color="#111111")\n'
        '        MathTex.set_default(color="#111111")\n'
    ),
    "dracula": (
        '        Text.set_default(color="#F8F8F2")\n'
        '        Tex.set_default(color="#F8F8F2")\n'
        '        MathTex.set_default(color="#F8F8F2")\n'
    ),
    "nord": (
        '        Text.set_default(color="#ECEFF4")\n'
        '        Tex.set_default(color="#ECEFF4")\n'
        '        MathTex.set_default(color="#ECEFF4")\n'
    ),
}

# Accent colors for the shapes
THEME_ACCENTS = {
    "3b1b": "#58C4DD",
    "clean": "#236B8E",  # Darker blue for contrast on white
    "dracula": "#FF79C6",
    "nord": "#88C0D0"
}

# Axis colors
THEME_AXIS_COLORS = {
    "3b1b": "#FFFFFF",
    "clean": "#000000",
    "dracula": "#FFFFFF",
    "nord": "#FFFFFF",
}

OUTPUT_DIR = Path("backend/static/style_previews")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def generate_preview(style):
    print(f"Generating preview for style: {style}")
    
    filename = f"temp_preview_{style}.py"
    accent = THEME_ACCENTS.get(style, "#58C4DD")
    axis_color = THEME_AXIS_COLORS.get(style, "#FFFFFF")
    
    # Manim script content
    script_content = f"""
from manim import *

class Preview(Scene):
    def construct(self):
{THEME_SETUP_CODES.get(style, "")}
{THEME_TEXT_DEFAULT_CODES.get(style, "")}

        # Create sample content
        axes = Axes(
            x_range=[-3, 3, 1],
            y_range=[-2, 2, 1],
            x_length=6,
            y_length=4,
            axis_config={{"include_tip": True, "color": "{axis_color}"}}
        )
        
        # Function graph
        graph = axes.plot(lambda x: 0.1 * x**3 - 0.5 * x, color="{accent}")
        
        # Math equation
        equation = MathTex(r"e^{{i\\pi}} + 1 = 0", font_size=48)
        equation.to_edge(UP, buff=1.0)
        
        # Shape
        circle = Circle(radius=0.5, color="{accent}", fill_opacity=0.5)
        circle.move_to(axes.c2p(2, 1))
        
        # Layout
        self.add(axes, graph, equation, circle)
"""

    with open(filename, "w") as f:
        f.write(script_content)

    # Run Manim
    # -v WARNING: Less verbose
    # -r 640,360: Low res for thumbnail
    # -s: Save last frame (no video)
    # --format=png: Save as PNG
    # --disable_caching: Ensure fresh render
    cmd = [
        sys.executable, "-m", "manim", 
        "-v", "WARNING", 
        "-r", "640,360", 
        "-s", 
        "--format=png", 
        "--disable_caching",
        filename, 
        "Preview"
    ]
    
    try:
        subprocess.run(cmd, check=True)
        
        # Move output file
        # Default output structure: media/images/{filename}/Preview.png
        # Filename is temp_preview_{style}
        # Find generated file (Manim appends version to filename)
        # Default output structure: media/images/{filename}/Preview*.png
        generated_dir = Path(f"media/images/temp_preview_{style}")
        generated_files = list(generated_dir.glob("Preview*.png"))
        target_file = OUTPUT_DIR / f"{style}.png"
        
        if generated_files:
            generated_file = generated_files[0]
            if target_file.exists():
                target_file.unlink()
            generated_file.rename(target_file)
            print(f"Saved preview to {target_file}")
        else:
            print(f"Error: Output file not found in {generated_dir}")
            
    except subprocess.CalledProcessError as e:
        print(f"Error running Manim for {style}: {e}")
    finally:
        # Cleanup
        if os.path.exists(filename):
            os.remove(filename)

def main():
    styles = ["3b1b", "clean", "dracula", "nord"]
    for style in styles:
        generate_preview(style)
        
    # Cleanup media dir if empty or just containing the temp folders
    # (Optional, maybe risky to delete media/ if it contains other stuff)

if __name__ == "__main__":
    main()
