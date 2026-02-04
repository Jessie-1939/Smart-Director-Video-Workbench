from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str
    model: str
    enable_thinking: bool


def get_settings() -> Settings:
    """Load settings from .env / environment variables."""
    load_dotenv(override=False)

    api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    base_url = os.getenv(
        "DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    ).strip()
    model = os.getenv("QWEN_MODEL", "qwen3-max-2026-01-23").strip()
    enable_thinking_raw = os.getenv("ENABLE_THINKING", "true").strip().lower()
    enable_thinking = enable_thinking_raw in {"1", "true", "yes", "y", "on"}

    return Settings(
        api_key=api_key,
        base_url=base_url,
        model=model,
        enable_thinking=enable_thinking,
    )
