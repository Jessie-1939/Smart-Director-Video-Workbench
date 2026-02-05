from __future__ import annotations

import json
import os
from datetime import datetime
from glob import glob
from typing import Any, Dict, List, Optional

class SessionManager:
    """Manages saving and loading of agent sessions."""

    def __init__(self, session_dir: str = "sessions"):
        self.session_dir = session_dir
        os.makedirs(session_dir, exist_ok=True)

    def list_sessions(self) -> List[str]:
        """Return list of session filenames (sorted by new)."""
        files = glob(os.path.join(self.session_dir, "*.json"))
        # Sort by mtime desc
        files.sort(key=os.path.getmtime, reverse=True)
        return [os.path.basename(f) for f in files]

    def save_session(self, name: str, state: Dict[str, Any]) -> str:
        """Save state to json file."""
        if not name.endswith(".json"):
            name += ".json"
        
        # Clean filename
        path = os.path.join(self.session_dir, name)
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        return path

    def load_session(self, name: str) -> Optional[Dict[str, Any]]:
        path = os.path.join(self.session_dir, name)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def auto_save_name(self) -> str:
        """Generate a timestamp-based name."""
        return datetime.now().strftime("Session_%Y%m%d_%H%M%S.json")
