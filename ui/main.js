let backend = null;
let lastFinal = "";

function initWebChannel() {
  new QWebChannel(qt.webChannelTransport, (channel) => {
    backend = channel.objects.backend;

    // Signals from Python
    backend.agentResponse.connect(onAgentResponse);
    backend.agentError.connect(onAgentError);
    backend.sessionListChanged.connect(refreshSessionsFromJson);

    // Initial load
    refreshSessions();
    applyVibeToBackend();
    updateLockVisibility();
  });
}

window.addEventListener("load", () => {
  if (typeof qt !== "undefined") {
    initWebChannel();
  }

  // UI events
  document.getElementById("image-drop").addEventListener("click", () => {
    document.getElementById("image-input").click();
  });

  document.getElementById("image-input").addEventListener("change", (e) => {
    if (e.target.files.length) {
      handleFile(e.target.files[0]);
    }
  });

  document.getElementById("vibe-detail").addEventListener("input", (e) => {
    document.getElementById("detail-val").textContent = e.target.value;
    applyVibeToBackend();
  });
  document.getElementById("vibe-atmo").addEventListener("input", (e) => {
    document.getElementById("atmo-val").textContent = e.target.value;
    applyVibeToBackend();
  });

  document.getElementById("vibe-lock").addEventListener("change", () => {
    updateLockVisibility();
    applyVibeToBackend();
  });

  ["vibe-preset", "vibe-short", "vibe-aspect", "vibe-duration", "vibe-fps"].forEach(id => {
    document.getElementById(id).addEventListener("change", applyVibeToBackend);
  });
});

function updateLockVisibility() {
  const lock = document.getElementById("vibe-lock").checked;
  document.getElementById("locked-params").style.opacity = lock ? "1" : "0.4";
}

function applyVibeToBackend() {
  if (!backend) return;
  const vibe = {
    preset: document.getElementById("vibe-preset").value,
    detail_density: Number(document.getElementById("vibe-detail").value),
    atmosphere_intensity: Number(document.getElementById("vibe-atmo").value),
    short_prompt_first: document.getElementById("vibe-short").checked,
    param_lock: document.getElementById("vibe-lock").checked,
    locked_aspect_ratio: document.getElementById("vibe-aspect").value,
    locked_duration_sec: Number(document.getElementById("vibe-duration").value),
    locked_fps: Number(document.getElementById("vibe-fps").value),
  };
  backend.updateVibe(JSON.stringify(vibe));
}

function sendMessage() {
  const input = document.getElementById("user-input");
  const text = input.value.trim();
  if (!text || !backend) return;

  appendMessage("用户", text, true);
  setStatus("busy");
  backend.sendMessage(text);
  input.value = "";
}

function forceFinalize() {
  if (!backend) return;
  setStatus("busy");
  backend.forceFinalize();
}

function resetChat() {
  if (!backend) return;
  backend.resetConversation();
}

function onAgentResponse(jsonStr) {
  try {
    const data = JSON.parse(jsonStr);

    if (data.status === "reset") {
      appendMessage("系统", data.assistant_message || "对话已重置", false);
      clearOptions();
      hideFinalPrompt();
      setStatus("idle");
      return;
    }

    appendMessage("助手", data.assistant_message || "", false);

    if (data.questions && data.questions.length) {
      renderOptions(data.questions);
    } else {
      clearOptions();
    }

    if (data.status === "finalized") {
      const compiled = backend.compilePrompt(JSON.stringify(data));
      const compiledObj = JSON.parse(compiled);
      if (!compiledObj.error) {
        showFinalPrompt(compiledObj.full_text);
        lastFinal = compiledObj.full_text;
        addHistoryItem(compiledObj.full_text);
      }
    }

    setStatus("idle");
  } catch (e) {
    onAgentError(e.toString());
  }
}

function onAgentError(err) {
  appendMessage("系统", `错误: ${err}`, false);
  setStatus("error");
}

function appendMessage(role, text, isUser) {
  const container = document.getElementById("chat-messages");
  const msg = document.createElement("div");
  msg.className = "message " + (isUser ? "user-message" : "system-message");
  msg.innerHTML = `<div class="msg-role">${role}</div><div class="msg-content">${escapeHtml(text)}</div>`;
  container.appendChild(msg);
  container.scrollTop = container.scrollHeight;
}

