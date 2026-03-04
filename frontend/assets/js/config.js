import { apiFetch } from "./api.js";

const MODEL_SUGGESTIONS = {
  openai: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
  anthropic: ["claude-sonnet-4-6", "claude-haiku-4-5-20251001", "claude-opus-4-6"],
  groq: ["llama3-70b-8192", "llama3-8b-8192", "mixtral-8x7b-32768", "gemma2-9b-it"],
  google: ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
  openrouter: [],
};

let state = { models: [], active_id: null };

// --- Feedback ---

function showFeedback(elId, msg, type) {
  const el = document.getElementById(elId);
  el.textContent = msg;
  el.className = `feedback ${type}`;
  setTimeout(() => { el.className = "feedback"; }, 4000);
}

// --- Model suggestions ---

function updateModelSuggestions(provider) {
  const datalist = document.getElementById("model-suggestions");
  datalist.innerHTML = "";
  (MODEL_SUGGESTIONS[provider] || []).forEach((m) => {
    const opt = document.createElement("option");
    opt.value = m;
    datalist.appendChild(opt);
  });
}

// --- Render models list ---

function renderModels() {
  const list = document.getElementById("models-list");
  const select = document.getElementById("active-select");

  // Update active select
  select.innerHTML = '<option value="">— Selecione um modelo —</option>';
  state.models.forEach((m) => {
    const opt = document.createElement("option");
    opt.value = m.id;
    opt.textContent = `${m.name} (${m.provider} / ${m.model})`;
    if (m.id === state.active_id) opt.selected = true;
    select.appendChild(opt);
  });

  // Update list
  if (state.models.length === 0) {
    list.innerHTML = '<p class="empty-state">Nenhum modelo cadastrado ainda.</p>';
    return;
  }

  list.innerHTML = state.models.map((m) => `
    <div class="model-item ${m.id === state.active_id ? "model-item--active" : ""}">
      <div class="model-item__info">
        <span class="model-item__name">${m.name}</span>
        ${m.id === state.active_id ? '<span class="badge badge--active">Ativo</span>' : ""}
        <span class="model-item__meta">${m.provider} / ${m.model}</span>
      </div>
      <div class="model-item__actions">
        <button class="btn-icon" title="Editar" onclick="editModel('${m.id}')">✏️</button>
        <button class="btn-icon btn-icon--danger" title="Remover" onclick="removeModel('${m.id}', '${m.name}')">🗑️</button>
      </div>
    </div>
  `).join("");
}

// --- Load ---

async function loadModels() {
  try {
    const data = await apiFetch("/admin/ai-models");
    state = data;
    renderModels();
  } catch (e) {
    showFeedback("active-feedback", e.message, "error");
  }
}

// --- Activate ---

document.getElementById("activate-btn").addEventListener("click", async () => {
  const id = document.getElementById("active-select").value;
  if (!id) return;
  try {
    await apiFetch(`/admin/ai-models/${id}/activate`, { method: "PUT" });
    state.active_id = id;
    renderModels();
    showFeedback("active-feedback", "Modelo ativo atualizado!", "success");
  } catch (e) {
    showFeedback("active-feedback", e.message, "error");
  }
});

// --- Form: cadastrar / editar ---

document.getElementById("provider").addEventListener("change", (e) => {
  updateModelSuggestions(e.target.value);
  document.getElementById("model").value = "";
});

document.getElementById("model-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = document.getElementById("save-btn");
  btn.disabled = true;

  const id = document.getElementById("edit-id").value;
  const payload = {
    name: document.getElementById("name").value.trim(),
    provider: document.getElementById("provider").value,
    model: document.getElementById("model").value.trim(),
    api_key: document.getElementById("api-key").value.trim(),
  };

  try {
    if (id) {
      await apiFetch(`/admin/ai-models/${id}`, { method: "PUT", body: JSON.stringify(payload) });
      showFeedback("form-feedback", "Modelo atualizado!", "success");
    } else {
      await apiFetch("/admin/ai-models", { method: "POST", body: JSON.stringify(payload) });
      showFeedback("form-feedback", "Modelo cadastrado!", "success");
    }
    resetForm();
    await loadModels();
  } catch (e) {
    showFeedback("form-feedback", e.message, "error");
  } finally {
    btn.disabled = false;
  }
});

document.getElementById("cancel-btn").addEventListener("click", resetForm);

function resetForm() {
  document.getElementById("edit-id").value = "";
  document.getElementById("model-form").reset();
  document.getElementById("form-title").textContent = "Cadastrar modelo";
  document.getElementById("save-btn").textContent = "Cadastrar";
  document.getElementById("cancel-btn").style.display = "none";
  document.getElementById("key-hint").style.display = "none";
  document.getElementById("api-key").placeholder = "Insira a chave de API";
}

// --- Edit / Remove (global functions for inline onclick) ---

window.editModel = function (id) {
  const m = state.models.find((m) => m.id === id);
  if (!m) return;

  document.getElementById("edit-id").value = m.id;
  document.getElementById("name").value = m.name;
  document.getElementById("provider").value = m.provider;
  updateModelSuggestions(m.provider);
  document.getElementById("model").value = m.model;
  document.getElementById("api-key").value = "";
  document.getElementById("api-key").placeholder = "Deixe em branco para manter a chave atual";
  document.getElementById("key-hint").style.display = "block";
  document.getElementById("form-title").textContent = "Editar modelo";
  document.getElementById("save-btn").textContent = "Salvar alterações";
  document.getElementById("cancel-btn").style.display = "inline-flex";

  document.getElementById("model-form").scrollIntoView({ behavior: "smooth" });
};

window.removeModel = async function (id, name) {
  if (!confirm(`Remover o modelo "${name}"?`)) return;
  try {
    await apiFetch(`/admin/ai-models/${id}`, { method: "DELETE" });
    await loadModels();
  } catch (e) {
    showFeedback("form-feedback", e.message, "error");
  }
};

// --- Auth ---

function init() {
  const savedToken = sessionStorage.getItem("admin_token");
  if (savedToken) {
    showPanel();
  }

  document.getElementById("token-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const token = document.getElementById("admin-token").value.trim();
    if (!token) return;
    sessionStorage.setItem("admin_token", token);
    showPanel();
  });

  document.getElementById("logout-btn").addEventListener("click", () => {
    sessionStorage.removeItem("admin_token");
    location.reload();
  });
}

function showPanel() {
  document.getElementById("token-section").style.display = "none";
  document.getElementById("main-section").style.display = "block";
  loadModels();
}

document.addEventListener("DOMContentLoaded", init);
