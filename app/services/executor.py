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


def _apply_auth(auth_type: str | None, auth_config: str | None, headers: dict, query_params: dict, cookies: dict) -> None:
    """Aplica autenticação mutando headers/query_params/cookies in-place."""
    if not auth_type or not auth_config:
        return
    cfg = json.loads(auth_config)

    if auth_type in ("bearer", "oauth"):
        headers["Authorization"] = f"Bearer {cfg.get('token', '')}"
    elif auth_type == "api_key":
        location = cfg.get("location", "header")
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


async def _load_and_prepare(endpoint_id: str, params: dict) -> dict:
    """Carrega endpoint do DB e resolve todos os campos com substituição. Retorna request dict pronto para execução."""
    pool = get_pool()
    row = await pool.fetchrow(
        """SELECT e.id, e.name, e.method, e.path, e.headers, e.query_params, e.body_template,
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

    base_url = row["base_url"].rstrip("/")
    path = _substitute(row["path"], params)
    if not path.startswith("/"):
        path = "/" + path
    url = base_url + path

    headers_str = _substitute(row["headers"] or "{}", params)
    query_str   = _substitute(row["query_params"] or "{}", params)
    body_str    = _substitute(row["body_template"] or "{}", params)

    headers      = json.loads(headers_str)
    query_params = json.loads(query_str)
    body         = json.loads(body_str) if body_str.strip() not in ("{}", "") else None
    cookies: dict = {}

    _apply_auth(row["auth_type"], row["auth_config"], headers, query_params, cookies)

    return {
        "method":       row["method"].upper(),
        "url":          url,
        "headers":      headers,
        "query_params": query_params,
        "body":         body,
        "cookies":      cookies,
    }


async def execute_endpoint(endpoint_id: str, params: dict) -> dict:
    """
    Executa um endpoint configurado no catálogo.
    Retorna: {status_code, body, headers}
    """
    req = await _load_and_prepare(endpoint_id, params)
    logger.info("[executor] %s %s", req["method"], req["url"])

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        response = await client.request(
            method=req["method"],
            url=req["url"],
            headers=req["headers"] or None,
            params=req["query_params"] or None,
            json=req["body"],
            cookies=req["cookies"] or None,
        )

    try:
        response_body = response.json()
    except Exception:
        response_body = response.text

    logger.info("[executor] resposta %s de %s", response.status_code, req["url"])
    return {
        "status_code": response.status_code,
        "body":        response_body,
        "headers":     dict(response.headers),
    }


async def simulate_endpoint(endpoint_id: str, params: dict) -> dict:
    """
    Dry-run: resolve todos os campos do endpoint sem executar a chamada HTTP.
    Retorna a requisição que seria enviada: {method, url, headers, query_params, body, cookies}
    """
    req = await _load_and_prepare(endpoint_id, params)
    logger.info("[executor] simulate %s %s", req["method"], req["url"])
    return req


async def execute_raw(
    method: str,
    url: str,
    headers: dict,
    query_params: dict,
    body: dict | None,
    auth_method_id: str | None = None,
) -> dict:
    """
    Executa uma requisição HTTP arbitrária (não precisa estar no catálogo).
    Opcionalmente aplica um auth_method cadastrado.
    Retorna: {status_code, body, headers, elapsed_ms}
    """
    method = method.upper()
    cookies: dict = {}

    if auth_method_id:
        pool = get_pool()
        auth_row = await pool.fetchrow(
            "SELECT type, config FROM auth_methods WHERE id = $1", auth_method_id
        )
        if auth_row:
            _apply_auth(auth_row["type"], auth_row["config"], headers, query_params, cookies)

    logger.info("[executor] raw %s %s", method, url)

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        response = await client.request(
            method=method,
            url=url,
            headers=headers or None,
            params=query_params or None,
            json=body if body else None,
            cookies=cookies or None,
        )

    elapsed_ms = int(response.elapsed.total_seconds() * 1000) if response.elapsed else 0

    try:
        response_body = response.json()
    except Exception:
        response_body = response.text

    logger.info("[executor] raw resposta %s (%dms)", response.status_code, elapsed_ms)
    return {
        "status_code": response.status_code,
        "body":        response_body,
        "headers":     dict(response.headers),
        "elapsed_ms":  elapsed_ms,
    }
