import { apiFetch } from "./api.js";

const MODEL_SUGGESTIONS = {
  openai: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
  anthropic: ["claude-sonnet-4-6", "claude-haiku-4-5-20251001", "claude-opus-4-6"],
  groq: ["llama3-70b-8192", "llama3-8b-8192", "mixtral-8x7b-32768", "gemma2-9b-it"],
  google: ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
  openrouter: ["moonshotai/kimi-k2", "moonshotai/kimi-k1.5", "meta-llama/llama-3.3-70b-instruct:free", "mistralai/mistral-7b-instruct:free"],
};

let modelsState = { models: [], active_id: null };
let phonesState = [];

// --- Feedback ---

function showFeedback(elId, msg, type) {
  const el = document.getElementById(elId);
  el.textContent = msg;
  el.className = `feedback ${type}`;
  setTimeout(() => { el.className = "feedback"; }, 4000);
}

// --- Sidebar navigation ---

function initNav() {
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("nav-item--active"));
      btn.classList.add("nav-item--active");
      const section = btn.dataset.section;
      document.querySelectorAll(".section").forEach((s) => s.style.display = "none");
      document.getElementById(`section-${section}`).style.display = "block";

      if (section === "whatsapp") {
        startWaPolling();
      } else {
        stopWaPolling();
      }
    });
  });
}

// =====================
// MODELS
// =====================

function updateModelSuggestions(provider) {
  const datalist = document.getElementById("model-suggestions");
  datalist.innerHTML = "";
  (MODEL_SUGGESTIONS[provider] || []).forEach((m) => {
    const opt = document.createElement("option");
    opt.value = m;
    datalist.appendChild(opt);
  });
}

function renderModels() {
  const list = document.getElementById("models-list");
  const select = document.getElementById("active-select");

  select.innerHTML = '<option value="">— Selecione um modelo —</option>';
  modelsState.models.forEach((m) => {
    const opt = document.createElement("option");
    opt.value = m.id;
    opt.textContent = `${m.name} (${m.provider} / ${m.model})`;
    if (m.id === modelsState.active_id) opt.selected = true;
    select.appendChild(opt);
  });

  if (modelsState.models.length === 0) {
    list.innerHTML = '<p class="empty-state">Nenhum modelo cadastrado ainda.</p>';
    return;
  }

  list.innerHTML = modelsState.models.map((m) => `
    <div class="list-item ${m.id === modelsState.active_id ? "list-item--active" : ""}">
      <div class="list-item__info">
        <span class="list-item__name">${m.name}</span>
        ${m.id === modelsState.active_id ? '<span class="badge badge--active">Ativo</span>' : ""}
        <span class="list-item__meta">${m.provider} / ${m.model}</span>
      </div>
      <div class="list-item__actions">
        <button class="btn-icon" title="Editar" onclick="editModel('${m.id}')">✏️</button>
        <button class="btn-icon btn-icon--danger" title="Remover" onclick="removeModel('${m.id}', '${m.name}')">🗑️</button>
      </div>
    </div>
  `).join("");
}

async function loadModels() {
  try {
    modelsState = await apiFetch("/admin/ai-models");
    renderModels();
  } catch (e) {
    showFeedback("active-feedback", e.message, "error");
  }
}

document.getElementById("activate-btn").addEventListener("click", async () => {
  const id = document.getElementById("active-select").value;
  if (!id) return;
  try {
    await apiFetch(`/admin/ai-models/${id}/activate`, { method: "PUT" });
    modelsState.active_id = id;
    renderModels();
    showFeedback("active-feedback", "Modelo ativo atualizado!", "success");
  } catch (e) {
    showFeedback("active-feedback", e.message, "error");
  }
});

document.getElementById("provider").addEventListener("change", (e) => {
  updateModelSuggestions(e.target.value);
  document.getElementById("model-id-input").value = "";
});

