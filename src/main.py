from __future__ import annotations

import sys
import traceback
from typing import Optional

import os

from PySide6.QtCore import QObject, QThread, Signal, Qt
from PySide6.QtGui import QAction, QFont, QPixmap
from PySide6.QtWidgets import (
	QApplication,
	QCheckBox,
	QComboBox,
	QFileDialog,
	QGroupBox,
	QHBoxLayout,
	QLabel,
	QListWidget,
	QListWidgetItem,
	QMainWindow,
	QMessageBox,
	QPlainTextEdit,
	QPushButton,
	QScrollArea,
	QSizePolicy,
	QSlider,
	QTextEdit,
	QVBoxLayout,
	QWidget,
	QInputDialog,
)
try:
	import speech_recognition as sr
except Exception:  # pragma: no cover
	sr = None  # type: ignore[assignment]

from agent import AgentResponse, VideoPromptAgent
from config import get_settings
from prompt_compiler import PromptCompiler, PromptCompilerConfig
from session_manager import SessionManager
from project_store import ProjectStore
from project_models import Project, ProjectDefaults, new_sequence, new_scene, new_shot, new_task
from dashscope_provider import DashScopeProvider
from task_queue import TaskQueue
from task_runner import TaskRunner


VIBE_QSS = """
QMainWindow { background: #0b0f17; }
QWidget { color: #e5e7eb; font-family: 'Microsoft YaHei UI'; }
QLabel { color: #e5e7eb; }
QTextEdit, QPlainTextEdit {
	background: #0f172a;
	border: 1px solid #1f2937;
	border-radius: 10px;
	padding: 10px;
	selection-background-color: #2563eb;
}
QTextEdit { font-size: 13px; }
QPlainTextEdit { font-size: 13px; }
QPushButton {
	background: #111827;
	border: 1px solid #243244;
	border-radius: 10px;
	padding: 8px 12px;
}
QPushButton:hover { border: 1px solid #3b82f6; }
QPushButton:disabled { color: #6b7280; border: 1px solid #1f2937; }
QGroupBox {
	border: 1px solid #1f2937;
	border-radius: 12px;
	margin-top: 10px;
	padding: 10px;
}
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: #93c5fd; }
QComboBox {
	background: #0f172a;
	border: 1px solid #1f2937;
	border-radius: 10px;
	padding: 6px 10px;
}
QSlider::groove:horizontal { height: 6px; background: #1f2937; border-radius: 3px; }
QSlider::handle:horizontal { width: 14px; margin: -6px 0; border-radius: 7px; background: #3b82f6; }
"""


def _extract_abc_choices(text: str):
	"""Parse choices like A:xxx B:yyy C:zzz from a question string."""
	import re
	if not text:
		return []
	pattern = re.compile(r"\b([A-D])\s*[：:.、]\s*([^\n;；]+)")
	choices = pattern.findall(text)
	return [(k.strip(), v.strip()) for k, v in choices if k and v]


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


class VoiceWorker(QObject):
	finished = Signal(str)
	failed = Signal(str)
	completed = Signal()

	def __init__(self, recognizer, microphone):
		super().__init__()
		self._recognizer = recognizer
		self._microphone = microphone

	def run(self) -> None:
		try:
			with self._microphone as source:
				audio_data = self._recognizer.listen(source, timeout=5, phrase_time_limit=10)
			try:
				text = self._recognizer.recognize_google(audio_data, language="zh-CN")
				self.finished.emit(text)
			except Exception as e:
				self.failed.emit(str(e))
		except Exception as e:
			self.failed.emit(str(e))
		finally:
			self.completed.emit()


class TaskWorker(QObject):
	finished = Signal(object)
	failed = Signal(str)

	def __init__(self, runner: TaskRunner, project_root: str):
		super().__init__()
		self._runner = runner
		self._project_root = project_root

	def run(self) -> None:
		try:
			result = self._runner.run_next(self._project_root)
			self.finished.emit(result)
		except Exception as e:
			self.failed.emit(str(e))


