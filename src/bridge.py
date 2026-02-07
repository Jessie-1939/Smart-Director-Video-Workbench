"""Smart Director v2 — Python↔WebChannel Bridge.

Exposes Python backend services to the HTML/JS frontend
via Qt WebChannel. All methods decorated with @Slot are
callable from JavaScript.
"""

from __future__ import annotations

import json
import traceback
from typing import Any, Optional

from PySide6.QtCore import QObject, Signal, Slot, QThread

from agent import VideoPromptAgent, AgentResponse
from config import get_settings, Settings
from prompt_compiler import PromptCompiler, VibeConfig, CompiledPrompt
from session_manager import SessionManager


class _LlmWorker(QObject):
    """Runs agent.step() in a background thread."""
    finished = Signal(str)   # JSON string result
    error = Signal(str)

    def __init__(self, agent: VideoPromptAgent, text: str, force: bool):
        super().__init__()
        self._agent = agent
        self._text = text
        self._force = force

    @Slot()
    def run(self):
        try:
            resp = self._agent.step(self._text, force_finalize=self._force)
            # Serialize AgentResponse to JSON
            data = {
                "status": resp.status,
                "assistant_message": resp.assistant_message,
                "questions": resp.questions,
                "checklist": resp.checklist,
                "short_prompt": resp.short_prompt,
                "director_script": resp.director_script,
                "music_sound": resp.music_sound,
                "negative": resp.negative,
                "params": resp.params,
                "token_usage": resp.token_usage,
            }
            self.finished.emit(json.dumps(data, ensure_ascii=False))
        except Exception as e:
            self.error.emit(f"{e}\n{traceback.format_exc()}")