document.getElementById("model-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = document.getElementById("save-model-btn");
  btn.disabled = true;

  const id = document.getElementById("edit-model-id").value;
  const payload = {
    name: document.getElementById("model-name").value.trim(),
    provider: document.getElementById("provider").value,
    model: document.getElementById("model-id-input").value.trim(),
    api_key: document.getElementById("api-key").value.trim(),
  };

  try {
    if (id) {
      await apiFetch(`/admin/ai-models/${id}`, { method: "PUT", body: JSON.stringify(payload) });
      showFeedback("model-form-feedback", "Modelo atualizado!", "success");
    } else {
      await apiFetch("/admin/ai-models", { method: "POST", body: JSON.stringify(payload) });
      showFeedback("model-form-feedback", "Modelo cadastrado!", "success");
    }
    resetModelForm();
    await loadModels();
  } catch (e) {
    showFeedback("model-form-feedback", e.message, "error");
  } finally {
    btn.disabled = false;
  }
});

document.getElementById("cancel-model-btn").addEventListener("click", resetModelForm);

function resetModelForm() {
  document.getElementById("edit-model-id").value = "";
  document.getElementById("model-form").reset();
  document.getElementById("model-form-title").textContent = "Cadastrar modelo";
  document.getElementById("save-model-btn").textContent = "Cadastrar";
  document.getElementById("cancel-model-btn").style.display = "none";
  document.getElementById("key-hint").style.display = "none";
  document.getElementById("api-key").placeholder = "Insira a chave de API";
}

window.editModel = function (id) {
  const m = modelsState.models.find((m) => m.id === id);
  if (!m) return;
  document.getElementById("edit-model-id").value = m.id;
  document.getElementById("model-name").value = m.name;
  document.getElementById("provider").value = m.provider;
  updateModelSuggestions(m.provider);
  document.getElementById("model-id-input").value = m.model;
  document.getElementById("api-key").value = "";
  document.getElementById("api-key").placeholder = "Deixe em branco para manter a chave atual";
  document.getElementById("key-hint").style.display = "block";
  document.getElementById("model-form-title").textContent = "Editar modelo";
  document.getElementById("save-model-btn").textContent = "Salvar alterações";
  document.getElementById("cancel-model-btn").style.display = "inline-flex";
  document.getElementById("model-form").scrollIntoView({ behavior: "smooth" });
};

window.removeModel = async function (id, name) {
  if (!confirm(`Remover o modelo "${name}"?`)) return;
  try {
    await apiFetch(`/admin/ai-models/${id}`, { method: "DELETE" });
    await loadModels();
  } catch (e) {
    showFeedback("model-form-feedback", e.message, "error");
  }
};

// =====================
// PHONES
// =====================

function renderPhones() {
  const list = document.getElementById("phones-list");

  if (phonesState.length === 0) {
    list.innerHTML = '<p class="empty-state">Nenhum número cadastrado. Todos os contatos estão bloqueados.</p>';
    return;
  }

  list.innerHTML = phonesState.map((p) => `
    <div class="list-item">
      <div class="list-item__info">
        <span class="list-item__name">${p.name || "Sem nome"}</span>
        <span class="list-item__meta">${p.phone}</span>
      </div>
      <div class="list-item__actions">
        <button class="btn-icon" title="Editar" onclick="editPhone('${p.id}')">✏️</button>
        <button class="btn-icon btn-icon--danger" title="Remover" onclick="removePhone('${p.id}', '${p.name || p.phone}')">🗑️</button>
      </div>
    </div>
  `).join("");
}

async function loadPhones() {
  try {
    const data = await apiFetch("/admin/phones");
    phonesState = data.phones;
    renderPhones();
  } catch (e) {
    showFeedback("phone-form-feedback", e.message, "error");
  }
}

document.getElementById("phone-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = document.getElementById("save-phone-btn");
  btn.disabled = true;

  const id = document.getElementById("edit-phone-id").value;
  const payload = {
    phone: document.getElementById("phone-number").value.trim(),
    name: document.getElementById("phone-name").value.trim(),
  };

  try {
    if (id) {
      await apiFetch(`/admin/phones/${id}`, { method: "PUT", body: JSON.stringify(payload) });
      showFeedback("phone-form-feedback", "Número atualizado!", "success");
    } else {
      await apiFetch("/admin/phones", { method: "POST", body: JSON.stringify(payload) });
      showFeedback("phone-form-feedback", "Número cadastrado!", "success");
    }
    resetPhoneForm();
    await loadPhones();
  } catch (e) {
    showFeedback("phone-form-feedback", e.message, "error");
  } finally {
    btn.disabled = false;
  }
});

