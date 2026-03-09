// platform.js — Plataforma: Sistemas, Auth, Endpoints, Agentes, Import, Simulador
// v4.0.0

import { apiFetch } from "./api.js?v=4.0.0";

// ─── Helpers ─────────────────────────────────────────────────────────────────

function fb(id, msg, type) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = msg;
  el.className = `feedback ${type}`;
  if (type !== "info") setTimeout(() => { el.className = "feedback"; }, 5000);
}

function parseJson(val, label) {
  const s = (val || "").trim();
  if (!s || s === "{}") return {};
  try { return JSON.parse(s); }
  catch { throw new Error(`${label}: JSON inválido`); }
}

function esc(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// ─── State ────────────────────────────────────────────────────────────────────

let sysState = [];
let authState = [];
let epState = [];
let agentState = [];
let aiModelState = [];
let epFilterSys = "";
let editAgentId = null;

// ─── SISTEMAS ─────────────────────────────────────────────────────────────────

async function loadSystems() {
  try {
    const d = await apiFetch("/admin/systems");
    sysState = d.systems || d;
    renderSystems();
  } catch (e) { fb("sys-feedback", e.message, "error"); }
}

function renderSystems() {
  const el = document.getElementById("systems-list");
  if (!el) return;
  if (!sysState.length) {
    el.innerHTML = '<p class="empty-state">Nenhum sistema cadastrado.</p>';
    return;
  }
  el.innerHTML = sysState.map(s => `
    <div class="list-item">
      <div class="list-item__info">
        <span class="list-item__name">${esc(s.name)}</span>
        <span class="list-item__meta">${esc(s.base_url)}</span>
      </div>
      <div class="list-item__actions">
        <button class="btn-icon" onclick="editSys('${s.id}')">✏️</button>
        <button class="btn-icon btn-icon--danger" onclick="delSys('${s.id}','${esc(s.name)}')">🗑️</button>
      </div>
    </div>`).join("");
}

document.getElementById("sys-form")?.addEventListener("submit", async e => {
  e.preventDefault();
  const btn = document.getElementById("save-sys-btn");
  btn.disabled = true;
  const id = document.getElementById("edit-sys-id").value;
  const payload = {
    name: document.getElementById("sys-name").value.trim(),
    base_url: document.getElementById("sys-base-url").value.trim(),
    description: document.getElementById("sys-desc").value.trim() || null,
  };
  try {
    if (id) {
      await apiFetch(`/admin/systems/${id}`, { method: "PUT", body: JSON.stringify(payload) });
      fb("sys-feedback", "Sistema atualizado!", "success");
    } else {
      await apiFetch("/admin/systems", { method: "POST", body: JSON.stringify(payload) });
      fb("sys-feedback", "Sistema cadastrado!", "success");
    }
    resetSysForm();
    await loadSystems();
  } catch (e) { fb("sys-feedback", e.message, "error"); }
  finally { btn.disabled = false; }
});

document.getElementById("cancel-sys-btn")?.addEventListener("click", resetSysForm);

function resetSysForm() {
  document.getElementById("edit-sys-id").value = "";
  document.getElementById("sys-form").reset();
  document.getElementById("sys-form-title").textContent = "Cadastrar sistema";
  document.getElementById("save-sys-btn").textContent = "Cadastrar";
  document.getElementById("cancel-sys-btn").style.display = "none";
}

window.editSys = id => {
  const s = sysState.find(x => x.id === id);
  if (!s) return;
  document.getElementById("edit-sys-id").value = s.id;
  document.getElementById("sys-name").value = s.name;
  document.getElementById("sys-base-url").value = s.base_url;
  document.getElementById("sys-desc").value = s.description || "";
  document.getElementById("sys-form-title").textContent = "Editar sistema";
  document.getElementById("save-sys-btn").textContent = "Salvar alterações";
  document.getElementById("cancel-sys-btn").style.display = "inline-flex";
  document.getElementById("sys-form").scrollIntoView({ behavior: "smooth" });
};

window.delSys = async (id, name) => {
  if (!confirm(`Remover o sistema "${name}"?`)) return;
  try {
    await apiFetch(`/admin/systems/${id}`, { method: "DELETE" });
    await loadSystems();
  } catch (e) { fb("sys-feedback", e.message, "error"); }
};

// ─── AUTH METHODS ─────────────────────────────────────────────────────────────

const AUTH_PLACEHOLDERS = {
  bearer:              '{\n  "token": "seu-token"\n}',
  oauth:               '{\n  "token": "seu-oauth-token"\n}',
  api_key:             '{\n  "location": "header",\n  "name": "X-Api-Key",\n  "value": "sua-chave"\n}',
  basic:               '{\n  "username": "usuario",\n  "password": "senha"\n}',
  custom_header:       '{\n  "headers": {\n    "X-Custom-Header": "valor"\n  }\n}',
  cookie_session:      '{\n  "cookies": {\n    "session": "cookie-value"\n  }\n}',
  reverse_engineering: '{\n  "headers": {"X-Token": "valor"},\n  "cookies": {"session": "cookie"}\n}',
};

async function loadAuth() {
  try {
    const d = await apiFetch("/admin/auth-methods");
    authState = d.auth_methods || d;
    renderAuth();
  } catch (e) { fb("auth-feedback", e.message, "error"); }
}

function renderAuth() {
  const el = document.getElementById("auth-list");
  if (!el) return;
  if (!authState.length) {
    el.innerHTML = '<p class="empty-state">Nenhum método de autenticação cadastrado.</p>';
    return;
  }
  el.innerHTML = authState.map(a => `
    <div class="list-item">
      <div class="list-item__info">
        <span class="list-item__name">${esc(a.name)}</span>
        <span class="list-item__meta">${a.type}</span>
      </div>
      <div class="list-item__actions">
        <button class="btn-icon" onclick="editAuth('${a.id}')">✏️</button>
        <button class="btn-icon btn-icon--danger" onclick="delAuth('${a.id}','${esc(a.name)}')">🗑️</button>
      </div>
    </div>`).join("");
}

document.getElementById("auth-type")?.addEventListener("change", e => {
  const cfg = document.getElementById("auth-config");
  if (!cfg.value.trim() || cfg.value.trim() === "{}") {
    cfg.value = AUTH_PLACEHOLDERS[e.target.value] || "{}";
  }
});

document.getElementById("auth-form")?.addEventListener("submit", async e => {
  e.preventDefault();
  const btn = document.getElementById("save-auth-btn");
  btn.disabled = true;
  const id = document.getElementById("edit-auth-id").value;
  let config;
  try {
    config = parseJson(document.getElementById("auth-config").value, "Configuração");
  } catch (err) {
    fb("auth-feedback", err.message, "error");
    btn.disabled = false;
    return;
  }
  const payload = {
    name: document.getElementById("auth-name").value.trim(),
    type: document.getElementById("auth-type").value,
    config: JSON.stringify(config),  // backend expects JSON string
  };
  try {
    if (id) {
      await apiFetch(`/admin/auth-methods/${id}`, { method: "PUT", body: JSON.stringify(payload) });
      fb("auth-feedback", "Método atualizado!", "success");
    } else {
      await apiFetch("/admin/auth-methods", { method: "POST", body: JSON.stringify(payload) });
      fb("auth-feedback", "Método cadastrado!", "success");
    }
    resetAuthForm();
    await loadAuth();
  } catch (e) { fb("auth-feedback", e.message, "error"); }
  finally { btn.disabled = false; }
});

document.getElementById("cancel-auth-btn")?.addEventListener("click", resetAuthForm);

function resetAuthForm() {
  document.getElementById("edit-auth-id").value = "";
  document.getElementById("auth-form").reset();
  document.getElementById("auth-config").value = "{}";
  document.getElementById("auth-form-title").textContent = "Cadastrar método";
  document.getElementById("save-auth-btn").textContent = "Cadastrar";
  document.getElementById("cancel-auth-btn").style.display = "none";
}

window.editAuth = id => {
  const a = authState.find(x => x.id === id);
  if (!a) return;
  document.getElementById("edit-auth-id").value = a.id;
  document.getElementById("auth-name").value = a.name;
  document.getElementById("auth-type").value = a.type;
  // config is a JSON string in DB — pretty-print for editing
  let cfgStr = AUTH_PLACEHOLDERS[a.type] || "{}";
  if (a.config) {
    try { cfgStr = JSON.stringify(JSON.parse(a.config), null, 2); } catch { cfgStr = a.config; }
  }
  document.getElementById("auth-config").value = cfgStr;
  document.getElementById("auth-form-title").textContent = "Editar método";
  document.getElementById("save-auth-btn").textContent = "Salvar alterações";
  document.getElementById("cancel-auth-btn").style.display = "inline-flex";
  document.getElementById("auth-form").scrollIntoView({ behavior: "smooth" });
};

window.delAuth = async (id, name) => {
  if (!confirm(`Remover o método "${name}"?`)) return;
  try {
    await apiFetch(`/admin/auth-methods/${id}`, { method: "DELETE" });
    await loadAuth();
  } catch (e) { fb("auth-feedback", e.message, "error"); }
};

// ─── ENDPOINTS ────────────────────────────────────────────────────────────────

async function loadEndpoints(sysId) {
  epFilterSys = sysId || "";
  try {
    const url = epFilterSys ? `/admin/endpoints?system_id=${epFilterSys}` : "/admin/endpoints";
    const d = await apiFetch(url);
    epState = d.endpoints || d;
    renderEndpoints();
  } catch (e) { fb("ep-feedback", e.message, "error"); }
}

function renderEndpoints() {
  const el = document.getElementById("ep-list");
  if (!el) return;
  if (!epState.length) {
    el.innerHTML = '<p class="empty-state">Nenhum endpoint cadastrado.</p>';
    return;
  }
  const sysMap = Object.fromEntries(sysState.map(s => [s.id, s.name]));
  el.innerHTML = epState.map(ep => `
    <div class="list-item">
      <div class="list-item__info">
        <span class="list-item__name">
          <span class="method-badge method-${ep.method.toLowerCase()}">${ep.method}</span>
          ${esc(ep.name)}
        </span>
        <span class="list-item__meta">${esc(ep.path)} — ${esc(sysMap[ep.system_id] || ep.system_id)}</span>
      </div>
      <div class="list-item__actions">
        <button class="btn-icon" title="Simular (dry-run)" onclick="simEp('${ep.id}')">⚡</button>
        <button class="btn-icon" title="Executar" onclick="runEp('${ep.id}')">▶</button>
        <button class="btn-icon" title="Editar" onclick="editEp('${ep.id}')">✏️</button>
        <button class="btn-icon btn-icon--danger" title="Remover" onclick="delEp('${ep.id}','${esc(ep.name)}')">🗑️</button>
      </div>
    </div>`).join("");
}

function populateEpFormSelects() {
  const sysEl = document.getElementById("ep-system-id");
  if (sysEl) {
    sysEl.innerHTML = '<option value="">Selecione um sistema...</option>' +
      sysState.map(s => `<option value="${s.id}">${esc(s.name)}</option>`).join("");
  }
  const authEl = document.getElementById("ep-auth-method-id");
  if (authEl) {
    authEl.innerHTML = '<option value="">Sem autenticação</option>' +
      authState.map(a => `<option value="${a.id}">${esc(a.name)} (${a.type})</option>`).join("");
  }
  const filterEl = document.getElementById("ep-filter-sys");
  if (filterEl) {
    filterEl.innerHTML = '<option value="">Todos os sistemas</option>' +
      sysState.map(s => `<option value="${s.id}">${esc(s.name)}</option>`).join("");
    filterEl.value = epFilterSys;
  }
}

document.getElementById("ep-filter-sys")?.addEventListener("change", e => {
  loadEndpoints(e.target.value);
});

document.getElementById("ep-form")?.addEventListener("submit", async e => {
  e.preventDefault();
  const btn = document.getElementById("save-ep-btn");
  btn.disabled = true;
  const id = document.getElementById("edit-ep-id").value;
  let headers, qp, body;
  try {
    headers = parseJson(document.getElementById("ep-headers").value, "Headers");
    qp = parseJson(document.getElementById("ep-query-params").value, "Query params");
    body = parseJson(document.getElementById("ep-body").value, "Body template");
  } catch (err) {
    fb("ep-feedback", err.message, "error");
    btn.disabled = false;
    return;
  }
  const authId = document.getElementById("ep-auth-method-id").value;
  const payload = {
    system_id: document.getElementById("ep-system-id").value,
    name: document.getElementById("ep-name").value.trim(),
    method: document.getElementById("ep-method").value,
    path: document.getElementById("ep-path").value.trim(),
    headers: JSON.stringify(headers),       // backend expects JSON string
    query_params: JSON.stringify(qp),       // backend expects JSON string
    body_template: JSON.stringify(body),    // backend expects JSON string
    auth_method_id: authId || null,
    description: document.getElementById("ep-description").value.trim() || null,
  };
  try {
    if (id) {
      await apiFetch(`/admin/endpoints/${id}`, { method: "PUT", body: JSON.stringify(payload) });
      fb("ep-feedback", "Endpoint atualizado!", "success");
    } else {
      await apiFetch("/admin/endpoints", { method: "POST", body: JSON.stringify(payload) });
      fb("ep-feedback", "Endpoint cadastrado!", "success");
    }
    resetEpForm();
    await loadEndpoints(epFilterSys);
  } catch (e) { fb("ep-feedback", e.message, "error"); }
  finally { btn.disabled = false; }
});

document.getElementById("cancel-ep-btn")?.addEventListener("click", resetEpForm);

function resetEpForm() {
  document.getElementById("edit-ep-id").value = "";
  document.getElementById("ep-form").reset();
  document.getElementById("ep-headers").value = "{}";
  document.getElementById("ep-query-params").value = "{}";
  document.getElementById("ep-body").value = "{}";
  document.getElementById("ep-form-title").textContent = "Cadastrar endpoint";
  document.getElementById("save-ep-btn").textContent = "Cadastrar";
  document.getElementById("cancel-ep-btn").style.display = "none";
}

window.editEp = async id => {
  try {
    const ep = await apiFetch(`/admin/endpoints/${id}`);
    document.getElementById("edit-ep-id").value = ep.id;
    document.getElementById("ep-system-id").value = ep.system_id;
    document.getElementById("ep-name").value = ep.name;
    document.getElementById("ep-method").value = ep.method;
    document.getElementById("ep-path").value = ep.path;
    // headers/query_params/body_template are JSON strings in the DB — pretty-print for editing
    const prettyJson = (s) => { try { return JSON.stringify(JSON.parse(s || "{}"), null, 2); } catch { return s || "{}"; } };
    document.getElementById("ep-headers").value = prettyJson(ep.headers);
    document.getElementById("ep-query-params").value = prettyJson(ep.query_params);
    document.getElementById("ep-body").value = prettyJson(ep.body_template);
    document.getElementById("ep-auth-method-id").value = ep.auth_method_id || "";
    document.getElementById("ep-description").value = ep.description || "";
    document.getElementById("ep-form-title").textContent = "Editar endpoint";
    document.getElementById("save-ep-btn").textContent = "Salvar alterações";
    document.getElementById("cancel-ep-btn").style.display = "inline-flex";
    document.getElementById("ep-form").scrollIntoView({ behavior: "smooth" });
  } catch (e) { fb("ep-feedback", e.message, "error"); }
};

window.delEp = async (id, name) => {
  if (!confirm(`Remover o endpoint "${name}"?`)) return;
  try {
    await apiFetch(`/admin/endpoints/${id}`, { method: "DELETE" });
    await loadEndpoints(epFilterSys);
  } catch (e) { fb("ep-feedback", e.message, "error"); }
};

window.simEp = async id => {
  const ep = epState.find(x => x.id === id);
  const raw = prompt(`Parâmetros para simular "${ep?.name || id}" (JSON):`, "{}");
  if (raw === null) return;
  try {
    const params = JSON.parse(raw || "{}");
    const r = await apiFetch(`/admin/endpoints/${id}/simulate`, {
      method: "POST",
      body: JSON.stringify({ params }),
    });
    alert("Requisição que seria enviada:\n\n" + JSON.stringify(r, null, 2));
  } catch (e) { alert("Erro: " + e.message); }
};

window.runEp = async id => {
  const ep = epState.find(x => x.id === id);
  const raw = prompt(`Parâmetros para executar "${ep?.name || id}" (JSON):`, "{}");
  if (raw === null) return;
  try {
    const params = JSON.parse(raw || "{}");
    const r = await apiFetch(`/admin/endpoints/${id}/execute`, {
      method: "POST",
      body: JSON.stringify({ params }),
    });
    alert(`Status: ${r.status_code}\n\n${JSON.stringify(r.body, null, 2)}`);
  } catch (e) { alert("Erro: " + e.message); }
};

// ─── AGENTS ───────────────────────────────────────────────────────────────────

async function loadAgents() {
  try {
    const d = await apiFetch("/admin/agents");
    agentState = d.agents || d;
    renderAgents();
  } catch (e) { fb("agent-feedback", e.message, "error"); }
}

function renderAgents() {
  const el = document.getElementById("agents-list");
  if (!el) return;
  if (!agentState.length) {
    el.innerHTML = '<p class="empty-state">Nenhum agente cadastrado.</p>';
    return;
  }
  el.innerHTML = agentState.map(a => `
    <div class="list-item">
      <div class="list-item__info">
        <span class="list-item__name">
          ${esc(a.name)}
          ${a.is_active ? '<span class="badge badge--active">Ativo</span>' : '<span class="badge badge--warning">Inativo</span>'}
          <span class="badge">${a.type}</span>
        </span>
        <span class="list-item__meta">${(a.endpoint_ids || []).length} endpoint(s) vinculado(s)</span>
      </div>
      <div class="list-item__actions">
        <button class="btn-sm" onclick="testAgent('${a.id}','${esc(a.name)}')">Testar</button>
        <button class="btn-icon" title="Editar" onclick="editAgent('${a.id}')">✏️</button>
        <button class="btn-icon btn-icon--danger" title="Remover" onclick="delAgent('${a.id}','${esc(a.name)}')">🗑️</button>
      </div>
    </div>`).join("");
}

async function loadAiModels() {
  try {
    const d = await apiFetch("/admin/ai-models");
    aiModelState = d.models || [];
  } catch { /* ignore */ }
}

function populateAgentFormSelects() {
  const modelEl = document.getElementById("agent-model-id");
  if (modelEl) {
    modelEl.innerHTML = '<option value="">Usar modelo padrão da plataforma</option>' +
      aiModelState.map(m => `<option value="${m.id}">${esc(m.name)} (${m.provider})</option>`).join("");
  }
}

document.getElementById("agent-form")?.addEventListener("submit", async e => {
  e.preventDefault();
  const btn = document.getElementById("save-agent-btn");
  btn.disabled = true;
  const id = document.getElementById("edit-agent-id").value;
  const payload = {
    name: document.getElementById("agent-name").value.trim(),
    description: document.getElementById("agent-description").value.trim() || null,
    type: document.getElementById("agent-type").value,
    is_active: document.getElementById("agent-is-active").checked,
    system_prompt: document.getElementById("agent-system-prompt").value.trim() || null,
    ai_model_id: document.getElementById("agent-model-id").value || null,
  };
  try {
    let savedId = id;
    if (id) {
      await apiFetch(`/admin/agents/${id}`, { method: "PUT", body: JSON.stringify(payload) });
      fb("agent-feedback", "Agente atualizado!", "success");
    } else {
      const r = await apiFetch("/admin/agents", { method: "POST", body: JSON.stringify(payload) });
      savedId = r.id;
      fb("agent-feedback", "Agente cadastrado! Configure os endpoints abaixo.", "success");
      document.getElementById("edit-agent-id").value = savedId;
      document.getElementById("agent-form-title").textContent = "Editar agente";
      document.getElementById("save-agent-btn").textContent = "Salvar alterações";
      document.getElementById("cancel-agent-btn").style.display = "inline-flex";
    }
    editAgentId = savedId;
    await loadAgents();
    showAgentEndpoints(savedId);
  } catch (e) { fb("agent-feedback", e.message, "error"); }
  finally { btn.disabled = false; }
});

document.getElementById("cancel-agent-btn")?.addEventListener("click", () => {
  resetAgentForm();
  hideAgentEndpoints();
});

function resetAgentForm() {
  document.getElementById("edit-agent-id").value = "";
  document.getElementById("agent-form").reset();
  document.getElementById("agent-is-active").checked = true;
  document.getElementById("agent-form-title").textContent = "Cadastrar agente";
  document.getElementById("save-agent-btn").textContent = "Cadastrar";
  document.getElementById("cancel-agent-btn").style.display = "none";
  editAgentId = null;
}

window.editAgent = async id => {
  try {
    const a = await apiFetch(`/admin/agents/${id}`);
    document.getElementById("edit-agent-id").value = a.id;
    document.getElementById("agent-name").value = a.name;
    document.getElementById("agent-description").value = a.description || "";
    document.getElementById("agent-type").value = a.type;
    document.getElementById("agent-is-active").checked = a.is_active;
    document.getElementById("agent-system-prompt").value = a.system_prompt || "";
    document.getElementById("agent-model-id").value = a.ai_model_id || "";
    document.getElementById("agent-form-title").textContent = "Editar agente";
    document.getElementById("save-agent-btn").textContent = "Salvar alterações";
    document.getElementById("cancel-agent-btn").style.display = "inline-flex";
    document.getElementById("agent-form").scrollIntoView({ behavior: "smooth" });
    showAgentEndpoints(a.id, a.endpoint_ids || []);
  } catch (e) { fb("agent-feedback", e.message, "error"); }
};

window.delAgent = async (id, name) => {
  if (!confirm(`Remover o agente "${name}"?`)) return;
  try {
    await apiFetch(`/admin/agents/${id}`, { method: "DELETE" });
    resetAgentForm();
    hideAgentEndpoints();
    await loadAgents();
  } catch (e) { fb("agent-feedback", e.message, "error"); }
};

function showAgentEndpoints(agentId, currentIds = []) {
  editAgentId = agentId;
  const card = document.getElementById("agent-ep-card");
  if (!card) return;
  card.style.display = "block";
  const container = document.getElementById("agent-ep-checklist");
  const sysMap = Object.fromEntries(sysState.map(s => [s.id, s.name]));
  if (!epState.length) {
    container.innerHTML = '<p class="empty-state">Nenhum endpoint disponível. Cadastre endpoints primeiro.</p>';
  } else {
    container.innerHTML = epState.map(ep => `
      <label class="ep-check-label">
        <input type="checkbox" name="agent-ep" value="${ep.id}" ${currentIds.includes(ep.id) ? "checked" : ""} />
        <span class="method-badge method-${ep.method.toLowerCase()}">${ep.method}</span>
        ${esc(ep.name)}
        <span class="ep-check-sys">(${esc(sysMap[ep.system_id] || "?")})</span>
      </label>`).join("");
  }
  card.scrollIntoView({ behavior: "smooth" });
}

function hideAgentEndpoints() {
  const card = document.getElementById("agent-ep-card");
  if (card) card.style.display = "none";
  editAgentId = null;
}

document.getElementById("save-agent-ep-btn")?.addEventListener("click", async () => {
  if (!editAgentId) return;
  const checked = Array.from(document.querySelectorAll('input[name="agent-ep"]:checked')).map(c => c.value);
  try {
    await apiFetch(`/admin/agents/${editAgentId}/endpoints`, {
      method: "PUT",
      body: JSON.stringify({ endpoint_ids: checked }),
    });
    fb("agent-ep-feedback", `${checked.length} endpoint(s) vinculado(s)!`, "success");
    await loadAgents();
  } catch (e) { fb("agent-ep-feedback", e.message, "error"); }
});

window.testAgent = (id, name) => {
  const card = document.getElementById("agent-test-card");
  if (!card) return;
  document.getElementById("agent-test-id").value = id;
  document.getElementById("agent-test-title").textContent = `Testar agente: ${name}`;
  document.getElementById("agent-test-msg").value = "";
  document.getElementById("agent-test-result").className = "result-box";
  card.style.display = "block";
  card.scrollIntoView({ behavior: "smooth" });
};

document.getElementById("agent-test-form")?.addEventListener("submit", async e => {
  e.preventDefault();
  const btn = document.getElementById("agent-test-btn");
  btn.disabled = true;
  btn.textContent = "Processando...";
  const id = document.getElementById("agent-test-id").value;
  const message = document.getElementById("agent-test-msg").value.trim();
  const resBox = document.getElementById("agent-test-result");
  try {
    fb("agent-test-feedback", "Executando agente...", "info");
    const r = await apiFetch(`/admin/agents/${id}/run`, {
      method: "POST",
      body: JSON.stringify({ message }),
    });
    const reply = r.response || r.reply || r.message || JSON.stringify(r, null, 2);
    resBox.textContent = reply;
    resBox.className = "result-box visible";
    document.getElementById("agent-test-feedback").className = "feedback";
  } catch (e) {
    fb("agent-test-feedback", e.message, "error");
    resBox.className = "result-box";
  } finally {
    btn.disabled = false;
    btn.textContent = "Enviar";
  }
});

// ─── IMPORT ───────────────────────────────────────────────────────────────────

function populateImportSysSelects() {
  ["import-sys-postman", "import-sys-openapi", "import-sys-curl"].forEach(elId => {
    const el = document.getElementById(elId);
    if (!el) return;
    el.innerHTML = '<option value="">Selecione um sistema...</option>' +
      sysState.map(s => `<option value="${s.id}">${esc(s.name)}</option>`).join("");
  });
}

// Tab switching
document.querySelectorAll(".tab-btn[data-group][data-tab]").forEach(btn => {
  btn.addEventListener("click", () => {
    const group = btn.dataset.group;
    const tab = btn.dataset.tab;
    document.querySelectorAll(`.tab-btn[data-group="${group}"]`).forEach(b => b.classList.remove("tab-btn--active"));
    btn.classList.add("tab-btn--active");
    document.querySelectorAll(`.tab-pane[data-group="${group}"]`).forEach(p => {
      p.style.display = p.dataset.tab === tab ? "block" : "none";
    });
  });
});

document.getElementById("import-postman-form")?.addEventListener("submit", async e => {
  e.preventDefault();
  const btn = document.getElementById("import-postman-btn");
  btn.disabled = true;
  const file = document.getElementById("import-postman-file").files[0];
  const sysId = document.getElementById("import-sys-postman").value;
  if (!file || !sysId) {
    fb("import-postman-feedback", "Selecione o arquivo e o sistema.", "error");
    btn.disabled = false;
    return;
  }
  try {
    const text = await file.text();
    const collection = JSON.parse(text);
    fb("import-postman-feedback", "Importando...", "info");
    const r = await apiFetch("/admin/import/postman", {
      method: "POST",
      body: JSON.stringify({ system_id: sysId, collection }),
    });
    let msg = `✓ ${r.created} criado(s), ${r.skipped} erro(s).`;
    if (r.errors?.length) msg += " | " + r.errors.slice(0, 3).join("; ");
    fb("import-postman-feedback", msg, "success");
  } catch (e) { fb("import-postman-feedback", e.message, "error"); }
  finally { btn.disabled = false; }
});

document.getElementById("import-openapi-form")?.addEventListener("submit", async e => {
  e.preventDefault();
  const btn = document.getElementById("import-openapi-btn");
  btn.disabled = true;
  const file = document.getElementById("import-openapi-file").files[0];
  const sysId = document.getElementById("import-sys-openapi").value;
  if (!file || !sysId) {
    fb("import-openapi-feedback", "Selecione o arquivo e o sistema.", "error");
    btn.disabled = false;
    return;
  }
  try {
    const text = await file.text();
    const spec = JSON.parse(text);
    fb("import-openapi-feedback", "Importando...", "info");
    const r = await apiFetch("/admin/import/openapi", {
      method: "POST",
      body: JSON.stringify({ system_id: sysId, spec }),
    });
    let msg = `✓ ${r.created} criado(s), ${r.skipped} erro(s).`;
    if (r.base_url_hint) msg += ` Base URL sugerida: ${r.base_url_hint}`;
    if (r.errors?.length) msg += " | " + r.errors.slice(0, 3).join("; ");
    fb("import-openapi-feedback", msg, "success");
  } catch (e) { fb("import-openapi-feedback", e.message, "error"); }
  finally { btn.disabled = false; }
});

document.getElementById("preview-curl-btn")?.addEventListener("click", async () => {
  const curl = document.getElementById("import-curl-text").value.trim();
  if (!curl) return;
  try {
    const r = await apiFetch("/admin/import/curl/preview", {
      method: "POST",
      body: JSON.stringify({ curl }),
    });
    fb("import-curl-feedback",
      `Preview: ${r.method} ${r.url || r.path} | headers: ${JSON.stringify(r.headers || {})}`,
      "info");
  } catch (e) { fb("import-curl-feedback", e.message, "error"); }
});

document.getElementById("import-curl-form")?.addEventListener("submit", async e => {
  e.preventDefault();
  const btn = document.getElementById("import-curl-btn");
  btn.disabled = true;
  const sysId = document.getElementById("import-sys-curl").value;
  const name = document.getElementById("import-curl-name").value.trim();
  const curl = document.getElementById("import-curl-text").value.trim();
  if (!sysId || !curl) {
    fb("import-curl-feedback", "Preencha o sistema e o comando CURL.", "error");
    btn.disabled = false;
    return;
  }
  try {
    fb("import-curl-feedback", "Importando...", "info");
    const r = await apiFetch("/admin/import/curl", {
      method: "POST",
      body: JSON.stringify({ system_id: sysId, name, curl }),
    });
    fb("import-curl-feedback", `✓ Endpoint criado: ${r.method} ${r.path}`, "success");
  } catch (e) { fb("import-curl-feedback", e.message, "error"); }
  finally { btn.disabled = false; }
});

// ─── SIMULATOR ────────────────────────────────────────────────────────────────

function populateSimSelects() {
  const epEl = document.getElementById("sim-endpoint-id");
  if (epEl) {
    const sysMap = Object.fromEntries(sysState.map(s => [s.id, s.name]));
    epEl.innerHTML = '<option value="">Selecione um endpoint...</option>' +
      epState.map(ep => `<option value="${ep.id}">[${ep.method}] ${esc(ep.name)} (${esc(sysMap[ep.system_id] || "?")})</option>`).join("");
  }
  const authEl = document.getElementById("sim-raw-auth-id");
  if (authEl) {
    authEl.innerHTML = '<option value="">Sem autenticação</option>' +
      authState.map(a => `<option value="${a.id}">${esc(a.name)} (${a.type})</option>`).join("");
  }
}

document.getElementById("sim-ep-form")?.addEventListener("submit", async e => {
  e.preventDefault();
  const btn = document.getElementById("sim-ep-btn");
  btn.disabled = true;
  const id = document.getElementById("sim-endpoint-id").value;
  const isDryRun = document.getElementById("sim-ep-dry-run").checked;
  let params;
  try { params = parseJson(document.getElementById("sim-ep-params").value, "Params"); }
  catch (err) { fb("sim-ep-feedback", err.message, "error"); btn.disabled = false; return; }

  const resBox = document.getElementById("sim-ep-result");
  btn.textContent = isDryRun ? "Simulando..." : "Executando...";
  try {
    fb("sim-ep-feedback", isDryRun ? "Simulando (dry-run)..." : "Executando...", "info");
    const path = isDryRun ? `/admin/endpoints/${id}/simulate` : `/admin/endpoints/${id}/execute`;
    const r = await apiFetch(path, { method: "POST", body: JSON.stringify({ params }) });
    resBox.textContent = JSON.stringify(r, null, 2);
    resBox.className = "result-box visible";
    document.getElementById("sim-ep-feedback").className = "feedback";
  } catch (e) {
    fb("sim-ep-feedback", e.message, "error");
    resBox.className = "result-box";
  } finally {
    btn.disabled = false;
    btn.textContent = "Executar";
  }
});

document.getElementById("sim-raw-form")?.addEventListener("submit", async e => {
  e.preventDefault();
  const btn = document.getElementById("sim-raw-btn");
  btn.disabled = true;
  btn.textContent = "Enviando...";
  let headers, qp, body;
  try {
    headers = parseJson(document.getElementById("sim-raw-headers").value, "Headers");
    qp = parseJson(document.getElementById("sim-raw-qp").value, "Query params");
    body = parseJson(document.getElementById("sim-raw-body").value, "Body");
  } catch (err) {
    fb("sim-raw-feedback", err.message, "error");
    btn.disabled = false;
    btn.textContent = "Enviar";
    return;
  }
  const payload = {
    method: document.getElementById("sim-raw-method").value,
    url: document.getElementById("sim-raw-url").value.trim(),
    headers,
    query_params: qp,
    body: Object.keys(body).length ? body : null,
    auth_method_id: document.getElementById("sim-raw-auth-id").value || null,
  };
  const resBox = document.getElementById("sim-raw-result");
  try {
    fb("sim-raw-feedback", "Enviando requisição...", "info");
    const r = await apiFetch("/admin/simulate/raw", { method: "POST", body: JSON.stringify(payload) });
    resBox.textContent = JSON.stringify(r, null, 2);
    resBox.className = "result-box visible";
    document.getElementById("sim-raw-feedback").className = "feedback";
  } catch (e) {
    fb("sim-raw-feedback", e.message, "error");
    resBox.className = "result-box";
  } finally {
    btn.disabled = false;
    btn.textContent = "Enviar";
  }
});

// ─── Section loader ───────────────────────────────────────────────────────────

async function loadPlatformSection(section) {
  if (section === "systems") {
    await loadSystems();
  } else if (section === "auth") {
    await loadAuth();
  } else if (section === "endpoints") {
    await Promise.all([loadSystems(), loadAuth()]);
    await loadEndpoints(epFilterSys);
    populateEpFormSelects();
  } else if (section === "agents") {
    await Promise.all([loadSystems(), loadAuth(), loadAiModels()]);
    await loadEndpoints(epFilterSys);
    await loadAgents();
    populateAgentFormSelects();
  } else if (section === "import") {
    await loadSystems();
    populateImportSysSelects();
  } else if (section === "simulator") {
    await Promise.all([loadSystems(), loadAuth()]);
    await loadEndpoints(epFilterSys);
    populateSimSelects();
  } else if (section === "history") {
    await loadHistoryUsers(1);
  }
}

// ─── Histórico ───────────────────────────────────────────────────────────────

let _historyUserPage = 1;
let _historyAgentPage = 1;

function _fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

async function loadHistoryUsers(page = 1) {
  _historyUserPage = page;
  const el = document.getElementById("history-user-list");
  el.innerHTML = "<p class='empty-state'>Carregando...</p>";
  try {
    const data = await apiFetch(`/admin/logs/user?page=${page}&per_page=20`);
    if (!data.logs || data.logs.length === 0) {
      el.innerHTML = "<p class='empty-state'>Nenhuma interação registrada ainda.</p>";
      document.getElementById("history-user-pagination").innerHTML = "";
      return;
    }
    el.innerHTML = data.logs.map(log => `
      <div style="border:1px solid var(--border);border-radius:8px;padding:12px 16px;margin-bottom:10px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
          <span style="font-weight:600;font-size:0.85rem;">${esc(log.phone)}</span>
          <span style="font-size:0.75rem;color:var(--text-secondary);">${_fmtDate(log.created_at)} · ${log.duration_ms}ms${log.agent_name ? " · " + esc(log.agent_name) : ""}</span>
        </div>
        <div style="margin-bottom:6px;"><span style="font-size:0.75rem;color:var(--text-secondary);">Mensagem</span><br/><span style="white-space:pre-wrap;word-break:break-word;">${esc(log.user_message)}</span></div>
        <div style="background:var(--bg-secondary);border-radius:6px;padding:8px 10px;white-space:pre-wrap;word-break:break-word;font-size:0.875rem;">${esc(log.final_response || "(sem resposta)")}</div>
      </div>
    `).join("");
    _renderPagination("history-user-pagination", page, data.total, 20, loadHistoryUsers);
  } catch (e) {
    el.innerHTML = `<p class='empty-state' style='color:var(--error);'>${esc(String(e))}</p>`;
  }
}

async function loadHistoryAgents(page = 1) {
  _historyAgentPage = page;
  const el = document.getElementById("history-agent-list");
  el.innerHTML = "<p class='empty-state'>Carregando...</p>";
  try {
    const data = await apiFetch(`/admin/logs/agent?page=${page}&per_page=20`);
    if (!data.logs || data.logs.length === 0) {
      el.innerHTML = "<p class='empty-state'>Nenhuma interação com tool calls registrada.</p>";
      document.getElementById("history-agent-pagination").innerHTML = "";
      return;
    }
    el.innerHTML = data.logs.map(log => {
      let toolCalls = [];
      try { toolCalls = JSON.parse(log.tool_calls || "[]"); } catch (_) {}
      const toolsHtml = toolCalls.length === 0 ? "" : `
        <div style="margin-top:8px;">
          <span style="font-size:0.75rem;color:var(--text-secondary);">Tool calls (${toolCalls.length})</span>
          ${toolCalls.map((tc, i) => `
            <div style="background:var(--bg-secondary);border-radius:6px;padding:8px 10px;margin-top:4px;font-size:0.8rem;">
              <div style="font-weight:600;margin-bottom:2px;">${i + 1}. ${esc(tc.tool_name || "")}</div>
              <div style="color:var(--text-secondary);margin-bottom:2px;">Params: <code style="font-size:0.75rem;">${esc(JSON.stringify(tc.params || {}))}</code></div>
              ${tc.error ? `<div style="color:var(--error);">Erro: ${esc(tc.error)}</div>` : `<div style="max-height:80px;overflow:auto;word-break:break-all;color:var(--text-secondary);">${esc((tc.result || "").substring(0, 300))}${(tc.result || "").length > 300 ? "…" : ""}</div>`}
            </div>
          `).join("")}
        </div>`;
      return `
        <div style="border:1px solid var(--border);border-radius:8px;padding:12px 16px;margin-bottom:10px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
            <span style="font-weight:600;font-size:0.85rem;">${esc(log.phone)}</span>
            <span style="font-size:0.75rem;color:var(--text-secondary);">${_fmtDate(log.created_at)} · ${log.duration_ms}ms · ${esc(log.agent_name || "")}</span>
          </div>
          <div style="margin-bottom:4px;font-size:0.875rem;">${esc(log.user_message)}</div>
          ${toolsHtml}
          <div style="background:var(--bg-secondary);border-radius:6px;padding:8px 10px;white-space:pre-wrap;word-break:break-word;font-size:0.875rem;margin-top:8px;">${esc(log.final_response || "(sem resposta)")}</div>
        </div>`;
    }).join("");
    _renderPagination("history-agent-pagination", page, data.total, 20, loadHistoryAgents);
  } catch (e) {
    el.innerHTML = `<p class='empty-state' style='color:var(--error);'>${esc(String(e))}</p>`;
  }
}

function _renderPagination(containerId, currentPage, total, perPage, loadFn) {
  const container = document.getElementById(containerId);
  const totalPages = Math.ceil(total / perPage);
  if (totalPages <= 1) { container.innerHTML = ""; return; }
  container.innerHTML = `
    <button class="btn btn-ghost" style="padding:4px 10px;" ${currentPage <= 1 ? "disabled" : ""} data-page="${currentPage - 1}">‹ Anterior</button>
    <span style="font-size:0.85rem;color:var(--text-secondary);">Página ${currentPage} de ${totalPages} (${total} registros)</span>
    <button class="btn btn-ghost" style="padding:4px 10px;" ${currentPage >= totalPages ? "disabled" : ""} data-page="${currentPage + 1}">Próxima ›</button>
  `;
  container.querySelectorAll("button[data-page]").forEach(btn => {
    btn.addEventListener("click", () => loadFn(Number(btn.dataset.page)));
  });
}

// Tabs do histórico
document.querySelectorAll('.tab-btn[data-group="history"]').forEach(btn => {
  btn.addEventListener("click", async () => {
    const tab = btn.dataset.tab;
    document.querySelectorAll('.tab-btn[data-group="history"]').forEach(b => b.classList.remove("tab-btn--active"));
    btn.classList.add("tab-btn--active");
    document.querySelectorAll('.tab-pane[data-group="history"]').forEach(p => {
      p.style.display = p.dataset.tab === tab ? "" : "none";
    });
    if (tab === "users") await loadHistoryUsers(1);
    else if (tab === "agents") await loadHistoryAgents(1);
  });
});

// ─── Navigation hook ─────────────────────────────────────────────────────────

const PLATFORM_SECTIONS = new Set(["systems", "auth", "endpoints", "agents", "import", "simulator", "history"]);

document.querySelectorAll(".nav-item").forEach(btn => {
  btn.addEventListener("click", () => {
    const section = btn.dataset.section;
    if (PLATFORM_SECTIONS.has(section)) {
      loadPlatformSection(section);
    }
  });
});
