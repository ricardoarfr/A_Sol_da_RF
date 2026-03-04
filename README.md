# A Sol da RF — Assistente WhatsApp Inteligente

Backend que transforma o WhatsApp em uma interface de gestão de campo — conectando técnicos, supervisores e operações em tempo real, sem precisar abrir nenhum sistema.

---

## Visão Geral

A Sol da RF é uma empresa de serviços de campo. Seus técnicos e supervisores precisam consultar atividades, verificar agendamentos, registrar ocorrências e obter informações operacionais — tudo isso enquanto estão em campo, muitas vezes sem tempo ou acesso fácil a sistemas desktop.

Este projeto resolve isso com um assistente via WhatsApp: o usuário manda uma mensagem em linguagem natural e o sistema responde com os dados corretos, consultando os sistemas internos nos bastidores.

---

## O Problema que Resolvemos

- Técnicos em campo precisam de informações que estão presas em sistemas web
- Supervisores perdem tempo verificando manualmente agendamentos e status
- Não existe uma interface unificada que fale com todos os sistemas da empresa
- Comunicação via WhatsApp já acontece informalmente — mas sem estrutura

---

## A Solução

Um assistente conversacional no WhatsApp que:

1. **Entende linguagem natural** — o usuário fala como fala normalmente
2. **Consulta os sistemas certos** — Produttivo, Voalle, Telerdar, etc.
3. **Responde de forma clara e direta** — sem menus complicados
4. **É extensível** — novos sistemas e novas capacidades são adicionados como módulos independentes

---

## Fluxo da Aplicação

```
Usuário (WhatsApp)
      ↓ envia mensagem
   [Z-API]
      ↓ dispara webhook
   [Render / FastAPI]  ←→  [IA: interpreta intenção]
      ↓ consulta
   [Produttivo API]  /  [Voalle]  /  [Telerdar]  /  [outros]
      ↓ resposta processada
   [Z-API]
      ↓ envia resposta
Usuário (WhatsApp)
```

---

## Sistemas Integrados

| Sistema | Função | Status |
|---------|--------|--------|
| Z-API | Gateway WhatsApp | Conectado |
| Produttivo | Gestão de atividades e técnicos de campo | Em desenvolvimento |
| Voalle | (a definir) | Planejado |
| Telerdar | (a definir) | Planejado |

---

## Arquitetura do Backend

```
app/
├── main.py              # FastAPI app — entry point
├── config.py            # Configurações via variáveis de ambiente
├── routes/
│   └── webhook.py       # Recebe e despacha mensagens do WhatsApp
├── services/
│   ├── zapi.py          # Envio de mensagens via Z-API
│   ├── produttivo.py    # Consultas ao Produttivo
│   └── [sistema].py     # Novos sistemas entram aqui como módulos
└── models/
    └── webhook.py       # Modelos Pydantic do payload Z-API
```

### Princípio de extensibilidade

Cada sistema externo vive em seu próprio arquivo dentro de `services/`. Eles são independentes entre si. O `webhook.py` (ou futuramente a IA) decide qual service chamar com base na intenção do usuário.

---

## Stack Tecnológica

| Componente | Tecnologia |
|------------|------------|
| Linguagem | Python 3.11+ |
| Framework | FastAPI |
| Servidor | Uvicorn |
| HTTP Client | httpx (async) |
| Validação | Pydantic v2 |
| Configuração | pydantic-settings |
| Hospedagem | Render |
| Gateway WhatsApp | Z-API |

---

## Setup Local

```bash
# 1. Clonar o repositório
git clone https://github.com/ricardoarfr/A_Sol_da_RF.git
cd A_Sol_da_RF

# 2. Criar ambiente virtual
python -m venv .venv
source .venv/bin/activate      # Linux/Mac
.venv\Scripts\activate         # Windows

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Configurar variáveis de ambiente
cp .env.example .env
# Editar .env com suas credenciais reais

# 5. Rodar localmente
uvicorn app.main:app --reload
```

Acesse: `http://localhost:8000`

Para testar o webhook localmente, use o [ngrok](https://ngrok.com):
```bash
ngrok http 8000
# Configure a URL gerada como webhook na Z-API
```

---

## Endpoints

| Método | Path | Descrição |
|--------|------|-----------|
| GET | `/` | Status do serviço |
| GET | `/health` | Health check (usado pelo Render) |
| POST | `/api/v1/webhook/zapi` | Recebe mensagens da Z-API |

---

## Deploy no Render

1. Conectar o repositório no [Render](https://render.com) → **New → Web Service**
2. O `render.yaml` configura o serviço automaticamente
3. Definir as variáveis secretas no painel do Render (ver `.env.example`)
4. Copiar a URL pública gerada (ex: `https://a-sol-da-rf.onrender.com`)
5. Configurar essa URL como webhook na Z-API

---

## Variáveis de Ambiente

Ver `.env.example` para a lista completa e comentada.

Nunca commitar o arquivo `.env` real — ele está no `.gitignore`.

---

## Roadmap

- [x] Estrutura inicial do projeto
- [x] Webhook Z-API funcional
- [x] Cliente Produttivo (atividades e técnicos)
- [x] Deploy no Render
- [ ] Configurar webhook na Z-API com URL pública
- [ ] Integração com modelo de IA (interpretação de intenção)
- [ ] Integração Voalle
- [ ] Integração Telerdar
- [ ] Autenticação de usuários por número de WhatsApp
- [ ] Histórico de conversas
- [ ] Painel de monitoramento

---

## Contribuindo

Este é um projeto interno da RF. Siga as diretrizes em `ASSISTANT.md` e `CLAUDE.md` antes de contribuir ou solicitar alterações.