document.getElementById("cancel-phone-btn").addEventListener("click", resetPhoneForm);

function resetPhoneForm() {
  document.getElementById("edit-phone-id").value = "";
  document.getElementById("phone-form").reset();
  document.getElementById("phone-form-title").textContent = "Cadastrar número";
  document.getElementById("save-phone-btn").textContent = "Cadastrar";
  document.getElementById("cancel-phone-btn").style.display = "none";
}

window.editPhone = function (id) {
  const p = phonesState.find((p) => p.id === id);
  if (!p) return;
  document.getElementById("edit-phone-id").value = p.id;
  document.getElementById("phone-number").value = p.phone;
  document.getElementById("phone-name").value = p.name || "";
  document.getElementById("phone-form-title").textContent = "Editar número";
  document.getElementById("save-phone-btn").textContent = "Salvar alterações";
  document.getElementById("cancel-phone-btn").style.display = "inline-flex";
  document.getElementById("phone-form").scrollIntoView({ behavior: "smooth" });
};

window.removePhone = async function (id, label) {
  if (!confirm(`Remover o número "${label}"?`)) return;
  try {
    await apiFetch(`/admin/phones/${id}`, { method: "DELETE" });
    await loadPhones();
  } catch (e) {
    showFeedback("phone-form-feedback", e.message, "error");
  }
};

// =====================
// WHATSAPP
// =====================

const WA_STATUS_LABELS = {
  disconnected: "Desconectado",
  qr: "Aguardando scan do QR code...",
  connecting: "Conectando...",
  connected: "Conectado",
};

const WA_STATUS_COLORS = {
  disconnected: "var(--error)",
  qr: "#f59e0b",
  connecting: "#f59e0b",
  connected: "var(--success)",
};

let _waPolling = null;

function updateWaUI(status) {
  const indicator = document.getElementById("wa-indicator");
  const statusText = document.getElementById("wa-status-text");
  const qrCard = document.getElementById("qr-card");

  indicator.style.background = WA_STATUS_COLORS[status] || "var(--text-muted)";
  statusText.textContent = WA_STATUS_LABELS[status] || status;

  if (status === "qr") {
    qrCard.style.display = "block";
    loadQr();
  } else {
    qrCard.style.display = "none";
    document.getElementById("qr-image").src = "";
  }
}

async function loadWaStatus() {
  try {
    const data = await apiFetch("/admin/whatsapp/status");
    updateWaUI(data.status);
  } catch {
    updateWaUI("disconnected");
  }
}

async function loadQr() {
  try {
    const data = await apiFetch("/admin/whatsapp/qr");
    document.getElementById("qr-image").src = data.qrDataUrl;
  } catch {
    // QR ainda não disponível
  }
}

function startWaPolling() {
  loadWaStatus();
  _waPolling = setInterval(loadWaStatus, 3000);
}

function stopWaPolling() {
  if (_waPolling) {
    clearInterval(_waPolling);
    _waPolling = null;
  }
}

// =====================
// AUTH
// =====================

function showApp() {
  document.getElementById("auth-screen").style.display = "none";
  document.getElementById("app").style.display = "flex";
  loadModels();
  loadPhones();
}

function init() {
  if (sessionStorage.getItem("admin_token")) {
    showApp();
  }

  document.getElementById("token-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const token = document.getElementById("admin-token").value.trim();
    if (!token) return;
    sessionStorage.setItem("admin_token", token);
    showApp();
  });

  document.getElementById("logout-btn").addEventListener("click", () => {
    sessionStorage.removeItem("admin_token");
    location.reload();
  });

  initNav();
}

document.addEventListener("DOMContentLoaded", init);