function renderOptions(questions) {
  const bar = document.getElementById("options-bar");
  bar.innerHTML = "";
  const options = parseOptions(questions);
  if (!options.length) {
    bar.classList.add("hidden");
    return;
  }
  options.forEach(opt => {
    const chip = document.createElement("div");
    chip.className = "option-chip";
    chip.textContent = opt.label;
    chip.onclick = () => {
      const input = document.getElementById("user-input");
      input.value = input.value + (input.value ? "\n" : "") + opt.text;
    };
    bar.appendChild(chip);
  });
  bar.classList.remove("hidden");
}

function parseOptions(questions) {
  const result = [];
  questions.forEach(q => {
    const lines = q.split("\n");
    lines.forEach(line => {
      const m = line.match(/^([A-D]):\s*(.+)$/);
      if (m) {
        result.push({
          label: `${m[1]} · ${m[2]}`,
          text: `${m[1]}: ${m[2]}`,
        });
      }
    });
  });
  return result;
}

function clearOptions() {
  const bar = document.getElementById("options-bar");
  bar.innerHTML = "";
  bar.classList.add("hidden");
}

function showFinalPrompt(text) {
  const panel = document.getElementById("final-prompt-panel");
  const pre = document.getElementById("final-prompt-text");
  pre.textContent = text;
  panel.classList.remove("hidden");
}

function hideFinalPrompt() {
  const panel = document.getElementById("final-prompt-panel");
  panel.classList.add("hidden");
}

function copyFinalPrompt() {
  if (!lastFinal) return;
  navigator.clipboard.writeText(lastFinal);
}

function addHistoryItem(text) {
  const list = document.getElementById("history-list");
  if (list.querySelector(".history-empty")) {
    list.innerHTML = "";
  }
  const item = document.createElement("div");
  item.className = "message";
  item.innerHTML = `<div class="msg-role">历史</div><div class="msg-content">${escapeHtml(text.slice(0, 120))}...</div>`;
  list.appendChild(item);
}

function refreshSessions() {
  if (!backend) return;
  const json = backend.listSessions();
  refreshSessionsFromJson(json);
}

function refreshSessionsFromJson(json) {
  try {
    const sessions = JSON.parse(json);
    const list = document.getElementById("session-list");
    list.innerHTML = '<option value="">选择会话...</option>';
    sessions.forEach(s => {
      const opt = document.createElement("option");
      opt.value = s.name;
      opt.textContent = `${s.name} (${s.modified})`;
      list.appendChild(opt);
    });
  } catch { /* ignore */ }
}

function saveSession() {
  if (!backend) return;
  const name = prompt("会话名称:");
  if (name) backend.saveSession(name);
}

function loadSession() {
  if (!backend) return;
  const list = document.getElementById("session-list");
  if (list.value) backend.loadSession(list.value);
}

function deleteSession() {
  if (!backend) return;
  const list = document.getElementById("session-list");
  if (list.value) backend.deleteSession(list.value);
}

function setStatus(state) {
  const dot = document.getElementById("status-dot");
  dot.classList.remove("dot-idle", "dot-busy", "dot-error");
  dot.classList.add(state === "busy" ? "dot-busy" : state === "error" ? "dot-error" : "dot-idle");
}

function handleDrop(event) {
  event.preventDefault();
  const file = event.dataTransfer.files[0];
  if (file) handleFile(file);
}

function handleFile(file) {
  if (!backend) return;
  const reader = new FileReader();
  reader.onload = () => {
    const preview = document.getElementById("image-preview");
    preview.innerHTML = `<img src="${reader.result}" style="max-width:100%;border-radius:8px"/>`;
  };
  reader.readAsDataURL(file);

  const path = file.path || "";
  if (path) {
    const summary = backend.setImage(path);
    document.getElementById("image-summary").textContent = summary;
  }
}

function escapeHtml(text) {
  return text.replace(/[&<>"']/g, (m) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;"
  }[m]));
}
