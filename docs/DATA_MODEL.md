# DATA_MODEL.md — Modelo de Dados

Documentação do schema do banco de dados PostgreSQL do A Sol da RF.

---

## Visão Geral do Schema

```
ai_models          → modelos de IA disponíveis (provider + chave + modelo)
authorized_phones  → whitelist de números WhatsApp autorizados
systems            → sistemas externos (Produttivo, Voalle, etc.)
auth_methods       → métodos de autenticação reutilizáveis
endpoints          → catálogo de endpoints de API
agents             → agentes de IA configurados
agent_endpoints    → relação N:N entre agents e endpoints
whatsapp_session   → dados de sessão do Baileys (Node.js)
```

---

## Diagrama de Relacionamentos

```
systems (1) ───────────────────────────── (N) endpoints
auth_methods (1) ──────────────────────── (N) endpoints
ai_models (0..1) ──────────────────────── (N) agents
agents (N) ──── agent_endpoints ──────── (N) endpoints

authorized_phones   [tabela independente]
whatsapp_session    [tabela independente]
ai_models           [tabela independente, active=bool]
```

---

## Tabelas

### `ai_models`

Modelos de IA disponíveis para uso pelos agentes.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | UUID (PK) | Identificador único |
| `name` | TEXT | Nome amigável (ex: "Gemini Flash") |
| `provider` | TEXT | Provider: `openai`, `anthropic`, `groq`, `google`, `openrouter` |
| `model` | TEXT | ID do modelo (ex: `gpt-4o`, `claude-sonnet-4-6`) |
| `api_key` | TEXT | Chave de API do provider |
| `active` | BOOLEAN | Apenas um modelo é `true` — é o modelo padrão |
| `created_at` | TIMESTAMP | Data de criação |

**Restrição:** `active = true` para no máximo um registro (enforçado por código em `ai_config.py`).

---

### `authorized_phones`

Whitelist de números WhatsApp que podem interagir com o assistente.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | UUID (PK) | Identificador único |
| `phone` | TEXT (UNIQUE) | Número normalizado (ex: `5511999999999`) |
| `name` | TEXT | Nome/apelido (opcional) |
| `created_at` | TIMESTAMP | Data de cadastro |

**Normalização:** DDI 55 adicionado automaticamente. 9º dígito do celular removido para números com 11 dígitos.

**Comportamento:** Lista vazia = todos os números bloqueados.

---

### `systems`

Sistemas externos que podem ser consultados via endpoints.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | UUID (PK) | Identificador único |
| `name` | TEXT | Nome do sistema (ex: "Produttivo") |
| `base_url` | TEXT | URL base (ex: `https://app.produttivo.com.br`) |
| `description` | TEXT | Descrição opcional |
| `created_at` | TIMESTAMP | Data de criação |
| `updated_at` | TIMESTAMP | Última atualização |

---

### `auth_methods`

Métodos de autenticação reutilizáveis, vinculados aos endpoints.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | UUID (PK) | Identificador único |
| `name` | TEXT | Nome amigável (ex: "Sessão Produttivo") |
| `type` | TEXT | Tipo de auth (ver abaixo) |
| `config` | TEXT | Configuração serializada como JSON string |
| `created_at` | TIMESTAMP | Data de criação |
| `updated_at` | TIMESTAMP | Última atualização |

**Tipos de `type` e estrutura de `config`:**

| type | config (JSON string) |
|------|----------------------|
| `bearer` | `{"token": "..."}` |
| `oauth` | `{"token": "..."}` |
| `api_key` | `{"location": "header|query", "name": "X-Key", "value": "..."}` |
| `basic` | `{"username": "...", "password": "..."}` |
| `custom_header` | `{"headers": {"X-Header": "valor"}}` |
| `cookie_session` | `{"cookies": {"nome": "valor"}}` |
| `reverse_engineering` | `{"headers": {...}, "cookies": {...}}` |

