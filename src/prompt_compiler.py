"""Smart Director v2 — Prompt Compiler.

Takes Agent's structured output + vibe console parameters
and compiles the final prompt text ready to paste into
video generation platforms.

vibe parameters are HARD CONSTRAINTS here — not suggestions.
The compiler enforces length limits, injects preset keywords,
and overrides params when param_lock is on.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional


# ─── vibe Style Presets ───────────────────────────────────────────
# Each preset defines keywords that get FORCE-INJECTED into the prompt.
STYLE_PRESETS: dict[str, dict[str, Any]] = {
    "Cinematic Noir（电影黑色）": {
        "inject_keywords": "film noir, high contrast, deep shadows, desaturated, moody lighting, film grain",
        "inject_negative": "bright colors, flat lighting, cartoon, overexposed",
        "default_aspect": "16:9",
    },
    "Dreamcore（梦核）": {
        "inject_keywords": "dreamlike, surreal, soft focus, ethereal glow, liminal space, nostalgic haze",
        "inject_negative": "sharp edges, realistic, clinical, harsh lighting",
        "default_aspect": "16:9",
    },
    "Cyber Neon（赛博霓虹）": {
        "inject_keywords": "neon lights, cyberpunk, rain-slick streets, holographic, electric blue and magenta, lens flares",
        "inject_negative": "natural lighting, pastoral, warm tones, daylight",
        "default_aspect": "16:9",
    },
    "Documentary Grit（纪实颗粒）": {
        "inject_keywords": "handheld camera, raw footage, natural lighting, film grain, cinema verite, 16mm film",
        "inject_negative": "polished, CGI, fantasy, smooth motion",
        "default_aspect": "16:9",
    },
    "Anime Live-Action Mix（动画写实混合）": {
        "inject_keywords": "anime-inspired, vibrant colors, dramatic angles, cel-shading meets photorealism, dynamic composition",
        "inject_negative": "pure 2D, static pose, dull colors",
        "default_aspect": "16:9",
    },
}


@dataclass
class VibeConfig:
    """vibe console state — passed from UI to compiler."""
    preset: str = "Cinematic Noir（电影黑色）"
    detail_density: int = 50        # 0-100, controls short_prompt max length
    atmosphere_intensity: int = 50  # 0-100, controls style keyword emphasis
    short_prompt_first: bool = True
    param_lock: bool = True
    # Locked params (only used when param_lock=True)
    locked_aspect_ratio: str = "16:9"
    locked_duration_sec: int = 5
    locked_fps: int = 24

    @property
    def max_short_len(self) -> int:
        """Calculate max short prompt length from detail density."""
        # density 0 → 150 chars, density 100 → 400 chars
        base = 150 + int(self.detail_density * 2.5)
        if self.short_prompt_first:
            return min(base, 320)
        return base


@dataclass
class CompiledPrompt:
    """Final compiled prompt ready for the user."""
    short_prompt: str = ""
    director_script: str = ""
    music_sound: str = ""
    negative: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    full_text: str = ""  # Combined copy-paste version


class PromptCompiler:
    """Compiles Agent output + vibe config into final prompt."""

    def compile(
        self,
        agent_output: dict[str, Any],
        vibe: Optional[VibeConfig] = None,
    ) -> CompiledPrompt:
        """Compile agent's structured output with vibe constraints.

        Args:
            agent_output: Dict from AgentResponse (short_prompt, director_script, etc.)
            vibe: vibe console config. If None, uses defaults.

        Returns:
            CompiledPrompt with all sections.
        """
        if vibe is None:
            vibe = VibeConfig()

        # 1. Extract raw sections
        short = agent_output.get("short_prompt", "")
        script = agent_output.get("director_script", "")
        music = agent_output.get("music_sound", "")
        negative = agent_output.get("negative", "")
        params = dict(agent_output.get("params", {}))

        # 2. FORCE-INJECT style preset keywords
        preset = STYLE_PRESETS.get(vibe.preset, {})
        if preset:
            inject_kw = preset.get("inject_keywords", "")
            if inject_kw and inject_kw not in short:
                short = f"{short.rstrip('。，, ')}; {inject_kw}"

            inject_neg = preset.get("inject_negative", "")
            if inject_neg and inject_neg not in negative:
                negative = f"{negative.rstrip('。，, ')}; {inject_neg}" if negative else inject_neg

        # 3. Enforce length limit on short prompt
        max_len = vibe.max_short_len
        if len(short) > max_len:
            short = self._smart_truncate(short, max_len)

        # 4. Apply param_lock overrides
        if vibe.param_lock:
            params["aspect_ratio"] = vibe.locked_aspect_ratio
            params["duration_sec"] = vibe.locked_duration_sec
            params["fps"] = vibe.locked_fps

        # 5. Build full text for copy-paste
        sections = []
        sections.append(f"【即梦短提示】\n{short}")
        if script:
            sections.append(f"【镜头脚本】\n{script}")
        if music:
            sections.append(f"【音乐/音效】\n{music}")
        if negative:
            sections.append(f"【负面约束】\n{negative}")
        if params:
            param_lines = []
            if params.get("aspect_ratio"):
                param_lines.append(f"比例: {params['aspect_ratio']}")
            if params.get("duration_sec"):
                param_lines.append(f"时长: {params['duration_sec']}s")
            if params.get("fps"):
                param_lines.append(f"帧率: {params['fps']}fps")
            if params.get("resolution"):
                param_lines.append(f"分辨率: {params['resolution']}")
            if param_lines:
                sections.append(f"【参数】\n{'  |  '.join(param_lines)}")

        full_text = "\n\n".join(sections)

        return CompiledPrompt(
            short_prompt=short,
            director_script=script,
            music_sound=music,
            negative=negative,
            params=params,
            full_text=full_text,
        )

    @staticmethod
    def _smart_truncate(text: str, max_len: int) -> str:
        """Truncate at natural break points (Chinese/English punctuation)."""
        if len(text) <= max_len:
            return text
        truncated = text[:max_len]
        # Find last good break point
        for punct in ["。", "；", "，", ". ", "; ", ", ", " "]:
            idx = truncated.rfind(punct)
            if idx > max_len * 0.6:
                return truncated[: idx + len(punct)].rstrip()
        return truncated.rstrip()
