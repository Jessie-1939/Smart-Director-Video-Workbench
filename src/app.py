"""Smart Director v2 — Application Entry Point.

Launches a PySide6 window with embedded WebEngineView.
The entire UI is rendered in HTML/CSS/JS for maximum
design flexibility (think DaVinci Resolve meets web).

Python backend is exposed via Qt WebChannel.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings, QWebEnginePage
from PySide6.QtWebChannel import QWebChannel

from bridge import Backend
from config import get_settings

_ROOT = Path(__file__).resolve().parent.parent
_UI_DIR = _ROOT / "ui"


class MainWindow(QMainWindow):
    """Main application window — hosts WebEngineView."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Smart Director — AI 视频一站式创作平台")
        self.setMinimumSize(1280, 800)
        self.resize(1440, 900)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        # WebEngine view
        self._web = QWebEngineView()
        layout.addWidget(self._web)

        # Configure WebEngine
        settings = self._web.settings()
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)

        # Set up WebChannel bridge
        self._backend = Backend(self)
        channel = QWebChannel()
        channel.registerObject("backend", self._backend)
        self._web.page().setWebChannel(channel)

        # Load the UI
        index_path = _UI_DIR / "index.html"
        if index_path.exists():
            self._web.setUrl(QUrl.fromLocalFile(str(index_path)))
        else:
            self._web.setHtml(self._fallback_html())

    @staticmethod
    def _fallback_html() -> str:
        return """
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8"></head>
        <body style="background:#1a1a2e;color:#e0e0e0;font-family:sans-serif;
                      display:flex;align-items:center;justify-content:center;height:100vh">
            <div style="text-align:center">
                <h1>⚠️ UI 文件未找到</h1>
                <p>请确保 <code>ui/index.html</code> 存在。</p>
            </div>
        </body>
        </html>
        """


def create_app() -> int:
    """Create and run the application. Returns exit code."""
    # Enable high-DPI
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

    app = QApplication(sys.argv)
    app.setApplicationName("Smart Director")
    app.setOrganizationName("SmartDirector")

    window = MainWindow()
    window.show()

    # Check config on startup
    warnings = get_settings().validate()
    if warnings:
        # Will be sent to frontend once WebChannel connects
        pass

    return app.exec()


if __name__ == "__main__":
    sys.exit(create_app())
