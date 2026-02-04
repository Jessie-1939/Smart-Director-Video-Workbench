from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from openai import OpenAI

from config import Settings


SYSTEM_PROMPT = """你是一个专业的“视频生成提示词（Prompt）”AI Agent，目标平台：即梦（剪映）视频生成。

平台适配（非常重要）：
- 即梦类视频模型往往会“抓重点而忽略长文本”。提示词过长、信息过密、嵌套括号太多、互相矛盾（例如：既要清晰无畸变又要强畸变、既要主观透窗又要走廊全景）会导致结果拉跨。
- 你的目标不是写一篇散文，而是给模型一个“稳定可执行”的指令：先给短关键词定风格，再给少量镜头脚本定节奏。
- 恐怖/血腥元素在部分平台可能触发弱化/风格化；因此你在最终输出中要额外给一个“低血腥替代表达”，保证可出片。

工作流程：
1) 用户先给一个粗略想法。
2) 你要像导演+摄影指导+编剧一样拆解需求，找出缺失信息。
3) 对不清楚/缺少细节之处进行追问；每轮最多问 3 个问题，问题要具体可选（给几个选项能更快）。
4) 当信息足够或用户要求总结时，输出最终“可直接粘贴”的提示词，必须同时包含：视频画面 + 音乐。

最终输出必须遵循“短而强”的结构（写进 final_prompt）：
1) 【即梦短提示】<= 280 字：用逗号分隔的关键词串（主体、场景、风格、光影、色彩、镜头、动作、质感、参数）。
2) 【12秒镜头脚本】<= 650 字：用 0-3s / 3-6s / 6-9s / 9-12s 四段，描述每段镜头内容与运镜。
3) 【音乐/音效】<= 220 字：节奏、情绪、配器、关键音效点。
4) 【负面】<= 160 字：用短词列表。
5) 【低血腥替代】（若存在血腥/腐烂/丧尸）：给一版更容易过审/更稳的替代表达（例如用“污渍、破损、阴影、非写实恐怖”替换直白血腥）。

表达要求：
- 全程中文。
- 画面要电影级，但最终可粘贴提示词必须“可执行、少冲突、少歧义”。
- 优先级：构图/主体动作/场景光线 > 风格质感 > 细枝末节；不要一次塞 30 个细节。
- 默认不杜撰用户明确否定的内容；但可以提出合理补全选项。
- 最终提示词要结构化、可复制粘贴，避免冗余解释。

输出格式：
你必须只输出 JSON（不要输出 Markdown 代码块），形如：
{
  "status": "need_more" | "final",
  "assistant_message": "给用户看的自然语言回复",
  "questions": ["...", "..."],
  "final_prompt": "...",
  "checklist": {
    "subject": "...",
    "scene": "...",
    "time": "...",
    "style": "...",
    "camera": "...",
    "lighting": "...",
    "color": "...",
    "motion": "...",
    "music": "...",
    "duration": "...",
    "aspect_ratio": "...",
    "fps": "...",
    "negatives": "..."
  }
}

规则：
- status=need_more 时，final_prompt 置空字符串；questions 给出 1-3 个。
- status=final 时，questions 置空数组；final_prompt 必须按“短提示+脚本+音乐+负面(+低血腥替代)”结构输出。
- 任何情况下都不要输出 Markdown 代码块；只输出 JSON。
"""


@dataclass
class AgentResponse:
    status: str
    assistant_message: str
    questions: List[str]
    final_prompt: str
    checklist: Dict[str, Any]


class VideoPromptAgent:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = OpenAI(api_key=settings.api_key, base_url=settings.base_url)
        self._messages: List[Dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]

    def reset(self) -> None:
        self._messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    def step(self, user_text: str, force_finalize: bool = False) -> AgentResponse:
        user_text = (user_text or "").strip()
        if force_finalize:
            user_text = user_text + "\n\n（用户指令：现在请直接总结并输出最终可粘贴提示词，必要时自行做合理补全，并在负面提示里标明避免项。）"

        self._messages.append({"role": "user", "content": user_text})

        extra_body = {"enable_thinking": self._settings.enable_thinking}

        completion = self._client.chat.completions.create(
            model=self._settings.model,
            messages=self._messages,
            extra_body=extra_body,
            temperature=0.7,
        )

        content = (completion.choices[0].message.content or "").strip()
        data = _safe_parse_json(content)

        # 如果模型没按要求输出JSON，降级处理
        if not isinstance(data, dict) or "status" not in data:
            assistant_message = content if content else "我没拿到有效回复，请再试一次。"
            self._messages.append({"role": "assistant", "content": assistant_message})
            return AgentResponse(
                status="need_more",
                assistant_message=assistant_message,
                questions=["你能再补充一下你想要的视频大概是什么风格/主题吗？"],
                final_prompt="",
                checklist={},
            )

        resp = AgentResponse(
            status=str(data.get("status", "need_more")),
            assistant_message=str(data.get("assistant_message", "")),
            questions=list(data.get("questions", []) or []),
            final_prompt=str(data.get("final_prompt", "")),
            checklist=dict(data.get("checklist", {}) or {}),
        )

        # 把给用户看的自然语言内容写回对话
        # 这样下一轮模型能看到自己问过什么/总结过什么
        stitched = resp.assistant_message
        if resp.status == "need_more" and resp.questions:
            stitched += "\n\n我需要你确认/补充：\n" + "\n".join(
                [f"- {q}" for q in resp.questions]
            )
        if resp.status == "final" and resp.final_prompt:
            stitched += "\n\n最终提示词：\n" + resp.final_prompt

        self._messages.append({"role": "assistant", "content": stitched})
        return resp


_JSON_RE = re.compile(r"\{[\s\S]*\}\s*$")
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def _safe_parse_json(text: str) -> Optional[Dict[str, Any]]:
    """Try best-effort JSON extraction.

    Some providers may prepend/append stray text; we attempt to extract the last JSON object.
    """
    text = (text or "").strip()
    if not text:
        return None

    # remove common markdown fences
    text = _FENCE_RE.sub("", text).strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    m = _JSON_RE.search(text)
    if not m:
        return None

    candidate = m.group(0)
    try:
        return json.loads(candidate)
    except Exception:
        return None
