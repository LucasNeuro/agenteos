"""Webhook opcional para disparar reindexação RAG em produção (Render, cron HTTP, n8n)."""

from __future__ import annotations

import os

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException

from .ingest_maria_knowledge import run_maria_knowledge_ingest_from_env
from .rich_logging import get_maria_logger, setup_maria_rich_logging


def build_maria_rag_ingest_router() -> APIRouter | None:
    """
    Se `MARIA_RAG_INGEST_SECRET` estiver definido, expõe:

    ``POST /webhooks/maria-rag-ingest`` com header ``X-Maria-Rag-Ingest-Secret: <secret>``

    A ingest corre em background (resposta imediata). Define o mesmo secret no Render e num Cron que faça POST.
    """
    secret = os.getenv("MARIA_RAG_INGEST_SECRET", "").strip()
    if not secret:
        return None

    setup_maria_rich_logging()
    router = APIRouter(tags=["maria-rag"])
    log = get_maria_logger()

    def _ingest_job() -> None:
        try:
            n = run_maria_knowledge_ingest_from_env()
            log.info("[green]Maria RAG ingest (background) ✓[/] %s ficheiros.", n)
        except Exception:  # noqa: BLE001
            log.exception("[red]Maria RAG ingest (background) falhou[/]")

    @router.post("/webhooks/maria-rag-ingest")
    def trigger_rag_ingest(
        background_tasks: BackgroundTasks,
        x_maria_rag_ingest_secret: str | None = Header(
            default=None,
            alias="X-Maria-Rag-Ingest-Secret",
        ),
    ) -> dict[str, bool | str]:
        if not x_maria_rag_ingest_secret or x_maria_rag_ingest_secret.strip() != secret:
            raise HTTPException(status_code=403, detail="Forbidden")
        background_tasks.add_task(_ingest_job)
        return {"ok": True, "queued": True}

    return router
