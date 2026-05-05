"""Ingere documentos (guardrails, FAQs) na base RAG da Maria.

Na raiz do projecto, com .env preenchido:

  python -m src.maria_crm.ingest_maria_knowledge

Modos:
  MARIA_KNOWLEDGE_INGEST_MODE=local (padrão) — pasta `MARIA_KNOWLEDGE_INGEST_DIR` (default docs/maria_guardrails).
  MARIA_KNOWLEDGE_INGEST_MODE=storage — bucket `MARIA_RAG_STORAGE_BUCKET` (migração 006), prefixo opcional `MARIA_RAG_STORAGE_PREFIX`.

Requer para storage: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, e mesma config RAG (Postgres + Mistral) que a ingest local.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from .config import maria_knowledge_ingest_mode, maria_rag_storage_bucket, maria_rag_storage_prefix
from .knowledge_maria import build_maria_knowledge
from .rich_logging import get_maria_logger, setup_maria_rich_logging
from .supabase_storage import supabase_storage_download_bytes, supabase_storage_walk_file_paths


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def ingest_guardrails_dir(
    directory: Path,
    *,
    patterns: tuple[str, ...] = (".md", ".txt", ".pdf", ".docx"),
    skip_if_exists: bool = True,
) -> int:
    """
    Carrega ficheiros da pasta para a base RAG (Agno Knowledge).
    Devolve número de ficheiros processados.
    """
    log = get_maria_logger()
    if not directory.is_dir():
        log.error("[red]Pasta inexistente:[/] %s", directory)
        return 0

    k = build_maria_knowledge()
    n = 0
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in patterns:
            continue
        rel = path.relative_to(directory)
        k.add_content(
            path=str(path),
            name=path.stem,
            description=f"Guardrails / conhecimento Maria — {rel.as_posix()}",
            metadata={
                "source": "maria_guardrails",
                "relative_path": rel.as_posix(),
            },
            skip_if_exists=skip_if_exists,
        )
        log.info("[green]RAG ingest ✓[/] %s", rel)
        n += 1
    return n


def ingest_guardrails_from_storage(
    *,
    patterns: tuple[str, ...] = (".md", ".txt", ".pdf", ".docx"),
    skip_if_exists: bool = True,
) -> int:
    """Ingere ficheiros do bucket Storage (privado; API com service_role)."""
    log = get_maria_logger()
    bucket = maria_rag_storage_bucket()
    prefix = maria_rag_storage_prefix()
    paths = supabase_storage_walk_file_paths(bucket, prefix)
    k = build_maria_knowledge()
    n = 0
    for object_path in sorted(paths):
        suf = Path(object_path).suffix.lower()
        if suf not in patterns:
            continue
        body = supabase_storage_download_bytes(bucket=bucket, object_path=object_path)
        stem = Path(object_path).stem
        suffix = Path(object_path).suffix
        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=suffix) as tmp:
            tmp.write(body)
            tmp_path = tmp.name
        try:
            k.add_content(
                path=tmp_path,
                name=stem or object_path,
                description=f"RAG Storage — {object_path}",
                metadata={
                    "source": "maria_rag_storage",
                    "bucket": bucket,
                    "object_path": object_path,
                },
                skip_if_exists=skip_if_exists,
            )
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        log.info("[green]RAG ingest ✓[/] storage [dim]%s[/]", object_path)
        n += 1
    return n


def main() -> None:
    setup_maria_rich_logging()
    try:
        from dotenv import load_dotenv
    except ImportError:
        load_dotenv = None  # type: ignore[misc, assignment]
    if load_dotenv:
        load_dotenv(_project_root() / ".env")

    mode = maria_knowledge_ingest_mode()
    if mode == "storage":
        n = ingest_guardrails_from_storage()
        get_maria_logger().info("[bold]Ingestão concluída[/] (storage): %s ficheiro(s).", n)
        return

    raw_dir = os.getenv("MARIA_KNOWLEDGE_INGEST_DIR", "docs/maria_guardrails").strip()
    root = Path(raw_dir)
    if not root.is_absolute():
        root = _project_root() / root

    n = ingest_guardrails_dir(root)
    get_maria_logger().info("[bold]Ingestão concluída[/] (local): %s ficheiro(s).", n)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