class MainWindow(QMainWindow):
	def __init__(self):
		super().__init__()
		self.setWindowTitle("Smart Director - AI视频一站式创作平台")
		self.resize(1200, 800)

		self._settings = get_settings()
		self._agent = VideoPromptAgent(self._settings)
		self._compiler = PromptCompiler()
		self._session_mgr = SessionManager()
		self._project_store = ProjectStore()
		self._project: Optional[Project] = None
		self._task_queue = TaskQueue(max_running=1)
		self._task_runner: Optional[TaskRunner] = None
		self._task_thread: Optional[QThread] = None
		self._task_worker: Optional[TaskWorker] = None

		self._thread: Optional[QThread] = None
		self._worker: Optional[LlmWorker] = None
		
		# 新增功能相关变量
		self.current_image_path = None
		self.recognizer = sr.Recognizer() if sr else None
		self.microphone = None
		self.is_recording = False
		self.option_buttons = []  # 存储选项按钮
		self.current_options = []  # 存储当前选项文本
		self._voice_thread: Optional[QThread] = None
		self._voice_worker: Optional[VoiceWorker] = None
		self._history_items = []
		self._sequence_id: Optional[str] = None
		self._scene_id: Optional[str] = None

		self._setup_menu()
		self.statusBar().showMessage("未加载项目")

		root = QWidget()
		self.setCentralWidget(root)

		main_layout = QHBoxLayout(root)  # 改为水平布局，左侧图片，右侧聊天

		# 左侧图片区域
		left_panel = QWidget()
		left_layout = QVBoxLayout(left_panel)
		
		# 图片上传和显示区域
		image_label = QLabel("参考图片（可选）：")
		image_label.setFont(QFont("Microsoft YaHei UI", 10))
		left_layout.addWidget(image_label)
		
		self.image_container = QScrollArea()
		self.image_container.setWidgetResizable(True)
		self.image_container.setMinimumWidth(300)
		self.image_container.setMaximumWidth(400)
		self.image_label = QLabel("点击下方按钮上传图片")
		self.image_label.setAlignment(Qt.AlignCenter)
		self.image_label.setWordWrap(True)
		self.image_container.setWidget(self.image_label)
		left_layout.addWidget(self.image_container)
		
		# 图片上传按钮
		self.upload_btn = QPushButton("上传图片")
		self.upload_btn.clicked.connect(self.on_upload_image)
		left_layout.addWidget(self.upload_btn)
		
		# 语音输入区域
		voice_label = QLabel("语音输入：")
		voice_label.setFont(QFont("Microsoft YaHei UI", 10))
		left_layout.addWidget(voice_label)
		
		self.voice_btn = QPushButton("开始录音")
		self.voice_btn.clicked.connect(self.on_voice_input)
		left_layout.addWidget(self.voice_btn)
		
		# VIBE 控制台
		vibe_box = QGroupBox("VIBE 控制台")
		vibe_layout = QVBoxLayout(vibe_box)

		vibe_layout.addWidget(QLabel("预设风格："))
		self.preset_combo = QComboBox()
		self.preset_combo.addItems(
			[
				"Cinematic Noir（电影黑色）",
				"Dreamcore（梦核）",
				"Cyber Neon（赛博霓虹）",
				"Documentary Grit（纪实颗粒）",
				"Anime Live-Action Mix（动画写实混合）",
			]
		)
		vibe_layout.addWidget(self.preset_combo)

		self.detail_label = QLabel("细节密度：50")
		vibe_layout.addWidget(self.detail_label)
		self.detail_slider = QSlider(Qt.Horizontal)
		self.detail_slider.setRange(0, 100)
		self.detail_slider.setValue(50)
		self.detail_slider.valueChanged.connect(lambda v: self.detail_label.setText(f"细节密度：{v}"))
		vibe_layout.addWidget(self.detail_slider)

		self.horror_label = QLabel("氛围强度：50")
		vibe_layout.addWidget(self.horror_label)
		self.horror_slider = QSlider(Qt.Horizontal)
		self.horror_slider.setRange(0, 100)
		self.horror_slider.setValue(50)
		self.horror_slider.valueChanged.connect(lambda v: self.horror_label.setText(f"氛围强度：{v}"))
		vibe_layout.addWidget(self.horror_slider)

		self.cb_short_prompt = QCheckBox("短提示优先（推荐）")
		self.cb_short_prompt.setChecked(True)
		vibe_layout.addWidget(self.cb_short_prompt)

		self.cb_low_gore = QCheckBox("低血腥兼容（更容易出片）")
		self.cb_low_gore.setChecked(True)
		vibe_layout.addWidget(self.cb_low_gore)

		self.cb_strict_params = QCheckBox("参数锁定（时长/比例/fps）")
		self.cb_strict_params.setChecked(True)
		vibe_layout.addWidget(self.cb_strict_params)

		left_layout.addWidget(vibe_box)

		# 会话管理
		session_box = QGroupBox("会话管理")
		session_layout = QVBoxLayout(session_box)
		self.session_list = QComboBox()
		self._refresh_session_list()
		session_layout.addWidget(self.session_list)

		session_btn_row = QHBoxLayout()
		self.save_session_btn = QPushButton("保存会话")
		self.save_session_btn.clicked.connect(self.on_save_session)
		session_btn_row.addWidget(self.save_session_btn)
		self.load_session_btn = QPushButton("加载会话")
		self.load_session_btn.clicked.connect(self.on_load_session)
		session_btn_row.addWidget(self.load_session_btn)
		session_layout.addLayout(session_btn_row)
		left_layout.addWidget(session_box)
		
		left_layout.addStretch()
		
		# 右侧聊天区域
		right_panel = QWidget()
		right_layout = QVBoxLayout(right_panel)

		title = QLabel("多轮追问 → 生成电影级视频提示词（含画面+音乐）")
		title.setFont(QFont("Microsoft YaHei UI", 12))
		right_layout.addWidget(title)

		self.chat_view = QTextEdit()
		self.chat_view.setReadOnly(True)
		self.chat_view.setFont(QFont("Microsoft YaHei UI", 10))
		right_layout.addWidget(self.chat_view, stretch=4)
		
		# 选项选择区域
		self.options_container = QWidget()
		self.options_layout = QVBoxLayout(self.options_container)
		self.options_container.setVisible(False)
		right_layout.addWidget(self.options_container)

		self.final_label = QLabel("最终可粘贴提示词（生成后可直接复制）：")
		self.final_label.setVisible(False)
		right_layout.addWidget(self.final_label)

		self.final_prompt_view = QPlainTextEdit()
		self.final_prompt_view.setReadOnly(True)
		self.final_prompt_view.setFont(QFont("Consolas", 10))
		self.final_prompt_view.setVisible(False)
		self.final_prompt_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
		right_layout.addWidget(self.final_prompt_view, stretch=2)

		self.history_label = QLabel("生成历史（点击回填）：")
		self.history_label.setVisible(True)
		right_layout.addWidget(self.history_label)
		self.history_list = QListWidget()
		self.history_list.itemClicked.connect(self.on_history_clicked)
		right_layout.addWidget(self.history_list, stretch=1)

		right_layout.addWidget(QLabel("你的补充/回答："))
		self.input_box = QPlainTextEdit()
		self.input_box.setPlaceholderText(
			"先描述你想要的视频（主题/人物/场景/氛围/风格/时长/比例/音乐等，知道多少写多少）…"
		)
		self.input_box.setFont(QFont("Microsoft YaHei UI", 10))
		self.input_box.setMaximumBlockCount(2000)
		right_layout.addWidget(self.input_box, stretch=1)

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

		self.gen_image_btn = QPushButton("生成图像候选（DashScope）")
		self.gen_image_btn.clicked.connect(lambda: self.on_generate_task("image"))
		btn_row.addWidget(self.gen_image_btn)

		self.gen_video_btn = QPushButton("生成视频候选（DashScope）")
		self.gen_video_btn.clicked.connect(lambda: self.on_generate_task("video"))
		btn_row.addWidget(self.gen_video_btn)

		btn_row.addStretch(1)
		right_layout.addLayout(btn_row)
		
		# 将左右面板添加到主布局
		main_layout.addWidget(left_panel)
		main_layout.addWidget(right_panel, stretch=1)

		self._append_system_hint()
		self._warn_if_key_missing()
		
		# 初始化语音识别
		self.init_speech_recognition()

	def _append_system_hint(self) -> None:
		self._append("系统", "把你的想法写粗一点也没关系，我会追问补全，最后输出可直接粘贴的提示词。你可以上传参考图片、使用语音输入或点击选项回答。")
		self._append("系统", "提示：想要更具风格化，建议先用单图生成确认氛围，生成视频时适当降低提示词复杂度。")
		
	def init_speech_recognition(self) -> None:
		"""初始化语音识别"""
		try:
			if sr is None:
				self.voice_btn.setEnabled(False)
				self.voice_btn.setText("语音不可用（缺少SpeechRecognition）")
				return
			if self.recognizer is None:
				self.voice_btn.setEnabled(False)
				self.voice_btn.setText("语音不可用")
				return

			# 获取默认麦克风
			mics = sr.Microphone.list_microphone_names()
			if not mics:
				self.voice_btn.setEnabled(False)
				self.voice_btn.setText("无可用麦克风")
				return
				
			# 使用默认麦克风
			self.microphone = sr.Microphone()
			
			# 在安静环境中调整麦克风
			with self.microphone as source:
				self.recognizer.adjust_for_ambient_noise(source, duration=1)
		except Exception as e:
			print(f"初始化语音识别失败: {e}")
			self.voice_btn.setEnabled(False)
			self.voice_btn.setText("语音初始化失败")

	def _setup_menu(self) -> None:
		menu_bar = self.menuBar()
		file_menu = menu_bar.addMenu("文件")

		new_action = QAction("新建项目", self)
		new_action.triggered.connect(self.on_new_project)
		file_menu.addAction(new_action)

		open_action = QAction("打开项目", self)
		open_action.triggered.connect(self.on_open_project)
		file_menu.addAction(open_action)

		save_action = QAction("保存项目", self)
		save_action.triggered.connect(self.on_save_project)
		file_menu.addAction(save_action)

	def _set_project(self, project: Project) -> None:
		self._project = project
		self._sequence_id = None
		self._scene_id = None
		self.setWindowTitle(f"Smart Director - {project.name}")
		self.statusBar().showMessage(f"已加载项目：{project.name}")
		self._init_task_runner()
		self._ensure_default_sequence_scene()

	def _init_task_runner(self) -> None:
		try:
			provider = DashScopeProvider(self._settings)
			self._task_runner = TaskRunner(self._project_store, self._task_queue, provider, provider)
		except Exception as e:
			self._task_runner = None
			self._append("系统", f"任务引擎未启用：{e}")

	def _ensure_default_sequence_scene(self) -> None:
		if not self._project:
			return
		if not self._project.sequence_ids:
			sequence = new_sequence(self._project.id, "Sequence 1", 1, self._project.defaults)
			self._project_store.add_sequence(self._project, sequence)
			self._sequence_id = sequence.id
		else:
			self._sequence_id = self._project.sequence_ids[0]
		if not self._project.scene_ids:
			scene = new_scene(self._project.id, self._sequence_id or "", "Scene 1", 1)
			self._project_store.add_scene(self._project, scene)
			self._scene_id = scene.id
		else:
			self._scene_id = self._project.scene_ids[0]

	def on_new_project(self) -> None:
		root_dir = QFileDialog.getExistingDirectory(self, "选择项目目录")
		if not root_dir:
			return

		project_file = os.path.join(root_dir, "project.json")
		if os.path.exists(project_file):
			resp = QMessageBox.question(
				self,
				"项目已存在",
				"所选目录已存在项目，是否直接打开？",
				QMessageBox.Yes | QMessageBox.No,
			)
			if resp == QMessageBox.Yes:
				self._open_project_from_dir(root_dir)
			return

		if os.listdir(root_dir):
			resp = QMessageBox.question(
				self,
				"目录非空",
				"所选目录非空，仍然在此初始化项目？",
				QMessageBox.Yes | QMessageBox.No,
			)
			if resp != QMessageBox.Yes:
				return

		name = os.path.basename(os.path.normpath(root_dir)) or "未命名项目"
		name, ok = QInputDialog.getText(self, "项目名称", "请输入项目名称：", text=name)
		if not ok:
			return
		name = (name or "").strip() or "未命名项目"

		try:
			project = self._project_store.create_project(
				root_dir=root_dir,
				name=name,
				defaults=ProjectDefaults(),
			)
			self._set_project(project)
			QMessageBox.information(self, "已创建", f"项目已创建：{project.root_path}")
		except Exception as e:
			QMessageBox.warning(self, "创建失败", str(e))

	def on_open_project(self) -> None:
		root_dir = QFileDialog.getExistingDirectory(self, "选择项目目录")
		if not root_dir:
			return
		self._open_project_from_dir(root_dir)

	def _open_project_from_dir(self, root_dir: str) -> None:
		try:
			project = self._project_store.load_project(root_dir)
			self._set_project(project)
		except Exception as e:
			QMessageBox.warning(self, "打开失败", str(e))

	def on_save_project(self) -> None:
		if not self._project:
			QMessageBox.information(self, "未加载项目", "请先新建或打开一个项目。")
			return
		try:
			self._project_store.save_project(self._project)
			self.statusBar().showMessage(f"项目已保存：{self._project.name}")
		except Exception as e:
			QMessageBox.warning(self, "保存失败", str(e))

	def on_generate_task(self, task_type: str) -> None:
		if not self._project:
			QMessageBox.information(self, "未加载项目", "请先新建或打开一个项目。")
			return
		if not self._task_runner:
			QMessageBox.warning(self, "任务不可用", "DashScope 任务引擎未就绪，请检查 API Key 与配置。")
			return
		prompt = self.input_box.toPlainText().strip()
		if not prompt:
			QMessageBox.information(self, "缺少内容", "请先在输入框填写镜头描述。")
			return

		self._ensure_default_sequence_scene()
		shot = new_shot(
			self._project.id,
			self._sequence_id or "",
			self._scene_id or "",
			order=len(self._project.shot_ids) + 1,
			prompt=prompt,
		)
		self._project_store.add_shot(self._project, shot)

		input_refs = {"shot_id": shot.id}
		if task_type == "video":
			if self.current_image_path and self.current_image_path.startswith("http"):
				input_refs["reference_path"] = self.current_image_path
			elif self.current_image_path:
				self._append("系统", "参考图片为本地文件，视频任务需要可访问URL，已忽略参考图。")

		model = self._settings.image_model if task_type == "image" else self._settings.video_t2v_model
		task = new_task(self._project.id, task_type, model, input_refs)
		self._project_store.add_task(self._project, task)
		self._task_queue.enqueue(task)
		self._append("系统", f"已提交 {task_type} 任务：{task.id}")
		self._run_task_async()

	def _run_task_async(self) -> None:
		if not self._project or not self._task_runner:
			return
		if self._task_thread is not None:
			return
		self._task_thread = QThread()
		self._task_worker = TaskWorker(self._task_runner, self._project.root_path)
		self._task_worker.moveToThread(self._task_thread)
		self._task_thread.started.connect(self._task_worker.run)
		self._task_worker.finished.connect(self._on_task_finished)
		self._task_worker.failed.connect(self._on_task_failed)
		self._task_worker.finished.connect(self._task_thread.quit)
		self._task_worker.failed.connect(self._task_thread.quit)
		self._task_thread.finished.connect(self._cleanup_task_thread)
		self._task_thread.start()

	def _cleanup_task_thread(self) -> None:
		if self._task_worker is not None:
			self._task_worker.deleteLater()
		if self._task_thread is not None:
			self._task_thread.deleteLater()
		self._task_worker = None
		self._task_thread = None

	def _on_task_finished(self, candidate_obj: object) -> None:
		if candidate_obj is None:
			self._append("系统", "任务执行完成，但未生成候选。")
			return
		try:
			candidate = candidate_obj
			self._append("系统", f"候选生成完成：{candidate.local_uri}")
		except Exception:
			self._append("系统", "候选生成完成。")

	def _on_task_failed(self, message: str) -> None:
		self._append("系统", f"任务执行失败：{message}")
			
	def on_upload_image(self) -> None:
		"""处理图片上传"""
		file_path, _ = QFileDialog.getOpenFileName(
			self, 
			"选择图片", 
			"", 
			"图片文件 (*.png *.jpg *.jpeg *.bmp *.gif)"
		)
		
		if file_path:
			self.current_image_path = file_path
			# 设置agent的图片路径
			self._agent.set_image(file_path)
			
			# 加载并显示图片
			pixmap = QPixmap(file_path)
			if not pixmap.isNull():
				# 缩放图片以适应显示区域
				scaled_pixmap = pixmap.scaled(
					self.image_container.width(), 
					400, 
					Qt.KeepAspectRatio, 
					Qt.SmoothTransformation
				)
				self.image_label.setPixmap(scaled_pixmap)
				self.upload_btn.setText("更换图片")
				
				# 添加图片信息到聊天
				self._append("系统", f"已上传参考图片: {os.path.basename(file_path)}")
			else:
				QMessageBox.warning(self, "图片加载失败", "无法加载所选图片，请尝试其他图片。")
				
	def on_voice_input(self) -> None:
		"""处理语音输入"""
		if not self.microphone:
			QMessageBox.warning(self, "麦克风不可用", "未检测到可用的麦克风设备。")
			return
			
		if self.is_recording:
			QMessageBox.information(self, "录音中", "正在识别语音，请稍等完成…")
			return

		# 开始录音（一次性录 5~10 秒，避免复杂的“持续录音”状态机）
		self.is_recording = True
		self.voice_btn.setEnabled(False)
		self.voice_btn.setText("正在识别…")
		self.voice_btn.setStyleSheet("background-color: #b91c1c; color: white;")

		self._voice_thread = QThread()
		self._voice_worker = VoiceWorker(self.recognizer, self.microphone)
		self._voice_worker.moveToThread(self._voice_thread)
		self._voice_thread.started.connect(self._voice_worker.run)
		self._voice_worker.finished.connect(self._on_voice_text)
		self._voice_worker.failed.connect(self._on_voice_error)
		self._voice_worker.completed.connect(self._voice_thread.quit)
		self._voice_thread.finished.connect(self._cleanup_voice_thread)
		self._voice_thread.start()

	def _cleanup_voice_thread(self) -> None:
		if self._voice_worker is not None:
			self._voice_worker.deleteLater()
		if self._voice_thread is not None:
			self._voice_thread.deleteLater()
		self._voice_worker = None
		self._voice_thread = None
		self.is_recording = False
		self.voice_btn.setEnabled(True)
		self.voice_btn.setText("开始录音")
		self.voice_btn.setStyleSheet("")

	def _on_voice_text(self, text: str) -> None:
		text = (text or "").strip()
		if not text:
			return
		# 仅填充输入框，不自动发送，避免误触
		self.input_box.setPlainText(text)
		self._append("系统", f"[语音转文字] {text}")

	def _on_voice_error(self, message: str) -> None:
		QMessageBox.warning(self, "语音识别失败", message or "语音识别失败")
		
	def _show_questions(self, questions: list) -> None:
		"""把Agent的 questions 渲染成‘可点选的快捷回答’。支持解析 A/B/C/D。"""
		# 清空旧组件
		while self.options_layout.count():
			item = self.options_layout.takeAt(0)
			w = item.widget()
			if w is not None:
				w.deleteLater()
		self.option_buttons.clear()

		if not questions:
			self.options_container.setVisible(False)
			return

		title = QLabel("快捷回答（点一下把答案填入输入框，可再编辑）：")
		title.setStyleSheet("color: #93c5fd;")
		self.options_layout.addWidget(title)

		for idx, q in enumerate(questions, start=1):
			q_label = QLabel(f"{idx}. {q}")
			q_label.setWordWrap(True)
			self.options_layout.addWidget(q_label)

			choices = _extract_abc_choices(q)
			if choices:
				row = QHBoxLayout()
				for k, v in choices:
					btn = QPushButton(k)
					btn.setToolTip(v)
					btn.clicked.connect(
						lambda checked, n=idx, kk=k, vv=v: self.on_choice_selected(n, kk, vv)
					)
					row.addWidget(btn)
					self.option_buttons.append(btn)
				row.addStretch(1)
				wrap = QWidget()
				wrap.setLayout(row)
				self.options_layout.addWidget(wrap)
			else:
				btn = QPushButton("把这个问题复制到输入框")
				btn.clicked.connect(lambda checked, qq=q: self._fill_input(qq))
				self.options_layout.addWidget(btn)
				self.option_buttons.append(btn)

		self.options_container.setVisible(True)

	def _fill_input(self, text: str) -> None:
		self.input_box.setPlainText((text or "").strip())

	def on_choice_selected(self, q_index: int, choice_key: str, choice_text: str) -> None:
		"""把选项以可追溯的格式填入输入框，方便多题连选。"""
		existing = self.input_box.toPlainText().strip()
		line = f"{q_index}. {choice_key}（{choice_text}）"
		merged = (existing + "\n" + line).strip() if existing else line
		self.input_box.setPlainText(merged)
		
	def on_option_selected(self, selected_option: str) -> None:
		"""处理选项选择"""
		# 兼容旧调用：现在不直接发送，只填入输入框
		self.input_box.setPlainText(selected_option)
		
		# 隐藏选项
		self.options_container.setVisible(False)

	def _build_vibe_context(self) -> str:
		preset = self.preset_combo.currentText().strip()
		detail = self.detail_slider.value()
		mood = self.horror_slider.value()
		flags = []
		if self.cb_short_prompt.isChecked():
			flags.append("短提示优先")
		if self.cb_low_gore.isChecked():
			flags.append("低血腥兼容")
		if self.cb_strict_params.isChecked():
			flags.append("参数锁定")
		flags_text = "、".join(flags) if flags else "无"
		return (
			"[VIBE控制参数]\n"
			f"- 预设: {preset}\n"
			f"- 细节密度(0-100): {detail}\n"
			f"- 氛围强度(0-100): {mood}\n"
			f"- 开关: {flags_text}\n"
			"- 约束: 输出按‘画面提示 + 剧本描述 + 风格参数’\n"
		)

	def _build_compiler_config(self) -> PromptCompilerConfig:
		# 细节密度影响长度上限
		detail = self.detail_slider.value()
		short_max = 240 + int(detail * 1.6)  # 240~400
		script_max = 520 + int(detail * 2.0)  # 520~720
		if self.cb_short_prompt.isChecked():
			short_max = min(short_max, 320)
		cfg = PromptCompilerConfig(
			max_short_len=short_max,
			max_script_len=script_max,
			strict_mode=self.cb_strict_params.isChecked(),
			platform="general",
		)
		return cfg

	def _compile_final_prompt(self, resp: AgentResponse) -> str:
		self._compiler.config = self._build_compiler_config()
		result = self._compiler.compile(resp.final_prompt or "")
		if result.warnings:
			self._append("系统", "编译器提示：\n" + "\n".join([f"- {w}" for w in result.warnings]))
		return result.final_text

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

		# 注入VIBE控制参数（纯文本，模型可读）
		user_text = user_text + "\n\n" + self._build_vibe_context()

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
				# 显示快捷回答
				self._show_questions(resp.questions)
			self._append("Agent", msg)
			return

		if resp.status == "final":
			self._append("Agent", msg or "已生成最终提示词。")
			self.final_label.setVisible(True)
			self.final_prompt_view.setVisible(True)
			compiled = self._compile_final_prompt(resp)
			self.final_prompt_view.setPlainText(compiled)
			self.copy_btn.setEnabled(bool(compiled.strip()))
			self._push_history_snapshot(compiled)
			# 隐藏选项
			self.options_container.setVisible(False)
			return

		# 兜底
		self._append("Agent", msg or "我收到了回复，但状态不明确。你可以继续补充，或点'直接总结'。")
		# 隐藏选项
		self.options_container.setVisible(False)

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
		self.current_image_path = None
		self.image_label.clear()
		self.image_label.setText("点击下方按钮上传图片")
		self.upload_btn.setText("上传图片")
		self.chat_view.clear()
		self.final_prompt_view.clear()
		self.final_label.setVisible(False)
		self.final_prompt_view.setVisible(False)
		self.copy_btn.setEnabled(False)
		self.history_list.clear()
		self._history_items.clear()
		# 隐藏选项
		self.options_container.setVisible(False)
		self._append_system_hint()

	def _push_history_snapshot(self, text: str) -> None:
		if not text.strip():
			return
		from datetime import datetime
		title = datetime.now().strftime("%H:%M:%S") + " - 生成快照"
		item = QListWidgetItem(title)
		item.setData(Qt.UserRole, text)
		self.history_list.insertItem(0, item)
		self._history_items.insert(0, text)

	def on_history_clicked(self, item: QListWidgetItem) -> None:
		text = item.data(Qt.UserRole) or ""
		if text:
			self.final_label.setVisible(True)
			self.final_prompt_view.setVisible(True)
			self.final_prompt_view.setPlainText(text)
			self.copy_btn.setEnabled(True)

	def _refresh_session_list(self) -> None:
		self.session_list.clear()
		for name in self._session_mgr.list_sessions():
			self.session_list.addItem(name)

	def _collect_session_state(self) -> dict:
		return {
			"version": 1,
			"agent_state": self._agent.get_state(),
			"vibe": {
				"preset": self.preset_combo.currentText(),
				"detail": self.detail_slider.value(),
				"mood": self.horror_slider.value(),
				"short_prompt": self.cb_short_prompt.isChecked(),
				"low_gore": self.cb_low_gore.isChecked(),
				"strict_params": self.cb_strict_params.isChecked(),
			},
			"chat_html": self.chat_view.toHtml(),
			"final_prompt": self.final_prompt_view.toPlainText(),
			"history": self._history_items,
			"image_path": self.current_image_path,
		}

	def on_save_session(self) -> None:
		state = self._collect_session_state()
		name = self._session_mgr.auto_save_name()
		path = self._session_mgr.save_session(name, state)
		self._refresh_session_list()
		QMessageBox.information(self, "已保存", f"会话已保存：\n{path}")

	def on_load_session(self) -> None:
		name = self.session_list.currentText().strip()
		if not name:
			QMessageBox.information(self, "无可加载会话", "当前没有会话文件。")
			return
		state = self._session_mgr.load_session(name)
		if not state:
			QMessageBox.warning(self, "加载失败", "会话文件读取失败。")
			return

		self._agent.load_state(state.get("agent_state", {}))
		vibe = state.get("vibe", {})
		self.preset_combo.setCurrentText(vibe.get("preset", self.preset_combo.currentText()))
		self.detail_slider.setValue(int(vibe.get("detail", 50)))
		self.horror_slider.setValue(int(vibe.get("mood", 50)))
		self.cb_short_prompt.setChecked(bool(vibe.get("short_prompt", True)))
		self.cb_low_gore.setChecked(bool(vibe.get("low_gore", True)))
		self.cb_strict_params.setChecked(bool(vibe.get("strict_params", True)))

		self.chat_view.setHtml(state.get("chat_html", ""))
		final_text = state.get("final_prompt", "")
		self.final_prompt_view.setPlainText(final_text)
		self.final_label.setVisible(bool(final_text))
		self.final_prompt_view.setVisible(bool(final_text))
		self.copy_btn.setEnabled(bool(final_text))

		self.history_list.clear()
		self._history_items = list(state.get("history", []))
		for text in self._history_items:
			item = QListWidgetItem("历史快照")
			item.setData(Qt.UserRole, text)
			self.history_list.addItem(item)

		image_path = state.get("image_path")
		if image_path:
			self._agent.set_image(image_path)
			pixmap = QPixmap(image_path)
			if not pixmap.isNull():
				scaled_pixmap = pixmap.scaled(
					self.image_container.width(),
					400,
					Qt.KeepAspectRatio,
					Qt.SmoothTransformation,
				)
				self.image_label.setPixmap(scaled_pixmap)
				self.upload_btn.setText("更换图片")
				self.current_image_path = image_path

		QMessageBox.information(self, "已加载", f"会话已加载：{name}")


def main() -> int:
	app = QApplication(sys.argv)
	app.setStyleSheet(VIBE_QSS)
	w = MainWindow()
	w.show()
	return app.exec()


if __name__ == "__main__":
	raise SystemExit(main())