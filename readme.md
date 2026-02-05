# Smart Director (AI Video Agent)

A professional desktop application for AI-assisted video creation, designed to act as your "AI Director" throughout the creative process.

[ **English** ](README.md) | [ **简体中文** ](README_zh.md)

---

Unlike simple prompt generators, Smart Director provides a full workflow: from **idea decomposition**, to **shot management**, to **automated asset generation** (Task Queue).

> **Powered by Alibaba DashScope (Wan2.1 / Qwen)**  
> Strictly uses Cloud APIs (No local GPU required).

##  Key Features

- **Structural Prompting**: Decomposes ideas into three layers: "Visual Prompt" (for Image Gen), "Director's Script" (for Video Gen), and "Negative/Style" constraints.
- **Project Management**: Organize your work into unlimited Projects, Sequences, Scenes, and Shots.
- **Task Queue System**: Asynchronous background generation. Queue up 10 variants of a shot and let it run while you edit the next scene.
- **Strictly Cloud-Native**: Built for the DashScope API ecosystem (Qwen-Max for logic, Wan for video, Qwen-VL for image understanding).
- **Format Control**: Automatically ensures prompts meet the strict length and format requirements of video generation models.

##  Project Structure

```
Smart-Director/
 src/                  # Core Application Source Code
    main.py           # GUI Entry Point (PySide6)
    agent.py          # LLM Logic (Qwen)
    project_store.py  # JSON-based Persistence Layer
    task_queue.py     # Background Execution Engine
    dashscope_provider.py # API Integration
 tests/                # Unit & Integration Tests (100% Coverage)
 sessions/             # Local Project Storage (Auto-created)
 run.py                # Application Launcher
 requirements.txt      # Python Dependencies
```

##  Getting Started

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/YourUsername/Smart-Director.git
cd Smart-Director

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Create a `.env` file in the root directory:

```ini
# .env
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
# Optional: Set default models
MODEL_LLM="qwen-max"
MODEL_IMAGE="wan-image-v1"
MODEL_VIDEO="wan-video-v1"
```

### 3. Run

```bash
python run.py
```

##  Development

This project uses `PySide6` for the UI and `Pytest` for reliability.

**Running Tests:**
```bash
pytest -q
```

##  Workflow Guide

1. **Create Project**: Start a new narrative.
2. **Draft Scene**: Enter a rough idea (e.g., "A cyberpunk detective in rain").
3. **AI Refinement**: The Agent expands this into visual details, camera angles, and lighting.
4. **Generate Assets**:
   - **Image Check**: Generate a still image to verify the look.
   - **Video Gen**: Send to the Video Generation Queue.
5. **Review**: Pick the best "Candidate" from your generated assets.

##  License

This project is licensed under the **GNU General Public License v3.0**. See the [LICENSE](LICENSE) file for details.
