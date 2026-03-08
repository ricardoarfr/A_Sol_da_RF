# DEVELOPMENT.md — Guia de Desenvolvimento

Tudo que um desenvolvedor precisa para trabalhar neste projeto.

---

## Pré-requisitos

- Python 3.11+
- PostgreSQL (local ou Docker)
- Node.js 18+ (apenas para o serviço Baileys)
- Git

---

## Setup do Ambiente

### 1. Clonar e instalar dependências Python

```bash
git clone https://github.com/ricardoarfr/A_Sol_da_RF.git
cd A_Sol_da_RF

python -m venv .venv
source .venv/bin/activate   # Mac/Linux
.venv\Scripts\activate      # Windows

pip install -r requirements.txt
```

### 2. Configurar variáveis de ambiente

```bash
cp .env.example .env
```

Editar `.env` com os valores reais:

```env
# Banco de dados (local)
DATABASE_URL=postgresql://postgres:senha@localhost:5432/a_sol_da_rf

# Autenticação do painel admin
ADMIN_TOKEN=meu-token-seguro-aqui

# Z-API (opcional para testes locais)
ZAPI_INSTANCE_ID=
ZAPI_TOKEN=
ZAPI_CLIENT_TOKEN=

# Baileys (opcional para testes locais)
WHATSAPP_SERVICE_URL=http://localhost:3000

# Produttivo (opcional para testes locais)
PRODUTTIVO_BASE_URL=https://app.produttivo.com.br
PRODUTTIVO_ACCOUNT_ID=
PRODUTTIVO_SESSION_COOKIE=
```

### 3. Criar banco de dados local

```bash
# Com PostgreSQL instalado
psql -U postgres -c "CREATE DATABASE a_sol_da_rf;"

# Ou com Docker
docker run -d \
  --name pg-rfdev \
  -e POSTGRES_PASSWORD=senha \
  -e POSTGRES_DB=a_sol_da_rf \
  -p 5432:5432 \
  postgres:16
```

O schema é criado automaticamente na primeira execução do backend.

### 4. Rodar o backend

```bash
uvicorn app.main:app --reload
```

O painel admin estará disponível em: **http://localhost:8000/admin**

### 5. (Opcional) Rodar o serviço Baileys

```bash
cd whatsapp-service
npm install
node dist/server.js
```

---

## Estrutura de Pastas e Responsabilidades

```
app/
├── main.py         → APENAS: criar app, routers, middleware, static files
├── config.py       → APENAS: variáveis de ambiente via pydantic-settings
├── routes/         → APENAS: receber HTTP, validar, chamar services, responder
├── services/       → APENAS: lógica de negócio e integrações externas
└── models/         → APENAS: estruturas Pydantic (sem lógica)
```

**Regras invioláveis:**
- `routes/` não contém lógica de negócio
- `services/` não conhece rotas HTTP
- Um arquivo por sistema externo em `services/`
- Nunca misturar lógica de dois sistemas no mesmo arquivo

---

## Como Adicionar um Novo Sistema Externo

Exemplo: integrar a API do Voalle.

**1. Criar o service:**

```python
# app/services/voalle.py
import httpx
import logging
from app.config import settings

logger = logging.getLogger(__name__)

async def get_contracts(client_id: str) -> list[dict]:
    """Busca contratos de um cliente no Voalle."""
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{settings.VOALLE_BASE_URL}/contracts",
            params={"client_id": client_id},
            headers={"Authorization": f"Bearer {settings.VOALLE_TOKEN}"},
        )
        r.raise_for_status()
        return r.json()
```

**2. Adicionar configurações:**

```python
# app/config.py — adicionar nos Settings:
voalle_base_url: str = ""
voalle_token: str = ""
```

```env
# .env.example — adicionar:
VOALLE_BASE_URL=https://api.voalle.com.br
VOALLE_TOKEN=
```

**3. Cadastrar via painel admin:**
- Adicionar o sistema em "Sistemas" com a base URL
- Criar um auth method com o token
- Criar os endpoints via "Endpoints" ou importar via "Import"
- Vincular os endpoints ao agente relevante

---

## Como Adicionar um Novo Endpoint Admin

```python
# app/routes/admin.py

class MeuPayload(BaseModel):
    campo_a: str
    campo_b: int = 0

@router.get("/meu-recurso")
async def listar(pool=Depends(get_pool)):
    rows = await pool.fetch("SELECT * FROM minha_tabela")
    return {"itens": [dict(r) for r in rows]}

@router.post("/meu-recurso")
async def criar(payload: MeuPayload, pool=Depends(get_pool)):
    row = await pool.fetchrow(
        "INSERT INTO minha_tabela (campo_a, campo_b) VALUES ($1, $2) RETURNING *",
        payload.campo_a, payload.campo_b
    )
    return dict(row)
```

---

## Como Adicionar uma Nova Tabela

```python
# app/services/database.py — adicionar no bloco CREATE TABLE IF NOT EXISTS:

await conn.execute("""
    CREATE TABLE IF NOT EXISTS minha_tabela (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        nome TEXT NOT NULL,
        dados TEXT DEFAULT '{}',
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );
""")
```

Como o schema usa `IF NOT EXISTS`, a nova tabela é criada automaticamente no próximo restart.

