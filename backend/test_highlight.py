#!/usr/bin/env python3
"""
Manual test: crop a highlight box and send the crop to the API for structured output.

Usage:
  python backend/scripts/test_highlight_crop_api.py
  python backend/scripts/test_highlight_crop_api.py --keep
  python backend/scripts/test_highlight_crop_api.py --no-api
"""

import argparse
import asyncio
import os
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from app.services.pipeline.animation.generation.validation.spatial.highlight_boxes import HighlightBoxChecker
from app.services.infrastructure.llm import PromptingEngine, PromptConfig


class FakeRenderer:
    def __init__(self, frame: np.ndarray, time: float = 1.0):
        self._frame = frame
        self.time = time

    def get_frame(self):
        return self._frame


class FakeScene:
    def __init__(self, frame: np.ndarray):
        self.renderer = FakeRenderer(frame)


class FakeBox:
    def __init__(self, center=(0.0, 0.0, 0.0), width=4.0, height=2.0):
        self._center = np.array(center, dtype=float)
        self.width = width
        self.height = height

    def get_center(self):
        return self._center


async def _send_crop_to_api(image_path: Path) -> dict:
    engine = PromptingEngine("script_generation")
    prompt = (
        "Describe the attached image in one short sentence. "
        "Return JSON: {\"summary\": string}."
    )
    response_schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"}
        },
        "required": ["summary"]
    }
    config = PromptConfig(
        temperature=0.2,
        max_output_tokens=256,
        timeout=60,
        response_format="json",
    )

    image_bytes = image_path.read_bytes()
    try:
        image_part = engine.types.Part.from_data(
            data=image_bytes,
            mime_type="image/png"
        )
    except AttributeError:
        image_part = engine.types.Part.from_bytes(
            data=image_bytes,
            mime_type="image/png"
        )

    # ImageAnalyzer uses [prompt, image_part] ordering.
    contents = [prompt, image_part]
    result = await engine.generate(
        prompt=prompt,
        config=config,
        response_schema=response_schema,
        contents=contents
    )
    return result


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep", action="store_true", help="Keep the cropped PNG on disk")
    parser.add_argument("--no-api", action="store_true", help="Skip the API call step")
    args = parser.parse_args()

    # Build a synthetic frame (320x180) with a white block in the center.
    frame = np.zeros((180, 320, 3), dtype=np.uint8)
    frame[60:120, 120:200] = [255, 255, 255]

    # Manim-like config (16:9 frame).
    config = SimpleNamespace(frame_width=14.0, frame_height=8.0)

    checker = HighlightBoxChecker(engine=SimpleNamespace(config=config, mobject_classes={}))
    scene = FakeScene(frame)
    box = FakeBox(center=(0.0, 0.0, 0.0), width=4.0, height=2.0)

    crop_path = checker.crop_highlight_box(scene, box, config)
    if not crop_path:
        print("Crop failed: no output file")
        return 1

    crop_path = Path(crop_path)
    print(f"Cropped image saved to: {crop_path}")

    if not args.no_api:
        try:
            result = await _send_crop_to_api(crop_path)
            print("API result success:", result.get("success"))
            print("Parsed JSON:", result.get("parsed_json"))
            if result.get("error"):
                print("Error:", result.get("error"))
        except Exception as exc:
            print("API call failed:", exc)

    if not args.keep:
        try:
            os.remove(crop_path)
            print("Cropped image removed.")
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
