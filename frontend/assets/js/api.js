const API_BASE = "/api/v1";

function getToken() {
  return sessionStorage.getItem("admin_token") || "";
}

async function apiFetch(path, options = {}) {
  const token = getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    signal: AbortSignal.timeout(10000),
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Admin-Token": token,
      ...(options.headers || {}),
    },
  });

  if (res.status === 401) throw new Error("Token inválido. Verifique e tente novamente.");
  if (!res.ok) throw new Error(`Erro ${res.status}: ${res.statusText}`);

  return res.json();
}

export { getToken, apiFetch };
