# API.md — Referência da API Admin

Documentação completa de todos os endpoints da API admin do A Sol da RF.

**Base URL:** `https://<seu-dominio>/api/v1`
**Autenticação:** Header `X-Admin-Token: <ADMIN_TOKEN>` em todas as requisições admin.

---

## Webhooks (Entrada de Mensagens)

Estes endpoints recebem mensagens do WhatsApp. Não requerem `X-Admin-Token`.

### POST /webhook/zapi

Recebe mensagens via Z-API.

**Body:**
```json
{
  "instanceId": "string",
  "messageId": "string",
  "phone": "5511999999999",
  "fromMe": false,
  "status": "received",
  "text": { "message": "quais atividades tenho hoje?" }
}
```

**Resposta:** `200 OK`
```json
{"status": "ok"}
```

### POST /webhook/baileys

Recebe mensagens via Baileys (serviço Node.js).

**Body:**
```json
{
  "phone": "5511999999999",
  "message": "quais atividades tenho hoje?",
  "fromMe": false,
  "messageId": "string"
}
```

---

## AI Models

### GET /admin/ai-models

Lista todos os modelos de IA cadastrados.

**Resposta:**
```json
{
  "models": [
    {
      "id": "uuid",
      "name": "Gemini Flash",
      "provider": "google",
      "model": "gemini-2.0-flash",
      "active": true,
      "created_at": "2026-03-01T00:00:00"
    }
  ],
  "active_id": "uuid"
}
```

### POST /admin/ai-models

Cadastra um novo modelo. Valida a chave de API antes de salvar.

**Body:**
```json
{
  "name": "GPT-4o",
  "provider": "openai",
  "model": "gpt-4o",
  "api_key": "sk-..."
}
```

**Providers aceitos:** `openai`, `anthropic`, `groq`, `google`, `openrouter`

### PUT /admin/ai-models/{id}

Atualiza um modelo. Se `api_key` for vazio ou omitido, mantém a chave atual.

### DELETE /admin/ai-models/{id}

Remove um modelo.

### PUT /admin/ai-models/{id}/activate

Define este modelo como o ativo (desativa os demais).

**Resposta:** `200 OK`
```json
{"ok": true}
```

---

## Authorized Phones

### GET /admin/phones

Lista números autorizados.

**Resposta:**
```json
{
  "phones": [
    {"id": "uuid", "phone": "5511999999999", "name": "João Técnico"}
  ]
}
```

### POST /admin/phones

Adiciona número à whitelist. O número é normalizado automaticamente.

**Body:**
```json
{
  "phone": "11999999999",
  "name": "João Técnico"
}
```

> O DDI 55 é adicionado se ausente. O 9º dígito do celular brasileiro é normalizado.

### PUT /admin/phones/{id}

Atualiza número ou nome.

### DELETE /admin/phones/{id}

Remove número da whitelist.

---

## WhatsApp

### GET /admin/whatsapp/status

Status da conexão WhatsApp.

**Resposta:**
```json
{
  "status": "connected"
}
```

**Status possíveis:** `disconnected`, `connecting`, `qr`, `connected`

### GET /admin/whatsapp/qr

Retorna o QR code para parear o WhatsApp.

**Resposta:**
```json
{
  "qrDataUrl": "data:image/png;base64,..."
}
```

### POST /admin/whatsapp/start

Inicia o processo de conexão WhatsApp.

---

## Systems

### GET /admin/systems

Lista sistemas externos cadastrados.

**Resposta:**
```json
{
  "systems": [
    {
      "id": "uuid",
      "name": "Produttivo",
      "base_url": "https://app.produttivo.com.br",
      "description": "Gestão de atividades de campo",
      "created_at": "2026-03-01T00:00:00",
      "updated_at": "2026-03-01T00:00:00"
    }
  ]
}
```

### POST /admin/systems

**Body:**
```json
{
  "name": "Produttivo",
  "base_url": "https://app.produttivo.com.br",
  "description": "Opcional"
}
```

### GET /admin/systems/{id}

