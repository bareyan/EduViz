"""
Tests for highlight box cropping.
"""

from types import SimpleNamespace

import numpy as np

from app.services.pipeline.animation.generation.validation.spatial.highlight_boxes import HighlightBoxChecker


class FakeRenderer:
    def __init__(self):
        self.time = 1.0

    def get_frame(self):
        return np.zeros((100, 100, 3), dtype=np.uint8)


class FakeScene:
    def __init__(self):
        self.renderer = FakeRenderer()


class FakeBox:
    def __init__(self, center=(0.0, 0.0, 0.0), width=4.0, height=2.0):
        self._center = np.array(center, dtype=float)
        self.width = width
        self.height = height

    def get_center(self):
        return self._center


def test_crop_highlight_box_creates_png(tmp_path):
    engine = SimpleNamespace(
        config=SimpleNamespace(frame_width=14.0, frame_height=8.0)
    )
    checker = HighlightBoxChecker(engine)
    scene = FakeScene()
    box = FakeBox()

    path = checker.crop_highlight_box(scene, box, engine.config)

    assert path is not None

    import os
    from PIL import Image

    assert os.path.exists(path)
    img = Image.open(path)
    assert img.size[0] > 0
    assert img.size[1] > 0
    img.close()
    os.remove(path)
