import base64
import json
import logging

import httpx

from app.services.database import get_pool

logger = logging.getLogger(__name__)


def _substitute(template: str, params: dict) -> str:
    """Substitui {variavel} no template com valores de params. Deixa sem substituição se a chave não existir."""
    try:
        return template.format_map(params)
    except (KeyError, ValueError):
        return template


async def execute_endpoint(endpoint_id: str, params: dict) -> dict:
    """
    Executa um endpoint configurado no catálogo.
    params: dicionário de variáveis de runtime para substituir nos templates.
    Retorna: {status_code, body, headers}
    """
    pool = get_pool()

    row = await pool.fetchrow(
        """SELECT e.id, e.method, e.path, e.headers, e.query_params, e.body_template,
                  s.base_url,
                  am.type  AS auth_type,
                  am.config AS auth_config
           FROM endpoints e
           JOIN systems s ON s.id = e.system_id
           LEFT JOIN auth_methods am ON am.id = e.auth_method_id
           WHERE e.id = $1""",
        endpoint_id,
    )
    if not row:
        raise ValueError("Endpoint não encontrado.")

    # --- Monta URL ---
    base_url = row["base_url"].rstrip("/")
    path = _substitute(row["path"], params)
    if not path.startswith("/"):
        path = "/" + path
    url = base_url + path

    # --- Parseia headers, query_params e body com substituição ---
    headers_str = _substitute(row["headers"] or "{}", params)
    query_str   = _substitute(row["query_params"] or "{}", params)
    body_str    = _substitute(row["body_template"] or "{}", params)

    headers      = json.loads(headers_str)
    query_params = json.loads(query_str)
    body         = json.loads(body_str) if body_str.strip() not in ("{}", "") else None

    # --- Aplica autenticação ---
    cookies: dict = {}
    auth_type   = row["auth_type"]
    auth_config = row["auth_config"]

    if auth_type and auth_config:
        cfg = json.loads(auth_config)

        if auth_type == "bearer" or auth_type == "oauth":
            token = cfg.get("token", "")
            headers["Authorization"] = f"Bearer {token}"

        elif auth_type == "api_key":
            location = cfg.get("location", "header")  # "header" ou "query"
            name     = cfg.get("name", "X-Api-Key")
            value    = cfg.get("value", "")
            if location == "query":
                query_params[name] = value
            else:
                headers[name] = value

        elif auth_type == "basic":
            user = cfg.get("username", "")
            pwd  = cfg.get("password", "")
            encoded = base64.b64encode(f"{user}:{pwd}".encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"

        elif auth_type == "custom_header":
            headers.update(cfg.get("headers", {}))

        elif auth_type == "cookie_session":
            cookies.update(cfg.get("cookies", {}))

        elif auth_type == "reverse_engineering":
            headers.update(cfg.get("headers", {}))
            cookies.update(cfg.get("cookies", {}))

    # --- Executa ---
    method = row["method"].upper()
    logger.info("[executor] %s %s", method, url)

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        response = await client.request(
            method=method,
            url=url,
            headers=headers or None,
            params=query_params or None,
            json=body,
            cookies=cookies or None,
        )

    try:
        response_body = response.json()
    except Exception:
        response_body = response.text

    logger.info("[executor] resposta %s de %s", response.status_code, url)

    return {
        "status_code": response.status_code,
        "body": response_body,
        "headers": dict(response.headers),
    }
