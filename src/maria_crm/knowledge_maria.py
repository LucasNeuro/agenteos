"""RAG opcional para a Mari: Agno Knowledge + Postgres (Supabase) + PgVector.

Os playbooks em `docs/playbooks/` permanecem no `instructions` do Agent; esta base
serve para guardrails e documentos extra indexados sem inflacionar o system prompt.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from sqlalchemy import create_engine, text

from .config import (
    maria_knowledge_auto_enabled,
    maria_knowledge_enabled_flag,
    maria_postgres_url_for_agno,
    mistral_api_key,
)
from .rich_logging import get_maria_logger


def maria_knowledge_max_results() -> int:
    raw = os.getenv("MARIA_KNOWLEDGE_MAX_RESULTS", "6").strip()
    try:
        n = int(raw)
    except ValueError:
        return 6
    return max(1, min(n, 25))


def maria_knowledge_embedder_id() -> str:
    return os.getenv("MARIA_EMBEDDING_MODEL", "mistral-embed").strip() or "mistral-embed"


@lru_cache(maxsize=1)
def build_maria_knowledge() -> Any:
    """Instância Agno `Knowledge` ou levanta erro se config em falta."""
    from agno.db.postgres.postgres import PostgresDb
    from agno.knowledge.embedder.mistral import MistralEmbedder
    from agno.knowledge.knowledge import Knowledge
    from agno.vectordb.pgvector.pgvector import PgVector

    db_url = maria_postgres_url_for_agno()
    if not db_url:
        msg = (
            "RAG: falta URL Postgres direta. Define MARIA_DATABASE_URL ou SUPABASE_DATABASE_URL "
            "(formato SQLAlchemy psycopg3: postgresql+psycopg://... — ver .env.example)."
        )
        raise RuntimeError(msg)
    if not mistral_api_key():
        raise RuntimeError("RAG: MISTRAL_API_KEY em falta (embeddings Mistral).")

    embedder = MistralEmbedder(id=maria_knowledge_embedder_id(), api_key=mistral_api_key())

    contents_db = PostgresDb(
        db_url=db_url,
        db_schema="ai",
        knowledge_table="maria_knowledge_contents",
        create_schema=False,
    )
    vector_db = PgVector(
        table_name="maria_knowledge_vectors",
        schema="ai",
        db_url=db_url,
        embedder=embedder,
        create_schema=False,
    )

    return Knowledge(
        name="Maria — conhecimento operacional",
        description=(
            "Políticas, FAQs, guardrails e docs internos HUB/Mari. Usa quando a pergunta "
            "exigir detalhe fora dos playbooks fixos."
        ),
        contents_db=contents_db,
        vector_db=vector_db,
        max_results=maria_knowledge_max_results(),
    )


def try_build_maria_knowledge_optional() -> Any | None:
    """Devolve `Knowledge` se RAG ligado e configurado; caso contrário None (silent)."""
    if not maria_knowledge_auto_enabled():
        return None
    log = get_maria_logger()
    try:
        k = build_maria_knowledge()
        log.info("[green]Maria RAG[/]: base de conhecimento [cyan]Supabase/pgvector[/] ativa.")
        return k
    except Exception as e:  # noqa: BLE001
        log.warning("[yellow]Maria RAG[/]: desligada — [red]%s[/]", e)
        return None


def maria_rag_health_snapshot(query: str | None = None, *, limit: int = 5) -> dict[str, Any]:
    """
    Snapshot operacional do RAG (estado, contagem de índices e validação de consulta textual).
    """
    db_url = maria_postgres_url_for_agno()
    snap: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "knowledge_enabled_flag": maria_knowledge_enabled_flag(),
        "knowledge_auto_enabled": maria_knowledge_auto_enabled(),
        "db_url_configured": bool(db_url),
        "mistral_api_key_configured": bool(mistral_api_key()),
        "embedding_model": maria_knowledge_embedder_id(),
        "max_results": maria_knowledge_max_results(),
        "tables": {
            "ai.maria_knowledge_contents": None,
            "ai.maria_knowledge_vectors": None,
        },
        "query_validation": None,
    }
    if not db_url:
        return snap

    engine = create_engine(db_url, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            for table in ("ai.maria_knowledge_contents", "ai.maria_knowledge_vectors"):
                try:
                    count = conn.execute(text(f"select count(*) from {table}")).scalar_one()
                    snap["tables"][table] = int(count)
                except Exception as e:  # noqa: BLE001
                    snap["tables"][table] = f"error: {str(e)[:180]}"

            q = (query or "").strip()
            if q:
                try:
                    stmt = text(
                        """
                        select id, content_id, left(coalesce(content, ''), 260) as preview
                        from ai.maria_knowledge_vectors
                        where content ilike :q
                        order by created_at desc
                        limit :lim
                        """
                    )
                    rows = conn.execute(stmt, {"q": f"%{q}%", "lim": max(1, min(limit, 20))}).mappings().all()
                    snap["query_validation"] = {
                        "query": q,
                        "matches": len(rows),
                        "samples": [dict(r) for r in rows],
                    }
                except Exception as e:  # noqa: BLE001
                    snap["query_validation"] = {
                        "query": q,
                        "error": str(e)[:220],
                    }
    finally:
        engine.dispose()
    return snap
