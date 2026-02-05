from __future__ import annotations

import os
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from provider_base import ImageProvider, VideoProvider
from provider_types import ImageResult, VideoResult


class MockProvider(ImageProvider, VideoProvider):
    def __init__(self, image_model: str = "mock-image", video_model: str = "mock-video") -> None:
        self.image_model = image_model
        self.video_model = video_model

    def generate_image(self, prompt: str, output_dir: str) -> ImageResult:
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, "mock_image.png")
        width, height = 768, 432
        image = Image.new("RGB", (width, height), color=(18, 24, 38))
        draw = ImageDraw.Draw(image)
        text = (prompt or "mock image")[:120]
        draw.text((20, 20), text, fill=(230, 230, 230))
        image.save(path)
        return ImageResult(local_path=path, width=width, height=height, model=self.image_model)

    def generate_video(self, prompt: str, output_dir: str, reference_path: Optional[str] = None) -> VideoResult:
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, "mock_video.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("MOCK VIDEO\n")
            f.write(f"prompt: {prompt}\n")
            if reference_path:
                f.write(f"reference: {reference_path}\n")
        return VideoResult(local_path=path, duration_sec=4.0, model=self.video_model)
