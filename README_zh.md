# Smart Director (AI 视频创作助手)

一个专业的桌面级 AI 辅助视频创作工具，旨在成为您创作过程中的“AI 导演”。

[ **English** ](README.md) | [ **中文** ](README_zh.md)

---

与简单的提示词生成器不同，Smart Director 提供了完整的工作流：从**创意拆解**，到**分镜管理**，再到**自动化资产生成**（任务队列）。

> **由阿里云 DashScope (Wan2.1 / Qwen) 驱动**  
> 纯云端 API 架构（无需本地 GPU）。

## 🔥 核心特性

- **结构化提示词 (Structural Prompting)**: 将创意拆解为三个层级：“画面提示词”（用于文生图）、“导演脚本”（用于文生视频）和“负面/风格”约束。
- **项目管理**: 以 Project -> Sequence -> Scene -> Shot 的层级组织您的创作，支持无限层级。
- **任务队列系统 (Task Queue)**: 异步后台生成。您可以一次性排队生成 10 个镜头的变体，并在后台运行的同时继续编辑下一个场景。
- **纯云端架构**: 专为 DashScope API 生态系统构建（Qwen-Max 用于逻辑推理，Wan 用于视频生成，Qwen-VL 用于图像理解）。
- **格式控制**: 自动确保生成的提示词符合视频生成模型的严格长度和格式要求。

## 📂 项目结构

```
Smart-Director/
├── src/                  # 核心应用源码
│   ├── main.py           # GUI 入口 (PySide6)
│   ├── agent.py          # LLM 逻辑 (Qwen)
│   ├── project_store.py  # JSON 持久化层
│   ├── task_queue.py     # 后台执行引擎
│   └── dashscope_provider.py # API 集成
├── sessions/             # 本地项目存储 (自动创建)
├── run.py                # 启动脚本
└── requirements.txt      # Python 依赖
```

## 🚀 快速开始

### 1. 安装

```bash
# 克隆仓库
git clone https://github.com/YourUsername/Smart-Director.git
cd Smart-Director

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置

在根目录创建一个 `.env` 文件：

```ini
# .env
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
# 可选：设置默认模型
MODEL_LLM="qwen-max"
MODEL_IMAGE="wan-image-v1"
MODEL_VIDEO="wan-video-v1"
```

### 3. 运行

```bash
python run.py
```

## 🛠️ 开发

本项目使用 `PySide6` 构建 UI，并使用 `Pytest` 保证稳定性。

**运行测试:**
```bash
pytest -q
```

## 📝 工作流指南

1. **创建项目**: 开始一个新的叙事工程。
2. **草拟场景**: 输入一个粗略的想法（例如：“雨中的赛博朋克侦探”）。
3. **AI 润色**: Agent 将其扩展为视觉细节、镜头角度和光影设置。
4. **生成资产**:
   - **图像检查**: 生成静帧图以验证视觉风格。
   - **视频生成**: 发送到视频生成队列。
5. **评审**: 从生成的资产中挑选最佳的“候选素材 (Candidate)”。

## 📄 许可证

本项目基于 **GNU General Public License v3.0** 开源。详情请参阅 [LICENSE](LICENSE) 文件。
