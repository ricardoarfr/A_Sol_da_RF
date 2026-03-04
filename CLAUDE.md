# CLAUDE.md — Diretrizes para a IA neste Projeto

Este arquivo define como a IA (Claude) deve se comportar ao trabalhar neste repositório.
Leia `README.md` e `ASSISTANT.md` antes de qualquer intervenção no código.

---

## Leitura Obrigatória Antes de Codar

1. `README.md` — visão geral do produto e arquitetura
2. `ASSISTANT.md` — premissas de negócio e decisões tomadas
3. Os arquivos relevantes ao que será alterado (nunca editar sem ler)

---

## Stack e Tecnologias

- **Linguagem:** Python 3.11+
- **Framework:** FastAPI
- **Validação:** Pydantic v2 — usar `model_validator`, `field_validator` quando necessário
- **Configuração:** pydantic-settings via `.env`
- **HTTP Client:** `httpx` com `AsyncClient` — sempre async
- **Hospedagem:** Render — considerar limitações do plano free (cold start)
- **Gateway WhatsApp:** Z-API

Não introduzir outras dependências sem justificativa explícita e aprovação.

---

## Estrutura de Diretórios

```
app/
├── main.py          # Apenas: criar app, registrar routers, middleware
├── config.py        # Apenas: Settings via pydantic-settings
├── routes/          # Endpoints HTTP — sem lógica de negócio aqui
├── services/        # Um arquivo por sistema externo — lógica de integração
└── models/          # Modelos Pydantic — apenas estrutura de dados
```

### Regras de organização

- `routes/` recebe a requisição, valida, chama services, devolve resposta
- `services/` faz chamadas externas e processa dados — sem conhecer rotas
- `models/` define apenas estruturas — sem lógica de negócio
- Um service por sistema externo (`zapi.py`, `produttivo.py`, `voalle.py`, etc.)
- Nunca misturar lógica de dois sistemas no mesmo arquivo

---

## Regras de Código

### Geral
- Sempre async/await para operações I/O (HTTP, banco, etc.)
- Usar `httpx.AsyncClient` com `timeout=30` como padrão
- Nunca usar `requests` (síncrono) — sempre `httpx`
- Tipagem explícita em funções públicas (parâmetros e retorno)
- Docstring apenas em funções não óbvias — uma linha basta

### Segurança
- Credenciais sempre via `settings` (pydantic-settings) — nunca hardcoded
- Nunca logar tokens, cookies ou dados sensíveis
- Nunca expor mensagens de erro internas no WhatsApp — tratar exceções nas rotas

### Erros
- Usar `try/except` apenas onde há tratamento real — não engolir exceções silenciosamente
- `raise_for_status()` em todas as chamadas HTTP externas
- Em caso de falha de sistema externo: logar o erro e retornar mensagem amigável ao usuário

### Logging
- Usar `logging` padrão do Python — não usar `print()`
- Logger por módulo: `logger = logging.getLogger(__name__)`
- Nível padrão: `INFO` — `DEBUG` apenas para desenvolvimento local

---

## Padrão de Resposta ao Usuário (WhatsApp)

- Respostas curtas — o usuário está em campo
- Usar formatação WhatsApp quando útil: `*negrito*`, `_itálico_`, listas com `•`
- Erros para o usuário: "Não consegui buscar essa informação agora. Tente novamente em instantes."
- Nunca expor stack traces, IDs internos ou dados técnicos

---

## Adicionando Novos Sistemas

Para integrar um novo sistema (ex: Voalle):

1. Criar `app/services/voalle.py` com as funções de consulta
2. Importar e chamar em `app/routes/webhook.py` (ou no handler de IA)
3. Adicionar as variáveis de ambiente necessárias em `config.py` e `.env.example`
4. Documentar o sistema na tabela de `README.md` e `ASSISTANT.md`
5. Nunca modificar serviços existentes para acomodar o novo sistema

---

## O que Não Fazer

- Não refatorar código funcionando sem solicitação explícita
- Não adicionar abstrações, classes base ou helpers genéricos antecipadamente
- Não criar arquivos de documentação extras além dos já existentes (`README.md`, `ASSISTANT.md`, `CLAUDE.md`)
- Não instalar novas dependências sem aprovação
- Não alterar `render.yaml` sem verificar impacto no deploy
- Não fazer push para `main` — usar branches de feature

---

## Fluxo de Trabalho

1. Ler os arquivos relevantes antes de qualquer alteração
2. Entender o impacto da mudança na arquitetura existente
3. Fazer a menor alteração possível que resolve o problema
4. Commitar com mensagem clara no padrão: `tipo: descrição curta`
   - Tipos: `feat`, `fix`, `refactor`, `docs`, `chore`
   - Exemplo: `feat: adicionar consulta de saldo via Voalle`
5. Push para o branch correto (nunca main diretamente)

---

## Contexto de Negócio Resumido

- Empresa de serviços de campo (RF)
- Técnicos em campo precisam de informações operacionais via WhatsApp
- Sistema principal: Produttivo (atividades, técnicos, agenda)
- Outros sistemas serão integrados progressivamente
- Prioridade: funcionar de forma simples e confiável
