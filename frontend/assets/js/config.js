import { apiFetch } from "./api.js";

const MODEL_SUGGESTIONS = {
  openai: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
  anthropic: ["claude-sonnet-4-6", "claude-haiku-4-5-20251001", "claude-opus-4-6"],
  groq: ["llama3-70b-8192", "llama3-8b-8192", "mixtral-8x7b-32768", "gemma2-9b-it"],
  google: ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
  openrouter: [],
};

function showFeedback(msg, type) {
  const el = document.getElementById("feedback");
  el.textContent = msg;
  el.className = `feedback ${type}`;
}

function updateModelSuggestions(provider) {
  const datalist = document.getElementById("model-suggestions");
  datalist.innerHTML = "";
  const suggestions = MODEL_SUGGESTIONS[provider] || [];
  suggestions.forEach((m) => {
    const opt = document.createElement("option");
    opt.value = m;
    datalist.appendChild(opt);
  });
}

async function loadConfig() {
  try {
    const data = await apiFetch("/admin/ai-config");
    document.getElementById("provider").value = data.provider || "";
    document.getElementById("model").value = data.model || "";
    document.getElementById("api-key").placeholder =
      data.api_key === "***" ? "Chave salva — deixe em branco para manter" : "Insira a chave de API";
    updateModelSuggestions(data.provider);
  } catch (e) {
    showFeedback(e.message, "error");
  }
}

async function saveConfig(e) {
  e.preventDefault();
  const btn = document.getElementById("save-btn");
  btn.disabled = true;
  btn.textContent = "Salvando...";

  const provider = document.getElementById("provider").value.trim();
  const model = document.getElementById("model").value.trim();
  const apiKey = document.getElementById("api-key").value.trim();

  try {
    await apiFetch("/admin/ai-config", {
      method: "POST",
      body: JSON.stringify({ provider, model, api_key: apiKey }),
    });
    showFeedback("Configuração salva com sucesso!", "success");
    document.getElementById("api-key").value = "";
    document.getElementById("api-key").placeholder = "Chave salva — deixe em branco para manter";
  } catch (e) {
    showFeedback(e.message, "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Salvar configuração";
  }
}

function init() {
  const savedToken = sessionStorage.getItem("admin_token");
  if (savedToken) {
    document.getElementById("token-section").style.display = "none";
    document.getElementById("config-section").style.display = "block";
    loadConfig();
  }

  document.getElementById("token-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const token = document.getElementById("admin-token").value.trim();
    if (!token) return;
    sessionStorage.setItem("admin_token", token);
    document.getElementById("token-section").style.display = "none";
    document.getElementById("config-section").style.display = "block";
    loadConfig();
  });

  document.getElementById("provider").addEventListener("change", (e) => {
    updateModelSuggestions(e.target.value);
    document.getElementById("model").value = "";
  });

  document.getElementById("config-form").addEventListener("submit", saveConfig);

  document.getElementById("logout-btn").addEventListener("click", () => {
    sessionStorage.removeItem("admin_token");
    location.reload();
  });
}

document.addEventListener("DOMContentLoaded", init);
