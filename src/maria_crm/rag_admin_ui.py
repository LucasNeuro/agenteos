"""UI web mínima para enviar documentos RAG ao bucket Supabase (protegida por segredo)."""

from __future__ import annotations

import html
import hmac
from pathlib import Path
from typing import Mapping

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .config import (
    crm_configured,
    maria_knowledge_ingest_mode,
    maria_rag_admin_reindex_after_upload,
    maria_rag_admin_secret,
    maria_rag_storage_bucket,
)
from .ingest_maria_knowledge import run_maria_knowledge_ingest_singleflight
from .knowledge_maria import maria_rag_health_snapshot
from .rich_logging import get_maria_logger, setup_maria_rich_logging
from .supabase_storage import supabase_upload_bytes

ROUTER_TAG = "Admin RAG"

_MAX_UPLOAD_BYTES = 20 * 1024 * 1024

_ALLOWED_SUFFIX_CT: Mapping[str, str] = {
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _check_token(provided: str | None, expected: str) -> None:
    p = (provided or "").strip().encode("utf-8")
    e = expected.encode("utf-8")
    if len(p) != len(e) or not hmac.compare_digest(p, e):
        raise HTTPException(status_code=401, detail="Token inválido.")


def _safe_object_path(prefix: str, filename: str) -> str:
    name = Path(filename or "").name.strip()
    if not name or name in (".", ".."):
        raise HTTPException(status_code=400, detail="Nome de ficheiro inválido.")
    suf = Path(name).suffix.lower()
    if suf not in _ALLOWED_SUFFIX_CT:
        raise HTTPException(
            status_code=400,
            detail=f"Extensão não permitida. Usa uma destas: {', '.join(sorted(_ALLOWED_SUFFIX_CT))}",
        )
    for ch in name:
        if ch in "\\/":
            raise HTTPException(status_code=400, detail="Nome não pode conter separadores.")

    pref = prefix.strip().replace("\\", "/").strip("/")
    if ".." in pref or pref.startswith("/"):
        raise HTTPException(status_code=400, detail="Prefixo de pasta inválido.")
    if not pref:
        return name
    return f"{pref}/{name}"


def _content_type(suffix: str, declared: str | None) -> str:
    base = _ALLOWED_SUFFIX_CT.get(suffix.lower(), "application/octet-stream")
    if declared:
        head = declared.split(";")[0].strip()
        if head in _ALLOWED_SUFFIX_CT.values():
            return head
    return base


def _wrap_page(title: str, inner: str) -> str:
    safe_title = html.escape(title, quote=True)
    bucket_esc = html.escape(maria_rag_storage_bucket(), quote=True)
    reindex_note = (
        "corre-se reindex de todo o bucket em background (pode demorar)."
        if maria_rag_admin_reindex_after_upload()
        else "activa MARIA_RAG_ADMIN_REINDEX_AFTER_UPLOAD=1 ou corre o ingest manualmente / webhook."
    )
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{safe_title}</title>
  <style>
    :root {{
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, sans-serif;
      line-height: 1.5;
      color: #111;
      background: #f0f2f5;
    }}
    body {{ margin: 0; padding: 1rem; }}
    main {{
      max-width: 36rem;
      margin: 0 auto;
      background: #fff;
      padding: 1.75rem;
      border-radius: 10px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }}
    h1 {{ font-size: 1.25rem; margin-top: 0; }}
    label {{ display: block; font-weight: 600; margin: 1rem 0 0.35rem; font-size: 0.9rem; }}
    input[type=text], input[type=file] {{ width: 100%; box-sizing: border-box; }}
    .hint {{ font-size: 0.85rem; color: #555; margin: 0.25rem 0 0; }}
    .ok {{ font-size: 0.9rem; color: #0d6832; background: #e8f5e9; padding: 0.65rem; border-radius: 6px; margin-bottom: 1rem; }}
    button {{
      margin-top: 1.25rem;
      padding: 0.65rem 1.2rem;
      border: none;
      border-radius: 8px;
      background: #0b63d6;
      color: #fff;
      font-weight: 600;
      cursor: pointer;
    }}
    button:hover {{ filter: brightness(1.05); }}
    .warn {{ font-size: 0.85rem; color: #7a5e00; background: #fff8e6; padding: 0.75rem; border-radius: 6px; margin-top: 1rem; }}
    a {{ color: #0b63d6; }}
    code {{ font-size: 0.88em; }}
  </style>
</head>
<body>
  <main>
    <h1>{safe_title}</h1>
    {inner}
    <p class="hint">Guarda o marcador com o parâmetro <code>t=</code> no URL. Bucket: <code>{bucket_esc}</code>.</p>
    <div class="warn">Uso interno. Após o envio, {reindex_note}</div>
  </main>
</body>
</html>
"""


def build_rag_admin_router() -> APIRouter | None:
    secret = maria_rag_admin_secret()
    if not secret:
        return None

    setup_maria_rich_logging()
    log = get_maria_logger()
    router = APIRouter(tags=[ROUTER_TAG])

    def _reindex_task() -> None:
        try:
            if maria_knowledge_ingest_mode() != "storage":
                log.warning("[yellow]RAG admin[/] reindex ignorado — MARIA_KNOWLEDGE_INGEST_MODE não é storage.")
                return
            n = run_maria_knowledge_ingest_singleflight()
            if n is None:
                log.info("[cyan]RAG admin[/] reindex já em execução; pedido ignorado.")
                return
            log.info("[green]RAG admin[/] reindex após upload ✓ %s ficheiros processados.", n)
        except Exception:  # noqa: BLE001
            log.exception("[red]RAG admin[/] reindex após upload falhou")

    @router.get("/admin/rag", response_class=HTMLResponse)
    def rag_admin_form(
        t: str = Query(..., description="Igual a MARIA_RAG_ADMIN_SECRET"),
        ok: int | None = Query(None),
    ) -> HTMLResponse:
        _check_token(t, secret)
        if not crm_configured():
            raise HTTPException(
                status_code=503,
                detail="SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY necessários para upload Storage.",
            )
        ok_block = ""
        if ok == 1:
            ok_block = '<p class="ok">Ficheiro enviado. Se a reindex estiver ligada, corre em background.</p>'
        form_inner = f"""
    {ok_block}
    <p class="hint">Tipos: {html.escape(", ".join(sorted(_ALLOWED_SUFFIX_CT)), quote=True)} · máx {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB.</p>
    <form method="post" action="/admin/rag/upload" enctype="multipart/form-data">
      <input type="hidden" name="t" value="{html.escape(t, quote=True)}" />
      <label for="prefix">Pasta dentro do bucket (opcional)</label>
      <input type="text" id="prefix" name="folder_prefix" placeholder="ex.: politicas" autocomplete="off" />
      <p class="hint">Grava como <code>politicas/nome.pdf</code>. Vazio = raiz do bucket.</p>
      <label for="file">Ficheiro</label>
      <input type="file" id="file" name="file" required accept=".md,.txt,.pdf,.docx" />
      <button type="submit">Enviar para o Storage</button>
    </form>
    """
        page = _wrap_page("Upload documentos RAG (Maria)", form_inner)
        return HTMLResponse(content=page, media_type="text/html; charset=utf-8")

    @router.post("/admin/rag/upload")
    async def rag_admin_upload(
        background_tasks: BackgroundTasks,
        t: str = Form(),
        folder_prefix: str = Form(""),
        file: UploadFile = File(...),
    ) -> RedirectResponse:
        _check_token(t, secret)
        if not crm_configured():
            raise HTTPException(
                status_code=503,
                detail="CRM Supabase não configurado.",
            )
        raw = await file.read()
        if len(raw) > _MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Ficheiro demasiado grande.")

        object_path = _safe_object_path(folder_prefix, file.filename or "documento")
        suffix = Path(object_path).suffix.lower()
        ct = _content_type(suffix, file.content_type)

        try:
            supabase_upload_bytes(
                bucket=maria_rag_storage_bucket(),
                object_path=object_path,
                data=raw,
                content_type=ct,
                upsert=True,
            )
        except Exception as e:  # noqa: BLE001
            log.exception("[red]RAG admin[/] upload falhou")
            raise HTTPException(status_code=502, detail=str(e)[:400]) from e

        log.info("[green]RAG admin[/] upload ✓ [dim]%s[/]", object_path[:120])

        if maria_rag_admin_reindex_after_upload():
            background_tasks.add_task(_reindex_task)

        from urllib.parse import quote

        return RedirectResponse(
            url=f"/admin/rag?t={quote(t, safe='')}&ok=1",
            status_code=303,
        )

    @router.get("/admin/rag/validate")
    def rag_admin_validate(
        t: str = Query(..., description="Igual a MARIA_RAG_ADMIN_SECRET"),
        q: str | None = Query(default=None, description="Texto para validar busca no índice"),
        limit: int = Query(default=5, ge=1, le=20),
    ) -> JSONResponse:
        _check_token(t, secret)
        snapshot = maria_rag_health_snapshot(q, limit=limit)
        return JSONResponse(snapshot)

    return router
