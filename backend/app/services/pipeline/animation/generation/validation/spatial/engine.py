"""
Execution engine for Manim validation.
Handles loading Manim, configuring the environment, and monkey-patching for tracking.
"""

import importlib.util
import inspect
import os
import sys
import tempfile
import traceback
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Type


from .utils import get_user_code_context


class ManimEngine:
    """
    Manages the Manim runtime environment for validation.
    """

    def __init__(self, linter_path: str):
        self.linter_path = linter_path
        self.config = None
        self.Scene = None
        self.ThreeDScene = None
        self.mobject_classes: Dict[str, Type] = {}
        self.creation_lines: Dict[int, int] = {}  # id(mobj) -> line_number
        self._initialized = False

    def initialize(self) -> None:
        """Lazy load and initialize Manim."""
        if self._initialized:
            return

        import manim
        from manim import (
            config, Scene, ThreeDScene,
            Text, MathTex, Tex, Code, ImageMobject,
            VMobject, NumberPlane, Axes, Arrow, Line,
            DashedLine, Brace, Vector, ComplexPlane,
            Circle, Square, Rectangle
        )

        self.config = config
        self.Scene = Scene
        self.ThreeDScene = ThreeDScene

        self.mobject_classes = {
            'Text': Text, 'MathTex': MathTex, 'Tex': Tex, 'Code': Code,
            'ImageMobject': ImageMobject, 'VMobject': VMobject,
            'NumberPlane': NumberPlane, 'Axes': Axes, 'Arrow': Arrow,
            'Line': Line, 'DashedLine': DashedLine, 'Brace': Brace,
            'Vector': Vector, 'ComplexPlane': ComplexPlane,
            'Circle': Circle, 'Square': Square, 'Rectangle': Rectangle,
        }

        # Patch __init__ of all manim classes to track creation lines
        engine = self
        def patch_init(cls):
            orig_init = cls.__init__
            def new_init(self, *args, **kwargs):
                orig_init(self, *args, **kwargs)
                _, line = get_user_code_context(engine.linter_path)
                engine.creation_lines[id(self)] = line
            cls.__init__ = new_init

        for cls in self.mobject_classes.values():
            patch_init(cls)

        self._initialized = True

    def apply_fast_config(self) -> None:
        """Configure Manim for high-speed validation."""
        if not self.config:
            self.initialize()
            
        self.config.update({
            "write_to_movie": False,
            "save_last_frame": False,
            "preview": False,
            "verbosity": "CRITICAL",
            "renderer": "cairo",
            "frame_rate": 1,
            "pixel_width": 320,
            "pixel_height": 180,
            "quality": "low_quality"
        })

    @contextmanager
    def patched_runtime(self, on_play_callback: Any):
        """Context manager that patches Manim methods and restores them after."""
        if not self.Scene:
            self.initialize()
            
        original_play = self.Scene.play
        original_wait = self.Scene.wait
        
        def patched_play(scene_self, *args, **kwargs):
            on_play_callback(scene_self)
            original_play(scene_self, *args, **kwargs)
            on_play_callback(scene_self)
            
        def patched_wait(scene_self, *args, **kwargs):
            original_wait(scene_self, *args, **kwargs)
            on_play_callback(scene_self)

        try:
            self.Scene.play = patched_play
            self.Scene.wait = patched_wait
            yield
        finally:
            self.Scene.play = original_play
            self.Scene.wait = original_wait

    def run_scenes(self, temp_filename: str) -> List[Any]:
        """Import code and return instantiated scenes."""
        module_name = os.path.basename(temp_filename).replace(".py", "")
        
        # Ensure we can import from the temp file
        spec = importlib.util.spec_from_file_location(module_name, temp_filename)
        user_module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = user_module
        
        try:
            spec.loader.exec_module(user_module)
            scene_classes = [
                obj for _, obj in inspect.getmembers(user_module)
                if inspect.isclass(obj) and issubclass(obj, self.Scene)
                and obj.__module__ == module_name
            ]
            
            scenes = []
            for SCls in scene_classes:
                # Set renderer based on scene type
                self.config.renderer = "opengl" if issubclass(SCls, self.ThreeDScene) else "cairo"
                scene = SCls()
                scene.render()
                scenes.append(scene)
            return scenes
        finally:
            if module_name in sys.modules:
                del sys.modules[module_name]
