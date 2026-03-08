const API_BASE = "/api/v1";

function getToken() {
  return sessionStorage.getItem("admin_token") || "";
}

async function apiFetch(path, options = {}) {
  const token = getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    signal: AbortSignal.timeout(60000),
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Admin-Token": token,
      ...(options.headers || {}),
    },
  });

  if (res.status === 401) throw new Error("Token inválido. Verifique e tente novamente.");
  if (!res.ok) {
    let detail = `Erro ${res.status}`;
    try {
      const body = await res.json();
      if (body.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {}
    throw new Error(detail);
  }

  return res.json();
}

export { getToken, apiFetch };
