import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.webhook import router as webhook_router
from app.config import settings

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="A Sol da RF — WhatsApp Assistant",
    description="Backend para assistente WhatsApp integrado ao Produttivo",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"status": "online", "service": "A Sol da RF — WhatsApp Assistant"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
