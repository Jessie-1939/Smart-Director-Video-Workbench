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
    enable_vision: bool
    vision_model: str
    image_model: str
    video_t2v_model: str
    video_i2v_model: str
    aigc_base_url: str
    image_endpoint: str
    video_endpoint: str
    task_endpoint: str
    poll_interval_sec: float
    request_timeout_sec: float


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

    enable_vision_raw = os.getenv("ENABLE_VISION", "false").strip().lower()
    enable_vision = enable_vision_raw in {"1", "true", "yes", "y", "on"}
    vision_model = os.getenv("QWEN_VISION_MODEL", "").strip()
    image_model = os.getenv("QWEN_IMAGE_MODEL", "qwen-image-max").strip()
    video_t2v_model = os.getenv("WAN_T2V_MODEL", "wan2.6-t2v").strip()
    video_i2v_model = os.getenv("WAN_I2V_MODEL", "wan2.6-i2v").strip()

    aigc_base_url = os.getenv("DASHSCOPE_AIGC_BASE_URL", "https://dashscope.aliyuncs.com/api/v1").strip()
    image_endpoint = os.getenv(
        "DASHSCOPE_IMAGE_ENDPOINT",
        "https://dashscope.aliyuncs.com/api/v1/services/aigc/image-generation/generation",
    ).strip()
    video_endpoint = os.getenv(
        "DASHSCOPE_VIDEO_ENDPOINT",
        "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis",
    ).strip()
    task_endpoint = os.getenv(
        "DASHSCOPE_TASK_ENDPOINT",
        "https://dashscope.aliyuncs.com/api/v1/tasks",
    ).strip()
    poll_interval_sec = float(os.getenv("DASHSCOPE_POLL_INTERVAL_SEC", "2.5").strip() or 2.5)
    request_timeout_sec = float(os.getenv("DASHSCOPE_REQUEST_TIMEOUT_SEC", "30").strip() or 30)

    return Settings(
        api_key=api_key,
        base_url=base_url,
        model=model,
        enable_thinking=enable_thinking,
        enable_vision=enable_vision,
        vision_model=vision_model,
        image_model=image_model,
        video_t2v_model=video_t2v_model,
        video_i2v_model=video_i2v_model,
        aigc_base_url=aigc_base_url,
        image_endpoint=image_endpoint,
        video_endpoint=video_endpoint,
        task_endpoint=task_endpoint,
        poll_interval_sec=poll_interval_sec,
        request_timeout_sec=request_timeout_sec,
    )
