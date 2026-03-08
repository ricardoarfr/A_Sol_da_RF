# AI_CONTEXT.md — Contexto para Assistentes de IA

Este arquivo é um guia rápido para que assistentes de IA (Claude, GPT, Copilot, etc.) compreendam rapidamente o projeto e raciocinem corretamente sobre modificações no código.

---

## O que é este projeto

**A Sol da RF** é um backend Python/FastAPI que funciona como assistente WhatsApp para uma empresa de serviços de campo (RF).

Técnicos e supervisores enviam mensagens em linguagem natural pelo WhatsApp. O sistema usa agentes de IA com tool use para consultar sistemas externos (como Produttivo — sistema de gestão de atividades de campo) e responder com informações relevantes.

**Não é um chatbot simples.** É uma plataforma de agentes configurável via painel admin.

---

## Arquitetura em Uma Página

```
WhatsApp → [Z-API/Baileys webhook] → [FastAPI]
                                          │
                                    phone whitelist check
                                          │
                                    orchestrator.py
                                    (seleciona agente)
                                          │
                                    agent_runner.py
                                    (tool use loop)
                                          │
                                    executor.py
                                    (HTTP requests)
                                          │
                                    APIs externas
                                    (Produttivo, etc.)
```

O painel admin (`/admin`) permite configurar toda a plataforma sem código.

---

## Módulos Críticos

| Arquivo | O que faz |
|---------|----------|
| `app/services/orchestrator.py` | Decide qual agente processa a mensagem |
| `app/services/agent_runner.py` | Executa agente com loop de tool use (até 10 iter) |
| `app/services/executor.py` | Executa requisições HTTP com auth e substituição |
| `app/services/database.py` | Schema do banco e pool asyncpg |
| `app/routes/admin.py` | ~500 linhas, toda a API admin |
| `app/routes/webhook.py` | Entrada de mensagens WhatsApp |

---

## Regras de Ouro do Projeto

1. **`routes/` não contém lógica** — só recebe, valida, chama service, responde
2. **`services/` não conhece HTTP** — funções puras de negócio
3. **Um service por sistema externo** — `produttivo.py`, `voalle.py`, etc.
4. **Sempre async** — toda I/O usa `async/await` e `httpx.AsyncClient`
5. **Credenciais só em `.env`** — nunca hardcoded
6. **Respostas curtas no WhatsApp** — usuário está em campo, sem textos longos
7. **Falhas graciosas** — erro de sistema externo → mensagem amigável para o usuário

---

## Armadilha Importante: Tipos de Campos JSON

Os campos `headers`, `query_params`, `body_template` em `endpoints` e `config` em `auth_methods` são armazenados como **TEXT** (não JSONB) no PostgreSQL.

**Consequência:** O backend espera receber esses campos como **strings JSON**, não como objetos.

```python
# CORRETO — enviar como string
payload = {
    "headers": '{"X-Token": "valor"}',        # string
    "query_params": '{"page": "1"}',          # string
    "body_template": '{"user": "{user_id}"}', # string
}

# ERRADO — enviar como objeto
payload = {
    "headers": {"X-Token": "valor"},           # dict — vai falhar!
}
```

No frontend, sempre usar `JSON.stringify()` antes de enviar.

---

## Como o Tool Use Funciona

Quando um agente recebe uma mensagem:

1. `agent_runner.py` carrega os endpoints vinculados ao agente
2. Para cada endpoint, extrai variáveis do path/headers/body (`{nome}` → parâmetro)
3. Constrói a definição de tool no formato do provider
4. Chama a IA com a mensagem + tools
5. Se IA quer chamar uma tool → `executor.execute_endpoint()`
6. Resultado volta para a IA → IA formula resposta
7. Loop até resposta final (máx 10 iterações)

O mapeamento de variáveis é automático — `{date}` no path vira um parâmetro na definição da tool.

---

## Providers de IA

