# A Sol da RF — Assistente WhatsApp

Backend em Python/FastAPI para assistente via WhatsApp integrado ao sistema [Produttivo](https://app.produttivo.com.br).

## Fluxo

```
[WhatsApp] ←→ [Z-API] ←→ [Render/FastAPI] ←→ [Produttivo API]
```

## Estrutura

```
app/
├── main.py              # Entry point FastAPI
├── config.py            # Variáveis de ambiente
├── routes/
│   └── webhook.py       # Endpoint webhook Z-API
├── services/
│   ├── zapi.py          # Cliente Z-API (envio de mensagens)
│   └── produttivo.py    # Cliente Produttivo API
└── models/
    └── webhook.py       # Modelos Pydantic do webhook
```

## Setup local

```bash
# Criar ambiente virtual
python -m venv .venv
source .venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis
cp .env.example .env
# Editar .env com suas credenciais

# Rodar localmente
uvicorn app.main:app --reload
```

A API ficará disponível em `http://localhost:8000`.

## Endpoints

| Método | Path | Descrição |
|--------|------|-----------|
| GET | `/` | Status do serviço |
| GET | `/health` | Health check |
| POST | `/api/v1/webhook/zapi` | Webhook Z-API |

## Deploy no Render

1. Conectar o repositório no [Render](https://render.com)
2. O `render.yaml` configura o serviço automaticamente
3. Definir as variáveis de ambiente secretas no painel do Render
4. Obter a URL pública e configurar no webhook da Z-API

## Variáveis de Ambiente

Ver `.env.example` para a lista completa.
