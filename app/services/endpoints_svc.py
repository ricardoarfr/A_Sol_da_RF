import logging
import uuid

from app.services.database import get_pool

logger = logging.getLogger(__name__)

HTTP_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH"}


async def list_endpoints(system_id: str | None = None) -> list[dict]:
    if system_id:
        rows = await get_pool().fetch(
            "SELECT id, system_id, auth_method_id, name, description, method, path,"
            " headers, query_params, body_template, response_example, created_at, updated_at"
            " FROM endpoints WHERE system_id = $1 ORDER BY name",
            system_id,
        )
    else:
        rows = await get_pool().fetch(
            "SELECT id, system_id, auth_method_id, name, description, method, path,"
            " headers, query_params, body_template, response_example, created_at, updated_at"
            " FROM endpoints ORDER BY name"
        )
    return [dict(r) for r in rows]


async def get_endpoint(endpoint_id: str) -> dict | None:
    row = await get_pool().fetchrow(
        "SELECT id, system_id, auth_method_id, name, description, method, path,"
        " headers, query_params, body_template, response_example, created_at, updated_at"
        " FROM endpoints WHERE id = $1",
        endpoint_id,
    )
    return dict(row) if row else None


async def create_endpoint(
    system_id: str,
    auth_method_id: str | None,
    name: str,
    description: str,
    method: str,
    path: str,
    headers: str,
    query_params: str,
    body_template: str,
    response_example: str,
) -> dict:
    if method.upper() not in HTTP_METHODS:
        raise ValueError(f"Método inválido: {method}. Válidos: {sorted(HTTP_METHODS)}")
    endpoint_id = str(uuid.uuid4())
    row = await get_pool().fetchrow(
        """INSERT INTO endpoints
               (id, system_id, auth_method_id, name, description, method, path,
                headers, query_params, body_template, response_example)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
           RETURNING id, system_id, auth_method_id, name, description, method, path,
                     headers, query_params, body_template, response_example, created_at, updated_at""",
        endpoint_id, system_id, auth_method_id, name, description, method.upper(), path,
        headers, query_params, body_template, response_example,
    )
    logger.info(f"Endpoint created: {endpoint_id} ({name}, {method.upper()} {path})")
    return dict(row)


async def update_endpoint(
    endpoint_id: str,
    system_id: str,
    auth_method_id: str | None,
    name: str,
    description: str,
    method: str,
    path: str,
    headers: str,
    query_params: str,
    body_template: str,
    response_example: str,
) -> dict:
    if method.upper() not in HTTP_METHODS:
        raise ValueError(f"Método inválido: {method}. Válidos: {sorted(HTTP_METHODS)}")
    row = await get_pool().fetchrow(
        """UPDATE endpoints
           SET system_id=$1, auth_method_id=$2, name=$3, description=$4, method=$5,
               path=$6, headers=$7, query_params=$8, body_template=$9,
               response_example=$10, updated_at=NOW()
           WHERE id=$11
           RETURNING id, system_id, auth_method_id, name, description, method, path,
                     headers, query_params, body_template, response_example, created_at, updated_at""",
        system_id, auth_method_id, name, description, method.upper(), path,
        headers, query_params, body_template, response_example, endpoint_id,
    )
    if not row:
        raise ValueError("Endpoint não encontrado.")
    logger.info(f"Endpoint updated: {endpoint_id}")
    return dict(row)


async def delete_endpoint(endpoint_id: str) -> None:
    await get_pool().execute("DELETE FROM endpoints WHERE id = $1", endpoint_id)
    logger.info(f"Endpoint deleted: {endpoint_id}")
