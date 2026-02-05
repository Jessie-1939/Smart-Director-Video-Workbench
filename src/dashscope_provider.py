from __future__ import annotations

import json
import os
import time
from typing import Optional
from urllib.parse import urlparse

import requests

from config import Settings
from provider_base import ImageProvider, VideoProvider
from provider_types import ImageResult, ProviderError, VideoResult


class DashScopeProvider(ImageProvider, VideoProvider):
    def __init__(self, settings: Settings) -> None:
        if not settings.api_key or "please_put_your_key_here" in settings.api_key:
            raise ProviderError(code="MISSING_API_KEY", message="DASHSCOPE_API_KEY 未配置")
        self._settings = settings

    def generate_image(self, prompt: str, output_dir: str) -> ImageResult:
        payload = {
            "model": self._settings.image_model,
            "input": {"prompt": prompt},
        }
        headers = self._auth_headers()
        response = requests.post(
            self._settings.image_endpoint,
            headers=headers,
            json=payload,
            timeout=self._settings.request_timeout_sec,
        )
        data = self._handle_response(response)
        url = _extract_first_url(data)
        local_path = _download_to(output_dir, url)
        width, height = _try_read_image_size(local_path)
        return ImageResult(local_path=local_path, width=width, height=height, model=self._settings.image_model)

    def generate_video(self, prompt: str, output_dir: str, reference_path: Optional[str] = None) -> VideoResult:
        payload = {
            "model": self._settings.video_t2v_model,
            "input": {"prompt": prompt},
        }
        if reference_path:
            if not _is_http_url(reference_path):
                raise ProviderError(code="REFERENCE_NOT_URL", message="reference_path 需要是可访问的URL")
            payload["model"] = self._settings.video_i2v_model
            payload["input"]["image_url"] = reference_path

        headers = self._auth_headers()
        headers["X-DashScope-Async"] = "enable"

        response = requests.post(
            self._settings.video_endpoint,
            headers=headers,
            json=payload,
            timeout=self._settings.request_timeout_sec,
        )
        data = self._handle_response(response)
        task_id = _extract_task_id(data)
        task_data = self._poll_task(task_id)
        url = _extract_first_url(task_data)
        local_path = _download_to(output_dir, url)
        return VideoResult(local_path=local_path, duration_sec=4.0, model=payload["model"])

    def _poll_task(self, task_id: str) -> dict:
        deadline = time.time() + 600
        while time.time() < deadline:
            response = requests.get(
                f"{self._settings.task_endpoint.rstrip('/')}/{task_id}",
                headers=self._auth_headers(),
                timeout=self._settings.request_timeout_sec,
            )
            data = self._handle_response(response)
            status = str(data.get("status", "")).lower()
            if status in {"succeeded", "success"}:
                return data
            if status in {"failed", "error"}:
                raise ProviderError(code="TASK_FAILED", message=json.dumps(data, ensure_ascii=False))
            time.sleep(self._settings.poll_interval_sec)
        raise ProviderError(code="TASK_TIMEOUT", message="任务轮询超时")

    def _auth_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._settings.api_key}",
            "Content-Type": "application/json",
        }

    def _handle_response(self, response: requests.Response) -> dict:
        if response.status_code >= 400:
            raise ProviderError(code=f"HTTP_{response.status_code}", message=response.text)
        try:
            return response.json()
        except Exception:
            raise ProviderError(code="INVALID_JSON", message=response.text)


def _extract_task_id(data: dict) -> str:
    task_id = data.get("task_id") or data.get("output", {}).get("task_id")
    if not task_id:
        raise ProviderError(code="TASK_ID_MISSING", message=json.dumps(data, ensure_ascii=False))
    return str(task_id)


def _extract_first_url(data: dict) -> str:
    candidates = []
    output = data.get("output") or {}
    if isinstance(output, dict):
        if "url" in output:
            candidates.append(output.get("url"))
        if "image_url" in output:
            candidates.append(output.get("image_url"))
        if "video_url" in output:
            candidates.append(output.get("video_url"))
        if "data" in output and isinstance(output["data"], list):
            for item in output["data"]:
                if isinstance(item, dict):
                    candidates.append(item.get("url") or item.get("image_url") or item.get("video_url"))
    for value in candidates:
        if isinstance(value, str) and value.startswith("http"):
            return value
    raise ProviderError(code="URL_MISSING", message=json.dumps(data, ensure_ascii=False))


def _download_to(output_dir: str, url: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.basename(urlparse(url).path) or "artifact"
    target = os.path.join(output_dir, filename)
    resp = requests.get(url, stream=True, timeout=30)
    if resp.status_code >= 400:
        raise ProviderError(code=f"DOWNLOAD_{resp.status_code}", message=resp.text)
    with open(target, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 64):
            if chunk:
                f.write(chunk)
    return target


def _try_read_image_size(path: str) -> tuple[int, int]:
    try:
        from PIL import Image

        with Image.open(path) as im:
            return im.size
    except Exception:
        return (0, 0)


def _is_http_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")
