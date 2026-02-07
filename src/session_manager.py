"""Smart Director v2 — Session Manager.

Handles save/load/delete/auto-save of agent conversation sessions.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from config import get_settings


class SessionManager:
    """Manages conversation session persistence."""

    def __init__(self, sessions_dir: Optional[str] = None):
        self._dir = Path(sessions_dir or get_settings().sessions_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def list_sessions(self) -> list[dict[str, str]]:
        """Return list of sessions sorted by modified time (newest first).

        Each entry: {"name": "...", "path": "...", "modified": "..."}
        """
        sessions = []
        for f in self._dir.glob("*.json"):
            try:
                mtime = f.stat().st_mtime
                sessions.append({
                    "name": f.stem,
                    "path": str(f),
                    "modified": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M"),
                })
            except OSError:
                continue
        sessions.sort(key=lambda s: s["modified"], reverse=True)
        return sessions

    def save_session(self, name: str, data: dict[str, Any]) -> str:
        """Save session data to JSON file. Returns file path."""
        safe_name = self._sanitize_name(name)
        path = self._dir / f"{safe_name}.json"
        data["_saved_at"] = datetime.now().isoformat()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return str(path)

    def load_session(self, name: str) -> Optional[dict[str, Any]]:
        """Load session data from JSON file."""
        safe_name = self._sanitize_name(name)
        path = self._dir / f"{safe_name}.json"
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def delete_session(self, name: str) -> bool:
        """Delete a session file. Returns True if deleted."""
        safe_name = self._sanitize_name(name)
        path = self._dir / f"{safe_name}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    def auto_save_name(self) -> str:
        """Generate an auto-save session name with timestamp."""
        return f"auto_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def auto_save(self, data: dict[str, Any]) -> str:
        """Auto-save to a timestamped file. Returns file path."""
        name = self.auto_save_name()
        return self.save_session(name, data)

    @staticmethod
    def _sanitize_name(name: str) -> str:
        """Sanitize filename — keep only safe characters."""
        safe = "".join(c if c.isalnum() or c in "-_. " else "_" for c in name)
        return safe.strip() or "unnamed"
