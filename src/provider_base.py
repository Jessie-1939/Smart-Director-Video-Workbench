from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from provider_types import ImageResult, VideoResult


class ImageProvider(ABC):
    @abstractmethod
    def generate_image(self, prompt: str, output_dir: str) -> ImageResult:
        raise NotImplementedError


class VideoProvider(ABC):
    @abstractmethod
    def generate_video(self, prompt: str, output_dir: str, reference_path: Optional[str] = None) -> VideoResult:
        raise NotImplementedError