Retorna um sistema específico.

### PUT /admin/systems/{id}

Atualiza sistema.

### DELETE /admin/systems/{id}

Remove sistema (não remove endpoints vinculados automaticamente).

---

## Auth Methods

### GET /admin/auth-methods

Lista métodos de autenticação.

**Resposta:**
```json
{
  "auth_methods": [
    {
      "id": "uuid",
      "name": "Sessão Produttivo",
      "type": "cookie_session",
      "config": "{\"cookies\": {\"_session\": \"abc123\"}}"
    }
  ]
}
```

> `config` é retornado como **string JSON** (campo TEXT no banco).

### POST /admin/auth-methods

**Body:**
```json
{
  "name": "Produttivo Bearer",
  "type": "bearer",
  "config": "{\"token\": \"meu-token\"}"
}
```

**Tipos suportados e config esperada:**

| Tipo | Config |
|------|--------|
| `bearer` | `{"token": "valor"}` |
| `oauth` | `{"token": "valor"}` |
| `api_key` | `{"location": "header|query", "name": "X-Key", "value": "valor"}` |
| `basic` | `{"username": "user", "password": "pass"}` |
| `custom_header` | `{"headers": {"X-Custom": "valor"}}` |
| `cookie_session` | `{"cookies": {"session": "valor"}}` |
| `reverse_engineering` | `{"headers": {...}, "cookies": {...}}` |

> **Importante:** `config` deve ser enviado como **string** (resultado de `JSON.stringify()`), não como objeto.

### GET /admin/auth-methods/{id}

### PUT /admin/auth-methods/{id}

### DELETE /admin/auth-methods/{id}

---

## Endpoints

### GET /admin/endpoints

Lista endpoints do catálogo.

**Query params:**
- `system_id` (opcional): filtra por sistema

**Resposta:**
```json
{
  "endpoints": [
    {
      "id": "uuid",
      "system_id": "uuid",
      "name": "Listar atividades",
      "method": "GET",
      "path": "/form_fills",
      "headers": "{}",
      "query_params": "{\"page\": \"1\"}",
      "body_template": "{}",
      "auth_method_id": "uuid",
      "description": "Lista preenchimentos de formulário"
    }
  ]
}
```

> `headers`, `query_params`, `body_template` são **strings JSON** (TEXT no banco).

### POST /admin/endpoints

**Body:**
```json
{
  "system_id": "uuid",
  "name": "Listar atividades",
  "method": "GET",
  "path": "/form_fills?page={page}",
  "headers": "{}",
  "query_params": "{}",
  "body_template": "{}",
  "auth_method_id": "uuid",
  "description": "Opcional"
}
```

> **Importante:** `headers`, `query_params`, `body_template` devem ser enviados como **strings** (`JSON.stringify(obj)`).

**Métodos aceitos:** `GET`, `POST`, `PUT`, `PATCH`, `DELETE`

### GET /admin/endpoints/{id}

Retorna endpoint específico.

### PUT /admin/endpoints/{id}

Atualiza endpoint.

### DELETE /admin/endpoints/{id}

Remove endpoint.

### POST /admin/endpoints/{id}/execute

Executa o endpoint com parâmetros fornecidos.

**Body:**
```json
{
  "params": {
    "date": "2026-03-08",
    "user_id": "42"
  }
}
```

**Resposta:**
```json
{
  "status_code": 200,
  "body": {...},
  "headers": {...},
  "elapsed_ms": 245.3
}
```

### POST /admin/endpoints/{id}/simulate

Simula a requisição sem executá-la (dry-run). Retorna a requisição montada.

**Body:** igual ao execute.

**Resposta:**
```json
{
  "method": "GET",
  "url": "https://app.produttivo.com.br/form_fills?page=1",
  "headers": {"Cookie": "..."},
  "body": null
}
```

---

## Agents

### GET /admin/agents

Lista agentes.