> **Nota técnica:** `config` é armazenado como `TEXT` (não `JSONB`) para flexibilidade. O aplicativo é responsável por serializar/deserializar.

---

### `endpoints`

Catálogo de endpoints de API que os agentes podem usar como ferramentas.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | UUID (PK) | Identificador único |
| `system_id` | UUID (FK → systems) | Sistema ao qual pertence |
| `auth_method_id` | UUID (FK → auth_methods, nullable) | Auth a aplicar |
| `name` | TEXT | Nome do endpoint (ex: "Listar atividades") |
| `description` | TEXT | Descrição para a IA entender quando usar |
| `method` | TEXT | HTTP method: `GET`, `POST`, `PUT`, `PATCH`, `DELETE` |
| `path` | TEXT | Path relativo (ex: `/form_fills/{id}`) |
| `headers` | TEXT | Headers como JSON string (ex: `"{}"`) |
| `query_params` | TEXT | Query params como JSON string |
| `body_template` | TEXT | Body template como JSON string |
| `created_at` | TIMESTAMP | Data de criação |
| `updated_at` | TIMESTAMP | Última atualização |

> **Nota técnica:** `headers`, `query_params`, `body_template` são `TEXT` contendo JSON. Suportam variáveis no formato `{nome_variavel}`.

**Exemplo de path com variáveis:**
```
/form_fills?range_time={range}&form_fill[user_ids][]={user_id}&page={page}
```

---

### `agents`

Agentes de IA com seu comportamento e configuração.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | UUID (PK) | Identificador único |
| `name` | TEXT | Nome do agente |
| `description` | TEXT | Quando este agente deve ser ativado |
| `type` | TEXT | `internal`, `external`, `orchestrator` |
| `is_active` | BOOLEAN | Se o agente está em uso |
| `system_prompt` | TEXT | Instrução de comportamento para a IA |
| `ai_model_id` | UUID (FK → ai_models, nullable) | Modelo específico ou NULL = padrão ativo |
| `created_at` | TIMESTAMP | Data de criação |
| `updated_at` | TIMESTAMP | Última atualização |

**Nota sobre `ai_model_id`:** Se `NULL`, o agente usa o modelo marcado como `active = true` na tabela `ai_models`.

---

### `agent_endpoints`

Tabela de junção N:N entre agentes e endpoints (define quais ferramentas cada agente pode usar).

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `agent_id` | UUID (FK → agents) | Agente |
| `endpoint_id` | UUID (FK → endpoints) | Endpoint vinculado |

**PK:** `(agent_id, endpoint_id)` — chave composta.

---

### `whatsapp_session`

Dados de sessão do serviço Baileys (Node.js). Gerenciada pelo serviço `whatsapp-service`.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | TEXT (PK) | Identificador da sessão (geralmente `"default"`) |
| `data` | TEXT | Dados de sessão serializados |
| `updated_at` | TIMESTAMP | Última atualização |

> Esta tabela é gerenciada exclusivamente pelo serviço Node.js e não deve ser alterada pelo backend Python.

---

## Inicialização do Schema

O schema é criado automaticamente na startup do FastAPI via `services/database.py`:

```python
async def init_db(pool):
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS ai_models (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                ...
            );
            ...
        """)
```

Não há migrations versionadas — o schema usa `CREATE TABLE IF NOT EXISTS` para ser idempotente.

---

## Decisões de Design

| Decisão | Motivo |
|---------|--------|
| UUID como PK em todas as tabelas | Evita colisões, facilita replicação futura |
| JSON como TEXT (não JSONB) | Simplicidade para o plano free do Render; evita problemas de tipo |
| Schema idempotente | Restarts do serviço não causam erros |
| Sem migrations formais | Projeto em estágio inicial; migrações manuais são suficientes |
| `active` em ai_models como bool | Um modelo ativo por vez; lógica simples via UPDATE |
