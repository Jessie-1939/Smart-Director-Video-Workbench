"""Smart Director v2 — Video Prompt Agent.

Multi-turn conversation agent that guides users to create
cinema-grade video prompts through iterative refinement.

Key improvements over v1:
- Token budget tracking (prevents context overflow)
- Structured JSON output with fallback parsing
- Separate thinking-mode (ask phase) vs schema-mode (finalize phase)
- Image tech summary without requiring vision model
- No content restrictions removed
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from openai import OpenAI

from config import Settings, get_settings

# ─── System Prompt ────────────────────────────────────────────────
SYSTEM_PROMPT = """\
你是 Smart Director — 一位顶级电影导演 + 摄影指导 + 声音设计师。

## 你的工作流
用户描述一个视频创意，你通过多轮对话补全细节，最后输出可直接粘贴到视频生成平台的结构化提示词。

## 追问阶段（status: "need_more"）
- 每轮最多问 3 个关键问题，用选项（A/B/C/D）方式让用户快速选择
- 问题聚焦于：主体动作、场景环境、镜头运动、光影氛围、色彩基调、音效节奏、时长参数
- 如果用户已给出足够信息（≥5个维度有明确描述），直接进入总结

## 总结阶段（status: "finalized"）
输出严格 JSON，包含以下字段：
{
  "status": "finalized",
  "assistant_message": "简短说明你的创作思路",
  "short_prompt": "≤280字的即梦/视频生成平台短提示词（主体+场景+风格+光影+镜头+参数）",
  "director_script": "按秒拆分的镜头脚本（如 0-3s: ... / 3-6s: ... ）",
  "music_sound": "音乐风格 + 关键音效节拍描述",
  "negative": "负面约束（不要出现的元素）",
  "params": {
    "aspect_ratio": "16:9 或 9:16 或 1:1",
    "duration_sec": 5,
    "fps": 24,
    "resolution": "1080p"
  }
}

## 追问阶段的 JSON 格式
{
  "status": "need_more",
  "assistant_message": "你的回复文本（可包含分析、建议）",
  "questions": [
    "问题1：关于XXX？\\nA: 选项A\\nB: 选项B\\nC: 选项C",
    "问题2：...",
    "问题3：..."
  ],
  "checklist": {
    "主体": "已确认/待确认",
    "场景": "已确认/待确认",
    "镜头": "已确认/待确认",
    "光影": "已确认/待确认",
    "色彩": "已确认/待确认",
    "音效": "已确认/待确认",
    "参数": "已确认/待确认"
  }
}

## 核心原则
1. short_prompt 必须 ≤280 字，信息密度优先于文学修辞
2. 避免冲突描述（如同时要求"主观镜头"和"多角度切换"）
3. 视频生成模型一次只能做一个连贯镜头，不要塞多个场景
4. director_script 的时间轴必须与 params.duration_sec 一致
5. 永远输出有效 JSON，不要输出 markdown 代码块包裹的 JSON

