"""
Importador de APIs (Etapa 9).

Formatos suportados:
  - Postman Collection v2.1 (JSON)
  - OpenAPI / Swagger 2.0 e 3.0 (JSON)
  - CURL command (string)

Todos os importadores recebem um system_id existente e criam endpoints nele.
"""

import json
import logging
import re
import shlex
import uuid
from urllib.parse import urlparse

from app.services.database import get_pool

logger = logging.getLogger(__name__)

_HTTP_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}
_VALID_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH"}


# ---------------------------------------------------------------------------
# Postman Collection v2.1
# ---------------------------------------------------------------------------

def _flatten_postman_items(items: list) -> list[dict]:
    """Desdobra recursivamente pastas Postman em lista plana de requests."""
    result = []
    for item in items:
        if "item" in item:  # é uma pasta
            result.extend(_flatten_postman_items(item["item"]))
        elif "request" in item:
            result.append(item)
    return result


def _postman_relative_path(url: str | dict) -> str:
    """Extrai o path relativo de uma URL Postman, convertendo {{var}} → {var}."""
    if isinstance(url, dict):
        raw = url.get("raw") or ""
        # Se tem array de path, usa ele
        path_parts = url.get("path") or []
        if path_parts:
            raw = "/" + "/".join(
                (":" + p[1:] if p.startswith(":") else p) for p in path_parts
            )
            # Adiciona query se houver
            query = url.get("query") or []
            active_query = [q for q in query if not q.get("disabled")]
            if active_query:
                qs = "&".join(
                    f"{q['key']}={q.get('value', '')}" for q in active_query
                )
                raw = raw + "?" + qs
            return re.sub(r"\{\{(\w+)\}\}", r"{\1}", raw)
    else:
        raw = url or ""
    # Extrai só o path da URL completa
    raw = re.sub(r"\{\{(\w+)\}\}", r"{\1}", raw)
    try:
        parsed = urlparse(raw)
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        return path
    except Exception:
        return raw


def _postman_headers(header_list: list) -> dict:
    return {
        h["key"]: re.sub(r"\{\{(\w+)\}\}", r"{\1}", h.get("value", ""))
        for h in (header_list or [])
        if not h.get("disabled") and h.get("key")
    }


def _postman_body(body_obj: dict | None) -> dict:
    if not body_obj:
        return {}
    mode = body_obj.get("mode", "")
    if mode == "raw":
        raw = body_obj.get("raw", "").strip()
        try:
            return json.loads(raw) if raw else {}
        except Exception:
            return {"_raw": raw}
    if mode == "urlencoded":
        return {
            f["key"]: f.get("value", "")
            for f in (body_obj.get("urlencoded") or [])
            if not f.get("disabled")
        }
    if mode == "formdata":
        return {
            f["key"]: f.get("value", "")
            for f in (body_obj.get("formdata") or [])
            if not f.get("disabled") and f.get("type") != "file"
        }
    return {}