| Provider | Como chamar tools |
|----------|------------------|
| `anthropic` | `tools` array no formato Claude |
| `openai` | `functions` array no formato OpenAI |
| `groq` | igual OpenAI (compatível) |
| `openrouter` | igual OpenAI (compatível) |
| `google` | sem tools nativas — ferramentas descritas no system prompt |

Lógica de diferenciação está em `agent_runner.py`, na função `run_agent()`.

---

## Fluxo de Configuração (Como o Admin Configura um Agente)

```
1. Sistema: cadastra base URL do sistema externo
2. Auth Method: cadastra como autenticar (token, cookie, etc.)
3. Endpoint: cadastra rota + vincula ao sistema e ao auth method
4. Agente: cria agente com system prompt + vincula endpoints como tools
5. Ativa o agente → próximas mensagens chegam ao agente
```

Tudo persiste em PostgreSQL. A startup inicializa as tabelas automaticamente.

---

## Como Modificar o Código com Segurança

### Adicionando um novo sistema externo (ex: Voalle)

```
1. Criar app/services/voalle.py
   - Funções async
   - httpx.AsyncClient(timeout=30)
   - raise_for_status() nas chamadas
   - Logger: logger = logging.getLogger(__name__)

2. Adicionar credenciais em app/config.py + .env.example

3. O resto é configuração via painel admin:
   - Cadastrar sistema, auth method, endpoints, vincular ao agente
```

### Adicionando um novo endpoint admin

```
1. Criar Pydantic model para o payload (se POST/PUT)
2. Criar função no service correspondente
3. Adicionar rota em routes/admin.py
   - Usar get_pool como dependência
   - Nunca colocar lógica de negócio na rota
```

### Modificando o agent_runner

```
⚠️ Arquivo crítico — modificações afetam todos os agentes.
Leia o arquivo completo antes de qualquer alteração.
Teste com o "Testar agente" no painel admin após alterações.
```

### Modificando o banco de dados

```
Adicionar em database.py com CREATE TABLE IF NOT EXISTS (idempotente).
Nunca fazer DROP TABLE ou ALTER TABLE sem backup.
Não usar migrations formais — o schema é simples e gerenciado manualmente.
```

---

## O que NÃO Fazer

- **Não refatorar código funcionando** sem solicitação explícita
- **Não adicionar abstrações** para "futuras necessidades" hipotéticas
- **Não usar `requests`** — sempre `httpx.AsyncClient` async
- **Não expor erros técnicos no WhatsApp** — tratar exceções antes de responder
- **Não commitar credenciais** — tudo via `.env` / `settings`
- **Não misturar lógica de dois sistemas** no mesmo arquivo de service
- **Não modificar `render.yaml`** sem entender o impacto no deploy

---

## Perguntas Frequentes para IA

**"Onde fica a lógica de processamento de mensagens?"**
→ `app/routes/webhook.py` recebe, `app/services/orchestrator.py` decide, `app/services/agent_runner.py` executa.

**"Como o agente sabe quais APIs chamar?"**
→ Endpoints são vinculados ao agente via `agent_endpoints` no banco. O `agent_runner.py` os carrega e os converte em tools para a IA.

**"Como adicionar autenticação em um endpoint?"**
→ Criar um `auth_method` no banco (via admin), depois vincular ao endpoint no campo `auth_method_id`.

**"Por que `headers` é uma string em vez de um dict?"**
→ Armazenado como TEXT no PostgreSQL por simplicidade. O `executor.py` deserializa com `json.loads()` antes de usar. O frontend usa `JSON.stringify()` antes de enviar.

**"Como testar sem o WhatsApp?"**
→ Usar "Testar agente" no painel admin, ou chamar `POST /admin/agents/{id}/run` com uma mensagem de teste.

**"O que é `WHATSAPP_SERVICE_URL`?"**
→ URL do serviço Node.js Baileys (geralmente `http://localhost:3000` local ou a URL do Render em produção). O FastAPI envia mensagens via HTTP para este serviço.
