from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ProviderError(Exception):
    code: str
    message: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.code}: {self.message}"


@dataclass
class ImageResult:
    local_path: str
    width: int
    height: int
    model: str


@dataclass
class VideoResult:
    local_path: str
    duration_sec: float
    model: str