async def import_postman(system_id: str, collection: dict) -> dict:
    """Importa uma Postman Collection v2.1. Retorna {created, skipped, errors}."""
    items = _flatten_postman_items(collection.get("item", []))
    if not items:
        raise ValueError("Nenhum endpoint encontrado na collection.")

    pool = get_pool()
    created, skipped = 0, 0
    errors: list[str] = []

    for item in items:
        try:
            req = item.get("request", {})
            method = (req.get("method") or "GET").upper()
            if method not in _VALID_METHODS:
                method = "GET"

            path = _postman_relative_path(req.get("url") or "")
            headers = _postman_headers(req.get("header") or [])
            body = _postman_body(req.get("body"))
            description = req.get("description") or ""
            if isinstance(description, dict):
                description = description.get("content", "")

            # Separar query_params do path se presentes
            query_params: dict = {}
            if "?" in path:
                path_part, qs = path.split("?", 1)
                for kv in qs.split("&"):
                    if "=" in kv:
                        k, v = kv.split("=", 1)
                        query_params[k] = v
                path = path_part

            ep_id = str(uuid.uuid4())
            await pool.execute(
                """INSERT INTO endpoints
                   (id, system_id, name, description, method, path, headers, query_params, body_template)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
                ep_id, system_id,
                item.get("name") or path,
                description, method, path or "/",
                json.dumps(headers, ensure_ascii=False),
                json.dumps(query_params, ensure_ascii=False),
                json.dumps(body, ensure_ascii=False),
            )
            created += 1
        except Exception as e:
            skipped += 1
            errors.append(f"{item.get('name', '?')}: {e}")

    logger.info("[importer] Postman: %d criados, %d erros → system=%s", created, skipped, system_id)
    return {"created": created, "skipped": skipped, "errors": errors[:10]}


# ---------------------------------------------------------------------------
# OpenAPI / Swagger (JSON)
# ---------------------------------------------------------------------------

def _openapi_base_url(spec: dict) -> str:
    # OAS 3.x
    servers = spec.get("servers") or []
    if servers:
        return servers[0].get("url", "").rstrip("/")
    # Swagger 2.0
    host = spec.get("host", "")
    if host:
        scheme = (spec.get("schemes") or ["https"])[0]
        base_path = spec.get("basePath", "").rstrip("/")
        return f"{scheme}://{host}{base_path}"
    return ""


def _openapi_operation_name(path: str, method: str, op: dict) -> str:
    return (
        op.get("summary")
        or op.get("operationId")
        or f"{method.upper()} {path}"
    )


def _openapi_query_params(parameters: list) -> dict:
    return {
        p["name"]: p.get("example") or p.get("default") or ""
        for p in (parameters or [])
        if p.get("in") == "query"
    }


def _openapi_body_template(op: dict, spec_version: str) -> dict:
    # OAS 3.x
    request_body = op.get("requestBody") or {}
    content = request_body.get("content") or {}
    json_content = content.get("application/json") or {}
    schema = json_content.get("schema") or {}
    if schema:
        return _schema_to_template(schema)
    # Swagger 2.0
    params = op.get("parameters") or []
    for p in params:
        if p.get("in") == "body":
            return _schema_to_template(p.get("schema") or {})
    return {}


def _schema_to_template(schema: dict, depth: int = 0) -> dict | list | str:
    """Converte schema JSON em template de exemplo."""
    if depth > 3:
        return {}
    t = schema.get("type", "object")
    if t == "object":
        props = schema.get("properties") or {}
        return {k: _schema_to_template(v, depth + 1) for k, v in props.items()}
    if t == "array":
        items = schema.get("items") or {}
        return [_schema_to_template(items, depth + 1)]
    if t == "string":
        return schema.get("example") or schema.get("default") or ""
    if t in ("integer", "number"):
        return schema.get("example") or schema.get("default") or 0
    if t == "boolean":
        return schema.get("example") or False
    return {}


async def import_openapi(system_id: str, spec: dict) -> dict:
    """Importa um spec OpenAPI 2.0 ou 3.x (JSON). Retorna {created, skipped, errors}."""
    paths = spec.get("paths") or {}
    if not paths:
        raise ValueError("Nenhum path encontrado no spec.")

    spec_version = "3" if "openapi" in spec else "2"
    pool = get_pool()
    created, skipped = 0, 0
    errors: list[str] = []

    for path, path_item in paths.items():
        for method, op in path_item.items():
            if method.upper() not in _HTTP_METHODS:
                continue
            if not isinstance(op, dict):
                continue
            norm_method = method.upper()
            if norm_method not in _VALID_METHODS:
                norm_method = "GET"

            try:
                name = _openapi_operation_name(path, method, op)
                description = op.get("description") or op.get("summary") or ""
                all_params = (
                    (path_item.get("parameters") or []) + (op.get("parameters") or [])
                )
                query_params = _openapi_query_params(all_params)
                body = _openapi_body_template(op, spec_version)

                ep_id = str(uuid.uuid4())
                await pool.execute(
                    """INSERT INTO endpoints
                       (id, system_id, name, description, method, path, query_params, body_template)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                    ep_id, system_id, name, description,
                    norm_method, path,
                    json.dumps(query_params, ensure_ascii=False),
                    json.dumps(body, ensure_ascii=False),
                )
                created += 1
            except Exception as e:
                skipped += 1
                errors.append(f"{method.upper()} {path}: {e}")

    logger.info("[importer] OpenAPI: %d criados, %d erros → system=%s", created, skipped, system_id)
    return {
        "created": created,
        "skipped": skipped,
        "errors": errors[:10],
        "base_url_hint": _openapi_base_url(spec),
    }