---

## Testando Localmente

### Testar o fluxo de webhook

```bash
# Simular uma mensagem recebida
curl -X POST http://localhost:8000/api/v1/webhook/zapi \
  -H "Content-Type: application/json" \
  -d '{
    "instanceId": "test",
    "messageId": "msg001",
    "phone": "5511999999999",
    "fromMe": false,
    "status": "received",
    "text": {"message": "olá"}
  }'
```

### Testar o painel admin

```bash
# Listar modelos de IA
curl http://localhost:8000/api/v1/admin/ai-models \
  -H "X-Admin-Token: meu-token"

# Criar um sistema
curl -X POST http://localhost:8000/api/v1/admin/systems \
  -H "X-Admin-Token: meu-token" \
  -H "Content-Type: application/json" \
  -d '{"name": "Produttivo", "base_url": "https://app.produttivo.com.br"}'
```

### Testar um agente

```bash
# Executar agente com mensagem de teste
curl -X POST http://localhost:8000/api/v1/admin/agents/<id>/run \
  -H "X-Admin-Token: meu-token" \
  -H "Content-Type: application/json" \
  -d '{"message": "quais atividades tenho hoje?"}'
```

### Usar o Simulador do painel admin

1. Acesse `http://localhost:8000/admin`
2. Navegue para "Simulador"
3. Selecione um endpoint e clique "Executar" (ou marque "Dry-run" para simular)

---

## Padrões de Código

### Python

- `async/await` em toda operação I/O
- `httpx.AsyncClient` com `timeout=30` para chamadas HTTP externas
- Nunca usar `requests` (síncrono)
- Tipagem explícita em funções públicas
- Logger por módulo: `logger = logging.getLogger(__name__)`
- `logging.INFO` como padrão; `DEBUG` só para desenvolvimento

```python
# Correto
async def fetch_data(id: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/resource/{id}")
        r.raise_for_status()
        return r.json()

# Errado
def fetch_data(id):
    r = requests.get(f"{BASE_URL}/resource/{id}")
    return r.json()
```

### Segurança

- Credenciais sempre via `settings` — nunca hardcoded
- Nunca logar tokens, cookies ou dados sensíveis
- Nunca expor mensagens técnicas no WhatsApp — tratar exceções nas rotas

```python
# Correto
except Exception as e:
    logger.error(f"Erro ao consultar Produttivo: {e}")
    return "Não consegui buscar essa informação agora. Tente em instantes."

# Errado
except Exception as e:
    return str(e)  # expõe detalhes técnicos para o usuário
```

### Frontend (JavaScript)

- ES Modules (type="module") — sem bundler
- `apiFetch()` para todas as chamadas à API
- `esc()` para escapar HTML antes de inserir no DOM
- `parseJson()` para validar campos JSON antes de enviar
- Campos `headers`, `query_params`, `body_template`, `config` devem ser enviados como `JSON.stringify(obj)` — o backend espera strings

---

## Convenções de Commit

```
tipo: descrição curta em minúsculas

Tipos:
  feat     → nova funcionalidade
  fix      → correção de bug
  refactor → refatoração sem mudança de comportamento
  docs     → documentação
  chore    → manutenção (deps, CI, config)

Exemplos:
  feat: adicionar consulta de contratos Voalle
  fix: normalizar telefone com DDI antes do whitelist check
  docs: atualizar API.md com novo endpoint de import
  chore: bumpar versão do httpx para 0.28.0
```

---

## Fluxo de Trabalho

```
1. Criar branch de feature a partir de main
   git checkout -b feat/voalle-integration

2. Fazer as alterações (ler arquivos antes de modificar!)

3. Testar localmente

4. Commit com mensagem clara
   git commit -m "feat: integrar consulta de contratos Voalle"

5. Push e criar PR para main
   git push origin feat/voalle-integration

6. Merge em main → deploy automático no Render
```

**Nunca commitar diretamente em `main`.**

---

## Render e Deploy

O `render.yaml` define dois serviços e um banco:

```yaml
services:
  - name: a-sol-da-rf          # Python FastAPI
  - name: a-sol-da-rf-whatsapp  # Node.js Baileys
databases:
  - name: a-sol-da-rf-db        # PostgreSQL free
```

Variáveis secretas são configuradas no painel do Render — nunca no arquivo `render.yaml`.

Para forçar um redeploy sem código novo:
```
Render → Service → Manual Deploy → Deploy latest commit
```

---

## Troubleshooting Comum

| Problema | Causa provável | Solução |
|----------|---------------|----------|
| `401` no painel admin | Token errado | Verificar `ADMIN_TOKEN` no `.env` |
| `connection refused` no banco | PostgreSQL não está rodando | Iniciar PostgreSQL local |
| Agente não responde | Modelo de IA sem chave válida | Cadastrar modelo com chave correta no painel |
| Webhook não chega | ngrok desconectado | Reiniciar ngrok e atualizar URL na Z-API |
| `JSON inválido` no endpoint | Campo TEXT com JSON mal formado | Usar `JSON.stringify()` no frontend |
| Cold start lento | Render free plan dorme após inatividade | Normal — primeira requisição pode demorar ~30s |
