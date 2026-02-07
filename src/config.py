"""Smart Director v2 — Configuration loader.

Non-frozen dataclass so GUI can modify at runtime.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env", override=False)


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def _env_bool(key: str, default: bool = False) -> bool:
    v = _env(key, str(default)).lower()
    return v in ("1", "true", "yes", "on")


def _env_int(key: str, default: int = 0) -> int:
    try:
        return int(_env(key, str(default)))
    except ValueError:
        return default


@dataclass
class Settings:
    """Application settings — mutable at runtime."""

    # ── DashScope credentials ──
    api_key: str = ""
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model: str = "qwen-max"
    enable_thinking: bool = True

    # ── AIGC endpoints ──
    aigc_base_url: str = "https://dashscope.aliyuncs.com"
    image_model: str = "wanx2.1-t2i-turbo"
    image_endpoint: str = (
        "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"
    )
    video_t2v_model: str = "wanx2.1-t2v-turbo"
    video_i2v_model: str = "wanx2.1-i2v-turbo"
    video_endpoint: str = (
        "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2video/video-synthesis"
    )
    task_endpoint: str = "/api/v1/tasks/{task_id}"

    # ── Tuning ──
    poll_interval_sec: int = 5
    request_timeout_sec: int = 30

    # ── Paths ──
    sessions_dir: str = ""
    projects_dir: str = ""

    def validate(self) -> list[str]:
        """Return list of validation warnings (empty = OK)."""
        warnings = []
        if not self.api_key or self.api_key.startswith("sk-your"):
            warnings.append("DASHSCOPE_API_KEY 未配置，请在 .env 中填入有效的 API Key")
        return warnings


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Return singleton Settings, loading from env on first call."""
    global _settings
    if _settings is None:
        _settings = Settings(
            api_key=_env("DASHSCOPE_API_KEY"),
            base_url=_env("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            model=_env("QWEN_MODEL", "qwen-max"),
            enable_thinking=_env_bool("ENABLE_THINKING", True),
            aigc_base_url=_env("AIGC_BASE_URL", "https://dashscope.aliyuncs.com"),
            image_model=_env("IMAGE_MODEL", "wanx2.1-t2i-turbo"),
            image_endpoint=_env(
                "IMAGE_ENDPOINT",
                "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis",
            ),
            video_t2v_model=_env("VIDEO_T2V_MODEL", "wanx2.1-t2v-turbo"),
            video_i2v_model=_env("VIDEO_I2V_MODEL", "wanx2.1-i2v-turbo"),
            video_endpoint=_env(
                "VIDEO_ENDPOINT",
                "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2video/video-synthesis",
            ),
            task_endpoint=_env("TASK_ENDPOINT", "/api/v1/tasks/{task_id}"),
            poll_interval_sec=_env_int("POLL_INTERVAL_SEC", 5),
            request_timeout_sec=_env_int("REQUEST_TIMEOUT_SEC", 30),
            sessions_dir=str(_ROOT / "sessions"),
            projects_dir=str(_ROOT / "projects"),
        )
    return _settings


def reset_settings() -> None:
    """Force re-load on next get_settings() — useful for tests."""
    global _settings
    _settings = None
