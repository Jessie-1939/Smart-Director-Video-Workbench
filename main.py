from __future__ import annotations

import sys
import traceback
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
	QApplication,
	QHBoxLayout,
	QLabel,
	QMainWindow,
	QMessageBox,
	QPushButton,
	QPlainTextEdit,
	QSizePolicy,
	QTextEdit,
	QVBoxLayout,
	QWidget,
)

from agent import AgentResponse, VideoPromptAgent
from config import get_settings


class LlmWorker(QObject):
	finished = Signal(object)
	failed = Signal(str)

	def __init__(self, agent: VideoPromptAgent, user_text: str, force_finalize: bool):
		super().__init__()
		self._agent = agent
		self._user_text = user_text
		self._force_finalize = force_finalize

	def run(self) -> None:
		try:
			resp = self._agent.step(self._user_text, force_finalize=self._force_finalize)
			self.finished.emit(resp)
		except Exception as e:
			detail = "".join(traceback.format_exception(type(e), e, e.__traceback__))
			self.failed.emit(detail)


class MainWindow(QMainWindow):
	def __init__(self):
		super().__init__()
		self.setWindowTitle("智能视频描述词生成 Agent（即梦/剪映）")
		self.resize(980, 720)

		self._settings = get_settings()
		self._agent = VideoPromptAgent(self._settings)

		self._thread: Optional[QThread] = None
		self._worker: Optional[LlmWorker] = None

		root = QWidget()
		self.setCentralWidget(root)

		layout = QVBoxLayout(root)

		title = QLabel("多轮追问 → 生成电影级视频提示词（含画面+音乐）")
		title.setFont(QFont("Microsoft YaHei UI", 12))
		layout.addWidget(title)

		self.chat_view = QTextEdit()
		self.chat_view.setReadOnly(True)
		self.chat_view.setFont(QFont("Microsoft YaHei UI", 10))
		layout.addWidget(self.chat_view, stretch=4)

		self.final_label = QLabel("最终可粘贴提示词（生成后可直接复制）：")
		self.final_label.setVisible(False)
		layout.addWidget(self.final_label)

		self.final_prompt_view = QPlainTextEdit()
		self.final_prompt_view.setReadOnly(True)
		self.final_prompt_view.setFont(QFont("Consolas", 10))
		self.final_prompt_view.setVisible(False)
		self.final_prompt_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
		layout.addWidget(self.final_prompt_view, stretch=2)

		layout.addWidget(QLabel("你的补充/回答："))
		self.input_box = QPlainTextEdit()
		self.input_box.setPlaceholderText(
			"先描述你想要的视频（主题/人物/场景/氛围/风格/时长/比例/音乐等，知道多少写多少）…"
		)
		self.input_box.setFont(QFont("Microsoft YaHei UI", 10))
		self.input_box.setMaximumBlockCount(2000)
		layout.addWidget(self.input_box, stretch=1)

		btn_row = QHBoxLayout()

		self.send_btn = QPushButton("发送")
		self.send_btn.clicked.connect(self.on_send)
		btn_row.addWidget(self.send_btn)

		self.finalize_btn = QPushButton("直接总结生成最终提示词")
		self.finalize_btn.clicked.connect(self.on_finalize)
		btn_row.addWidget(self.finalize_btn)

		self.copy_btn = QPushButton("复制最终提示词")
		self.copy_btn.clicked.connect(self.on_copy)
		self.copy_btn.setEnabled(False)
		btn_row.addWidget(self.copy_btn)

		self.reset_btn = QPushButton("重置")
		self.reset_btn.clicked.connect(self.on_reset)
		btn_row.addWidget(self.reset_btn)

		btn_row.addStretch(1)
		layout.addLayout(btn_row)

		self._append_system_hint()
		self._warn_if_key_missing()

	def _append_system_hint(self) -> None:
		self._append("系统", "把你的想法写粗一点也没关系，我会追问补全，最后输出可直接粘贴的提示词。")

	def _warn_if_key_missing(self) -> None:
		if not self._settings.api_key or "please_put_your_key_here" in self._settings.api_key:
			QMessageBox.warning(
				self,
				"需要配置 API Key",
				"检测到 DASHSCOPE_API_KEY 未配置（或仍为占位符）。\n\n"
				"请在项目根目录的 .env 中设置 DASHSCOPE_API_KEY，然后重启程序。",
			)

	def _append(self, who: str, text: str) -> None:
		safe = (text or "").strip()
		if not safe:
			return
		self.chat_view.append(f"<b>{who}：</b>")
		self.chat_view.append(safe.replace("\n", "<br>"))
		self.chat_view.append("<hr>")

	def _set_busy(self, busy: bool) -> None:
		self.send_btn.setEnabled(not busy)
		self.finalize_btn.setEnabled(not busy)
		self.reset_btn.setEnabled(not busy)
		self.input_box.setReadOnly(busy)

	def _start_request(self, user_text: str, force_finalize: bool) -> None:
		user_text = (user_text or "").strip()
		if not user_text:
			return

		self._append("你", user_text)
		self.input_box.setPlainText("")
		self._set_busy(True)

		self._thread = QThread()
		self._worker = LlmWorker(self._agent, user_text=user_text, force_finalize=force_finalize)
		self._worker.moveToThread(self._thread)
		self._thread.started.connect(self._worker.run)
		self._worker.finished.connect(self._on_llm_finished)
		self._worker.failed.connect(self._on_llm_failed)
		self._worker.finished.connect(self._thread.quit)
		self._worker.failed.connect(self._thread.quit)
		self._thread.finished.connect(self._cleanup_thread)
		self._thread.start()

	def _cleanup_thread(self) -> None:
		if self._worker is not None:
			self._worker.deleteLater()
		if self._thread is not None:
			self._thread.deleteLater()
		self._worker = None
		self._thread = None

	def _on_llm_finished(self, resp_obj: object) -> None:
		self._set_busy(False)
		resp: AgentResponse = resp_obj  # type: ignore[assignment]

		msg = (resp.assistant_message or "").strip()
		if resp.status == "need_more":
			if resp.questions:
				msg = (msg + "\n\n" if msg else "") + "我需要你确认/补充：\n" + "\n".join(
					[f"- {q}" for q in resp.questions]
				)
			self._append("Agent", msg)
			return

		if resp.status == "final":
			self._append("Agent", msg or "已生成最终提示词。")
			self.final_label.setVisible(True)
			self.final_prompt_view.setVisible(True)
			self.final_prompt_view.setPlainText(resp.final_prompt or "")
			self.copy_btn.setEnabled(bool((resp.final_prompt or "").strip()))
			return

		# 兜底
		self._append("Agent", msg or "我收到了回复，但状态不明确。你可以继续补充，或点“直接总结”。")

	def _on_llm_failed(self, detail: str) -> None:
		self._set_busy(False)
		QMessageBox.critical(self, "调用失败", f"请求模型失败：\n\n{detail}")

	def on_send(self) -> None:
		self._start_request(self.input_box.toPlainText(), force_finalize=False)

	def on_finalize(self) -> None:
		text = self.input_box.toPlainText().strip()
		if not text:
			text = "请基于目前对话，直接输出最终提示词。"
		self._start_request(text, force_finalize=True)

	def on_copy(self) -> None:
		text = self.final_prompt_view.toPlainText()
		if not text.strip():
			return
		QApplication.clipboard().setText(text)
		QMessageBox.information(self, "已复制", "最终提示词已复制到剪贴板。")

	def on_reset(self) -> None:
		if self._thread is not None:
			QMessageBox.information(self, "请稍等", "当前正在请求模型，请等待完成后再重置。")
			return
		self._agent.reset()
		self.chat_view.clear()
		self.final_prompt_view.clear()
		self.final_label.setVisible(False)
		self.final_prompt_view.setVisible(False)
		self.copy_btn.setEnabled(False)
		self._append_system_hint()


def main() -> int:
	app = QApplication(sys.argv)
	w = MainWindow()
	w.show()
	return app.exec()


if __name__ == "__main__":
	raise SystemExit(main())
