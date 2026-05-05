"""RAG opcional para a Mari: Agno Knowledge + Postgres (Supabase) + PgVector.

Os playbooks em `docs/playbooks/` permanecem no `instructions` do Agent; esta base
serve para guardrails e documentos extra indexados sem inflacionar o system prompt.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from .config import maria_knowledge_auto_enabled, maria_postgres_url_for_agno, mistral_api_key
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
