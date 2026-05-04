"""Grava cada turno (user + assistant) em maria_sessions / maria_messages no Supabase."""

from __future__ import annotations

from typing import Any

import httpx
from agno.session.agent import AgentSession
from agno.run.agent import RunOutput

from .config import crm_configured, supabase_service_role_key, supabase_url
from .rich_logging import get_maria_logger


def _headers() -> dict[str, str]:
    key = supabase_service_role_key()
    if not key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY em falta")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _rest_insert(table: str, row: dict[str, Any]) -> list[dict[str, Any]]:
    base = supabase_url().rstrip("/")
    url = f"{base}/rest/v1/{table}"
    r = httpx.post(url, headers=_headers(), json=row, timeout=30.0)
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else [data]


def _find_session_row(external_session_id: str) -> str | None:
    base = supabase_url().rstrip("/")
    url = f"{base}/rest/v1/maria_sessions"
    r = httpx.get(
        url,
        headers=_headers(),
        params={
            "external_session_id": f"eq.{external_session_id}",
            "select": "id",
            "limit": "1",
        },
        timeout=30.0,
    )
    r.raise_for_status()
    rows = r.json()
    if isinstance(rows, list) and rows:
        rid = rows[0].get("id")
        return str(rid) if rid else None
    return None


def _get_or_create_session_row(
    external_session_id: str,
    *,
    user_id: str | None,
    run_id: str | None,
) -> tuple[str, bool]:
    """Retorna (uuid interno, criou_sessão_agora)."""
    existing = _find_session_row(external_session_id)
    if existing:
        return existing, False
    meta: dict[str, Any] = {}
    if user_id:
        meta["user_id"] = user_id
    if run_id:
        meta["last_run_id"] = run_id
    inserted = _rest_insert(
        "maria_sessions",
        {
            "external_session_id": external_session_id,
            "channel": "agentos",
            "metadata": meta,
        },
    )
    return str(inserted[0]["id"]), True


def _insert_message_row(
    internal_session_uuid: str,
    role: str,
    content: str,
    metadata: dict[str, Any],
) -> None:
    base = supabase_url().rstrip("/")
    url = f"{base}/rest/v1/maria_messages"
    row = {
        "session_id": internal_session_uuid,
        "role": role,
        "content": content,
        "metadata": metadata,
    }
    r = httpx.post(url, headers=_headers(), json=row, timeout=30.0)
    r.raise_for_status()


def _short(s: str | None, max_len: int = 14) -> str:
    if not s:
        return "—"
    t = str(s).replace("\n", " ")
    return t if len(t) <= max_len else t[: max_len - 1] + "…"


def post_log_maria_conversation_turn(
    run_output: RunOutput,
    session: AgentSession,
    **kwargs: Any,
) -> None:
    """
    Post-hook Agno: persiste mensagem do utilizador e resposta do assistente no Supabase.
    """
    log = get_maria_logger()
    if not crm_configured():
        log.debug(
            "[dim]Maria CRM · avulso[/dim] [yellow]Supabase não configurado[/] — sem gravação de mensagens"
        )
        return
    try:
        external_id = session.session_id if session is not None else run_output.session_id
        if not external_id:
            log.warning("[yellow]Maria CRM[/] turno sem [cyan]session_id[/] — ignorado")
            return

        internal_id, created_now = _get_or_create_session_row(
            str(external_id),
            user_id=run_output.user_id or (session.user_id if session else None),
            run_id=run_output.run_id,
        )

        meta_base: dict[str, Any] = {
            "run_id": run_output.run_id,
            "agent_id": run_output.agent_id,
        }

        saved_user = False
        saved_asst = False

        if run_output.input is not None:
            user_text = run_output.input.input_content_string()
            if user_text and user_text.strip():
                _insert_message_row(
                    internal_id,
                    "user",
                    user_text[:80_000],
                    meta_base,
                )
                saved_user = True

        assistant_text = ""
        if isinstance(run_output.content, str):
            assistant_text = run_output.content
        elif run_output.content is not None:
            assistant_text = str(run_output.content)
        if assistant_text.strip():
            meta = {**meta_base}
            if run_output.tools:
                meta["tools"] = [
                    {"name": getattr(t, "tool_name", None) or getattr(t, "name", None)}
                    for t in run_output.tools[:20]
                ]
            _insert_message_row(internal_id, "assistant", assistant_text[:80_000], meta)
            saved_asst = True

        sess_note = "[bold green]nova sessão Supabase[/]" if created_now else "sessão existente"
        log.info(
            "[bold green]Maria CRM ✓[/] [dim]maria_messages[/] · %s · "
            "ext=[cyan]%s[/] db=[magenta]%s[/] · user=%s · assistant=%s · run=[dim]%s[/]",
            sess_note,
            _short(str(external_id), 36),
            _short(internal_id, 36),
            "[green]sim[/]" if saved_user else "[dim]não[/]",
            "[green]sim[/]" if saved_asst else "[dim]não[/]",
            _short(run_output.run_id, 24),
        )

    except Exception as e:  # noqa: BLE001
        log.exception(
            "[bold red]Maria CRM ✗[/] falha ao gravar [dim]maria_messages[/] — [red]%s[/]",
            e,
        )