## vibe 控制参数
用户消息末尾可能附带 [vibe] 标签的控制参数，请尊重这些参数约束。
"""


# ─── Data Types ───────────────────────────────────────────────────
@dataclass
class AgentResponse:
    """Parsed response from the agent."""
    status: str = "need_more"
    assistant_message: str = ""
    questions: list[str] = field(default_factory=list)
    checklist: dict[str, str] = field(default_factory=dict)
    short_prompt: str = ""
    director_script: str = ""
    music_sound: str = ""
    negative: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    raw_json: dict[str, Any] = field(default_factory=dict)
    token_usage: dict[str, int] = field(default_factory=dict)


# ─── Agent ────────────────────────────────────────────────────────
class VideoPromptAgent:
    """Multi-turn conversation agent for video prompt generation."""

    MAX_CONTEXT_TOKENS = 12000
    SUMMARY_TRIGGER = 8000

    def __init__(self, settings: Optional[Settings] = None):
        self._settings = settings or get_settings()
        self._client = OpenAI(
            api_key=self._settings.api_key,
            base_url=self._settings.base_url,
        )
        self._messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        self._total_tokens = 0
        self._image_summary: Optional[str] = None

    def step(self, user_text: str, force_finalize: bool = False) -> AgentResponse:
        """Send user message and get agent response."""
        full_text = user_text
        if self._image_summary:
            full_text = f"[参考图片信息] {self._image_summary}\n\n{user_text}"
            self._image_summary = None

        self._messages.append({"role": "user", "content": full_text})

        if force_finalize:
            self._messages.append({
                "role": "user",
                "content": (
                    "请立即根据目前收集到的所有信息，输出最终的结构化提示词 JSON。"
                    'status 必须是 "finalized"。如有信息不足的维度，请用你的专业判断补全。'
                ),
            })

        try:
            call_kwargs: dict[str, Any] = {
                "model": self._settings.model,
                "messages": self._messages,
            }
            if self._settings.enable_thinking and not force_finalize:
                call_kwargs["extra_body"] = {"enable_thinking": True}

            response = self._client.chat.completions.create(**call_kwargs)
            choice = response.choices[0]
            raw_content = choice.message.content or ""

            usage = {}
            if response.usage:
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens or 0,
                    "completion_tokens": response.usage.completion_tokens or 0,
                    "total_tokens": response.usage.total_tokens or 0,
                }
                self._total_tokens += usage.get("total_tokens", 0)

            self._messages.append({"role": "assistant", "content": raw_content})

            if self._total_tokens > self.SUMMARY_TRIGGER:
                self._compress_context()

            parsed = self._safe_parse_json(raw_content)
            return self._build_response(parsed, raw_content, usage)

        except Exception as e:
            return AgentResponse(status="error", assistant_message=f"请求失败: {e}")

    def set_image(self, image_path: str) -> str:
        """Set reference image and return tech summary."""
        summary = self._summarize_image(image_path)
        self._image_summary = summary
        return summary

    def clear_image(self) -> None:
        self._image_summary = None

    def reset(self) -> None:
        self._messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        self._total_tokens = 0
        self._image_summary = None

    def get_history(self) -> list[dict]:
        return list(self._messages)

    def load_history(self, messages: list[dict]) -> None:
        self._messages = messages
        self._total_tokens = 0

    @property
    def message_count(self) -> int:
        return len(self._messages)

    @property
    def estimated_tokens(self) -> int:
        return self._total_tokens

    # ── Private ───────────────────────────────────────────────────

    def _compress_context(self) -> None:
        """Compress early turns into a summary to stay within token budget."""
        if len(self._messages) <= 6:
            return
        sys_msg = self._messages[0]
        keep_recent = self._messages[-4:]
        middle = self._messages[1:-4]
        if not middle:
            return
        parts = []
        for msg in middle:
            content = msg["content"]
            if len(content) > 200:
                content = content[:200] + "..."
            parts.append(f"[{msg['role']}] {content}")
        summary = "[对话历史摘要]\n" + "\n".join(parts)
        self._messages = [sys_msg, {"role": "assistant", "content": summary}, *keep_recent]
        self._total_tokens = int(self._total_tokens * 0.4)

    def _build_response(self, parsed: dict, raw_content: str, usage: dict) -> AgentResponse:
        status = parsed.get("status", "need_more")
        if status == "finalized":
            return AgentResponse(
                status="finalized",
                assistant_message=parsed.get("assistant_message", ""),
                short_prompt=parsed.get("short_prompt", ""),
                director_script=parsed.get("director_script", ""),
                music_sound=parsed.get("music_sound", ""),
                negative=parsed.get("negative", ""),
                params=parsed.get("params", {}),
                raw_json=parsed,
                token_usage=usage,
            )
        return AgentResponse(
            status="need_more",
            assistant_message=parsed.get("assistant_message", raw_content),
            questions=parsed.get("questions", []),
            checklist=parsed.get("checklist", {}),
            raw_json=parsed,
            token_usage=usage,
        )

    @staticmethod
    def _safe_parse_json(text: str) -> dict[str, Any]:
        """Extract JSON from LLM output with multiple fallback strategies."""
        if not text or not text.strip():
            return {}
        cleaned = text.strip()

        # Strategy 1: Direct parse
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Strategy 2: Remove markdown fences
        for block in re.findall(r"```(?:json)?\s*\n?(.*?)\n?\s*```", cleaned, re.DOTALL):
            try:
                return json.loads(block.strip())
            except json.JSONDecodeError:
                continue

        # Strategy 3: Find last {...} block
        for match in reversed(re.findall(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", cleaned, re.DOTALL)):
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue

        return {"status": "need_more", "assistant_message": cleaned}

    @staticmethod
    def _summarize_image(image_path: str) -> str:
        """Generate technical summary of an image."""
        try:
            from PIL import Image
            from math import gcd
            img = Image.open(image_path)
            w, h = img.size
            g = gcd(w, h)
            ratio = f"{w // g}:{h // g}"
            small = img.resize((1, 1))
            avg = small.getpixel((0, 0))
            avg_str = f"RGB({avg[0]},{avg[1]},{avg[2]})" if isinstance(avg, (tuple, list)) and len(avg) >= 3 else str(avg)
            gray = img.convert("L")
            pixels = list(gray.getdata())
            brightness = sum(pixels) / len(pixels) if pixels else 128
            tone = "偏暗" if brightness < 100 else "中等" if brightness < 170 else "偏亮"
            return f"分辨率: {w}x{h} | 比例: {ratio} | 平均色: {avg_str} | 亮度: {brightness:.0f}/255 | 色调: {tone}"
        except Exception as e:
            return f"图片分析失败: {e}"