**Resposta:**
```json
{
  "agents": [
    {
      "id": "uuid",
      "name": "Assistente de Campo",
      "type": "internal",
      "is_active": true,
      "description": "Consulta atividades no Produttivo",
      "system_prompt": "Você é um assistente...",
      "ai_model_id": "uuid",
      "endpoint_ids": ["uuid1", "uuid2"],
      "created_at": "2026-03-01T00:00:00"
    }
  ]
}
```

### POST /admin/agents

**Body:**
```json
{
  "name": "Assistente de Campo",
  "type": "internal",
  "is_active": true,
  "description": "Consulta atividades no Produttivo",
  "system_prompt": "Você é um assistente...",
  "ai_model_id": "uuid"
}
```

**Tipos de agente:** `internal`, `external`, `orchestrator`

**Resposta:** retorna o agente criado com seu `id`.

### GET /admin/agents/{id}

### PUT /admin/agents/{id}

### DELETE /admin/agents/{id}

### PUT /admin/agents/{id}/endpoints

Define quais endpoints este agente pode usar como ferramentas.

**Body:**
```json
{
  "endpoint_ids": ["uuid1", "uuid2", "uuid3"]
}
```

**Resposta:**
```json
{"ok": true}
```

### POST /admin/agents/{id}/run

Executa o agente com uma mensagem de teste.

**Body:**
```json
{
  "message": "quais atividades tenho hoje?"
}
```

**Resposta:**
```json
{
  "response": "Você tem 3 atividades hoje: ..."
}
```

> Este endpoint pode demorar até 60 segundos dependendo do número de iterações do agente.

---

## Import

### POST /admin/import/postman

Importa endpoints de uma Postman Collection.

**Body:**
```json
{
  "system_id": "uuid",
  "collection": { ... }
}
```

O campo `collection` é o conteúdo do arquivo JSON da collection Postman v2.1.

**Resposta:**
```json
{
  "created": 15,
  "skipped": 2,
  "errors": ["Endpoint X: método inválido"]
}
```

### POST /admin/import/openapi

Importa endpoints de uma spec OpenAPI/Swagger (apenas JSON).

**Body:**
```json
{
  "system_id": "uuid",
  "spec": { ... }
}
```

**Resposta:**
```json
{
  "created": 42,
  "skipped": 0,
  "errors": [],
  "base_url_hint": "https://api.exemplo.com/v2"
}
```

### POST /admin/import/curl

Importa um endpoint a partir de um comando CURL.

**Body:**
```json
{
  "system_id": "uuid",
  "name": "Buscar usuário",
  "curl": "curl -X GET 'https://api.exemplo.com/users/1' -H 'Authorization: Bearer token'"
}
```

**Resposta:**
```json
{
  "id": "uuid",
  "method": "GET",
  "path": "/users/1",
  "name": "Buscar usuário"
}
```

### POST /admin/import/curl/preview

Preview do CURL sem salvar no banco.

**Body:**
```json
{
  "curl": "curl -X POST 'https://api.exemplo.com/data' -H 'Content-Type: application/json' -d '{\"key\": \"value\"}'"
}
```

**Resposta:**
```json
{
  "method": "POST",
  "url": "https://api.exemplo.com/data",
  "path": "/data",
  "headers": {"Content-Type": "application/json"},
  "body": {"key": "value"}
}
```

---

## Simulator

### POST /admin/simulate/raw

Envia uma requisição HTTP arbitrária.

**Body:**
```json
{
  "method": "GET",
  "url": "https://api.exemplo.com/users",
  "headers": {"Accept": "application/json"},
  "query_params": {"page": "1"},
  "body": null,
  "auth_method_id": "uuid"
}
```

**Resposta:**
```json
{
  "status_code": 200,
  "body": [...],
  "headers": {...},
  "elapsed_ms": 320.1
}
```

---

## Códigos de Erro

| Status | Significado |
|--------|-------------|
| `401` | Token admin inválido ou ausente |
| `404` | Recurso não encontrado |
| `422` | Erro de validação (body inválido) |
| `500` | Erro interno do servidor |

**Formato de erro:**
```json
{
  "detail": "mensagem de erro descritiva"
}
```