# ---------------------------------------------------------------------------
# CURL command parser
# ---------------------------------------------------------------------------

def parse_curl(curl_str: str) -> dict:
    """
    Converte um comando curl em campos de endpoint.
    Retorna: {method, url, path, headers, query_params, body}
    """
    curl_str = curl_str.strip()
    if curl_str.startswith("curl"):
        curl_str = curl_str[4:].strip()

    # Normaliza continuações de linha
    curl_str = re.sub(r"\s*\\\s*\n\s*", " ", curl_str)

    try:
        tokens = shlex.split(curl_str)
    except ValueError:
        tokens = curl_str.split()

    method = "GET"
    url = ""
    headers: dict = {}
    body_str = ""

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in ("-X", "--request") and i + 1 < len(tokens):
            method = tokens[i + 1].upper()
            i += 2
        elif tok in ("-H", "--header") and i + 1 < len(tokens):
            h = tokens[i + 1]
            if ": " in h:
                k, v = h.split(": ", 1)
            elif ":" in h:
                k, v = h.split(":", 1)
                v = v.strip()
            else:
                k, v = h, ""
            headers[k] = v
            i += 2
        elif tok in ("-d", "--data", "--data-raw", "--data-binary", "--json") and i + 1 < len(tokens):
            body_str = tokens[i + 1].lstrip("@")  # ignorar leitura de arquivo
            if tok == "--json":
                headers.setdefault("Content-Type", "application/json")
                method = method if method != "GET" else "POST"
            i += 2
        elif tok in ("-G", "--get"):
            method = "GET"
            i += 1
        elif not tok.startswith("-") and not url:
            url = tok
            i += 1
        else:
            i += 1

    # Infere método POST se há body e método ainda é GET
    if body_str and method == "GET":
        method = "POST"

    # Valida método
    if method not in _VALID_METHODS:
        method = "POST" if body_str else "GET"

    # Extrai path e query_params da URL
    path = "/"
    query_params: dict = {}
    base_url = ""
    if url:
        try:
            parsed = urlparse(url)
            base_url = f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else ""
            path = parsed.path or "/"
            if parsed.query:
                for kv in parsed.query.split("&"):
                    if "=" in kv:
                        k, v = kv.split("=", 1)
                        query_params[k] = v
        except Exception:
            path = url

    # Parseia body
    body: dict = {}
    if body_str:
        try:
            body = json.loads(body_str)
        except Exception:
            body = {"_raw": body_str}

    # Remove Content-Type dos headers se será gerenciado automaticamente
    headers.pop("Content-Type", None)
    headers.pop("content-type", None)

    return {
        "method": method,
        "url": url,
        "base_url_hint": base_url,
        "path": path,
        "headers": headers,
        "query_params": query_params,
        "body": body,
    }


async def import_curl(system_id: str, name: str, curl_str: str) -> dict:
    """Converte um CURL em endpoint e persiste no banco."""
    parsed = parse_curl(curl_str)
    ep_id = str(uuid.uuid4())
    pool = get_pool()
    await pool.execute(
        """INSERT INTO endpoints
           (id, system_id, name, method, path, headers, query_params, body_template)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
        ep_id, system_id, name or parsed["path"],
        parsed["method"], parsed["path"],
        json.dumps(parsed["headers"], ensure_ascii=False),
        json.dumps(parsed["query_params"], ensure_ascii=False),
        json.dumps(parsed["body"], ensure_ascii=False),
    )
    logger.info("[importer] CURL: endpoint %s criado → system=%s", ep_id, system_id)
    return {
        "endpoint_id": ep_id,
        "method": parsed["method"],
        "path": parsed["path"],
        "base_url_hint": parsed["base_url_hint"],
    }