class Backend(QObject):
    """Bridge object registered with WebChannel as 'backend'.

    All @Slot methods are callable from JS via:
        backend.methodName(args, function(result) { ... })
    """

    # Signals that push data TO the frontend
    agentResponse = Signal(str)     # JSON string
    agentError = Signal(str)
    sessionListChanged = Signal(str)  # JSON array of sessions
    configWarnings = Signal(str)     # JSON array of warning strings

    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings: Settings = get_settings()
        self._agent = VideoPromptAgent(self._settings)
        self._compiler = PromptCompiler()
        self._session_mgr = SessionManager()
        self._vibe = VibeConfig()

        # Thread management
        self._llm_thread: Optional[QThread] = None
        self._llm_worker: Optional[_LlmWorker] = None

    # ── Agent ─────────────────────────────────────────────────────

    @Slot(str)
    def sendMessage(self, text: str):
        """Send user message to agent (async, result via agentResponse signal)."""
        # Append vibe context
        vibe_tag = self._build_vibe_tag()
        full_text = f"{text}\n\n{vibe_tag}" if vibe_tag else text
        self._run_agent(full_text, force=False)

    @Slot()
    def forceFinalize(self):
        """Force agent to output final prompt immediately."""
        self._run_agent("", force=True)

    @Slot()
    def resetConversation(self):
        """Reset agent conversation."""
        self._agent.reset()
        self.agentResponse.emit(json.dumps({
            "status": "reset",
            "assistant_message": "对话已重置。请描述你想要的视频创意。",
        }, ensure_ascii=False))

    @Slot(str, result=str)
    def setImage(self, path: str) -> str:
        """Set reference image, returns tech summary."""
        return self._agent.set_image(path)

    @Slot()
    def clearImage(self):
        self._agent.clear_image()

    # ── Prompt Compiler ───────────────────────────────────────────

    @Slot(str, result=str)
    def compilePrompt(self, agent_json: str) -> str:
        """Compile agent output with current vibe settings.

        Args:
            agent_json: JSON string of agent's finalized output.

        Returns:
            JSON string of CompiledPrompt.
        """
        try:
            data = json.loads(agent_json)
            result = self._compiler.compile(data, self._vibe)
            return json.dumps({
                "short_prompt": result.short_prompt,
                "director_script": result.director_script,
                "music_sound": result.music_sound,
                "negative": result.negative,
                "params": result.params,
                "full_text": result.full_text,
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    # ── vibe Console ──────────────────────────────────────────────

    @Slot(str)
    def updateVibe(self, vibe_json: str):
        """Update vibe config from frontend.

        Args:
            vibe_json: JSON with vibe console state.
        """
        try:
            data = json.loads(vibe_json)
            self._vibe = VibeConfig(
                preset=data.get("preset", self._vibe.preset),
                detail_density=data.get("detail_density", self._vibe.detail_density),
                atmosphere_intensity=data.get("atmosphere_intensity", self._vibe.atmosphere_intensity),
                short_prompt_first=data.get("short_prompt_first", self._vibe.short_prompt_first),
                param_lock=data.get("param_lock", self._vibe.param_lock),
                locked_aspect_ratio=data.get("locked_aspect_ratio", self._vibe.locked_aspect_ratio),
                locked_duration_sec=data.get("locked_duration_sec", self._vibe.locked_duration_sec),
                locked_fps=data.get("locked_fps", self._vibe.locked_fps),
            )
        except (json.JSONDecodeError, TypeError):
            pass

    @Slot(result=str)
    def getVibeConfig(self) -> str:
        """Return current vibe config as JSON."""
        return json.dumps({
            "preset": self._vibe.preset,
            "detail_density": self._vibe.detail_density,
            "atmosphere_intensity": self._vibe.atmosphere_intensity,
            "short_prompt_first": self._vibe.short_prompt_first,
            "param_lock": self._vibe.param_lock,
            "locked_aspect_ratio": self._vibe.locked_aspect_ratio,
            "locked_duration_sec": self._vibe.locked_duration_sec,
            "locked_fps": self._vibe.locked_fps,
        }, ensure_ascii=False)

    # ── Session Management ────────────────────────────────────────

    @Slot(result=str)
    def listSessions(self) -> str:
        return json.dumps(self._session_mgr.list_sessions(), ensure_ascii=False)

    @Slot(str, result=str)
    def saveSession(self, name: str) -> str:
        data = {
            "messages": self._agent.get_history(),
            "vibe": {
                "preset": self._vibe.preset,
                "detail_density": self._vibe.detail_density,
                "atmosphere_intensity": self._vibe.atmosphere_intensity,
                "short_prompt_first": self._vibe.short_prompt_first,
                "param_lock": self._vibe.param_lock,
                "locked_aspect_ratio": self._vibe.locked_aspect_ratio,
                "locked_duration_sec": self._vibe.locked_duration_sec,
                "locked_fps": self._vibe.locked_fps,
            },
        }
        path = self._session_mgr.save_session(name, data)
        self.sessionListChanged.emit(self.listSessions())
        return json.dumps({"path": path}, ensure_ascii=False)

    @Slot(str, result=str)
    def loadSession(self, name: str) -> str:
        data = self._session_mgr.load_session(name)
        if not data:
            return json.dumps({"error": "Session not found"}, ensure_ascii=False)
        # Restore agent
        messages = data.get("messages", [])
        if messages:
            self._agent.load_history(messages)
        # Restore vibe
        vibe_data = data.get("vibe", {})
        if vibe_data:
            self.updateVibe(json.dumps(vibe_data))
        return json.dumps({"ok": True, "message_count": len(messages)}, ensure_ascii=False)

    @Slot(str, result=str)
    def deleteSession(self, name: str) -> str:
        ok = self._session_mgr.delete_session(name)
        self.sessionListChanged.emit(self.listSessions())
        return json.dumps({"deleted": ok}, ensure_ascii=False)

    @Slot()
    def autoSave(self):
        """Auto-save current session."""
        data = {
            "messages": self._agent.get_history(),
            "vibe": {
                "preset": self._vibe.preset,
                "detail_density": self._vibe.detail_density,
                "atmosphere_intensity": self._vibe.atmosphere_intensity,
                "short_prompt_first": self._vibe.short_prompt_first,
                "param_lock": self._vibe.param_lock,
                "locked_aspect_ratio": self._vibe.locked_aspect_ratio,
                "locked_duration_sec": self._vibe.locked_duration_sec,
                "locked_fps": self._vibe.locked_fps,
            },
        }
        self._session_mgr.auto_save(data)

    # ── Config ────────────────────────────────────────────────────

    @Slot(result=str)
    def getConfigWarnings(self) -> str:
        return json.dumps(self._settings.validate(), ensure_ascii=False)

    @Slot(result=str)
    def getAgentStats(self) -> str:
        return json.dumps({
            "message_count": self._agent.message_count,
            "estimated_tokens": self._agent.estimated_tokens,
        })

    # ── Private ────────────────────────────────────────────────────

    def _run_agent(self, text: str, force: bool):
        """Run agent in background thread."""
        if self._llm_thread is not None and self._llm_thread.isRunning():
            self.agentError.emit("Agent 正在处理中，请稍候...")
            return

        self._llm_thread = QThread()
        self._llm_worker = _LlmWorker(self._agent, text, force)
        self._llm_worker.moveToThread(self._llm_thread)

        self._llm_thread.started.connect(self._llm_worker.run)
        self._llm_worker.finished.connect(self._on_agent_done)
        self._llm_worker.error.connect(self._on_agent_error)
        self._llm_worker.finished.connect(self._cleanup_thread)
        self._llm_worker.error.connect(self._cleanup_thread)

        self._llm_thread.start()

    def _on_agent_done(self, result_json: str):
        self.agentResponse.emit(result_json)
        # Auto-save after each response
        self.autoSave()

    def _on_agent_error(self, err: str):
        self.agentError.emit(err)

    def _cleanup_thread(self):
        if self._llm_thread:
            self._llm_thread.quit()
            self._llm_thread.wait(3000)
            if self._llm_worker:
                self._llm_worker.deleteLater()
            self._llm_thread.deleteLater()
            self._llm_thread = None
            self._llm_worker = None

    def _build_vibe_tag(self) -> str:
        """Build vibe context tag for injection into user message."""
        parts = [f"预设风格: {self._vibe.preset}"]
        parts.append(f"细节密度: {self._vibe.detail_density}/100")
        parts.append(f"氛围强度: {self._vibe.atmosphere_intensity}/100")
        if self._vibe.short_prompt_first:
            parts.append("短提示优先（≤280字）")
        if self._vibe.param_lock:
            parts.append(
                f"参数锁定: {self._vibe.locked_aspect_ratio}, "
                f"{self._vibe.locked_duration_sec}s, "
                f"{self._vibe.locked_fps}fps"
            )
        return "[vibe] " + " | ".join(parts)
