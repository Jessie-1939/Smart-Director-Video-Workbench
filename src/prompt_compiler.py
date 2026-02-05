from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union

@dataclass
class PromptCompilerConfig:
    max_short_len: int = 500  # DashScope supports longer contexts
    max_script_len: int = 2000
    strict_mode: bool = True
    platform: str = "general"

@dataclass
class CompiledResult:
    final_text: str
    warnings: List[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

class PromptCompiler:
    """
    Compiles structured agent output into platform-ready prompts.
    Handles length constraints, conflict resolution, and formatting.
    """
    def __init__(self, config: PromptCompilerConfig = None):
        self.config = config or PromptCompilerConfig()

    def compile(self, raw_data: Union[dict, str]) -> CompiledResult:
        """
        Input: JSON output from Agent
        Output: Final string.
        """
        warnings = []
        
        if isinstance(raw_data, str):
            extracted = self._parse_sections(raw_data)
        else:
            extracted = raw_data

        short = extracted.get("short_prompt", extracted.get("final_prompt", "")).strip()
        script = extracted.get("script", "") or extracted.get("final_prompt", "")
        negatives = extracted.get("negatives", "")
        
        # Simple Length Checks
        if len(short) > self.config.max_short_len:
            warnings.append(f"Short prompt very long ({len(short)} chars).")
            short = self._smart_truncate(short, self.config.max_short_len)

        parts = []
        
        parts.append("【画面提示】\n" + short)
        
        if script and script != short:
            parts.append("\n【镜头脚本】\n" + script)
            
        if negatives:
            parts.append("\n【负面提示】\n" + negatives)

        final_text = "\n".join(parts)
        
        return CompiledResult(
            final_text=final_text,
            warnings=warnings,
            stats={"total_len": len(final_text)}
        )

    def _parse_sections(self, text: str) -> Dict[str, str]:
        """Parse sections from a final prompt string."""
        if not text:
            return {}

        sections = {
            "short_prompt": "",
            "script": "",
            "negatives": "",
            "final_prompt": text,
        }

        mapping = {
            "画面提示": "short_prompt",
            "即梦短提示": "short_prompt", # Legacy support
            "镜头脚本": "script",
            "12秒镜头脚本": "script",
            "负面": "negatives",
            "负面提示": "negatives",
        }

        pattern = re.compile(r"【([^】]+)】\s*\n")
        matches = list(pattern.finditer(text))
        if not matches:
            return sections

        for idx, m in enumerate(matches):
            title = m.group(1).strip()
            key = mapping.get(title)
            if not key:
                continue
            start = m.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            content = text[start:end].strip()
            sections[key] = content

        return sections

    def _smart_truncate(self, text: str, max_len: int) -> str:
        if len(text) <= max_len:
            return text
        
        # Try to cut at last delimiter before max_len
        cut_point = max_len
        delimiters = ["。", "；", "，", ".", ";", ","]
        
        subset = text[:max_len]
        for d in delimiters:
            pos = subset.rfind(d)
            if pos > max_len * 0.7:  # Don't cut too early
                cut_point = pos + 1
                break
                
        return text[:cut_point] + "..."
