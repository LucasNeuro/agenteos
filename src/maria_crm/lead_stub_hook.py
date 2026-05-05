"""Pós-hook: lead mínimo (stub) por sessão se o modelo não chamou `registrar_lead_no_crm`."""

from __future__ import annotations

from typing import Any

from agno.session.agent import AgentSession
from agno.run.agent import RunOutput

from .lead_service import ensure_auto_contact_stub_lead


def _assistant_text(run_output: RunOutput) -> str:
    if isinstance(run_output.content, str):
        return run_output.content
    if run_output.content is not None:
        return str(run_output.content)
    return ""


def _run_called_registrar_lead(run_output: RunOutput) -> bool:
    for t in run_output.tools or []:
        name = getattr(t, "tool_name", None) or getattr(t, "name", None)
        if name == "registrar_lead_no_crm":
            return True
    return False


def post_ensure_maria_contact_stub_lead(
    run_output: RunOutput,
    session: AgentSession,
    session_state: dict[str, Any] | None = None,
    user_id: str | None = None,
    **kwargs: Any,
) -> None:
    """
    Garante um contacto no CRM quando há resposta da Mari sem tool de lead —
    cobre abandono após primeira mensagem (utilizador não responde mais).
    """
    if _run_called_registrar_lead(run_output):
        return
    if not _assistant_text(run_output).strip():
        return

    ext = (session.session_id if session is not None else None) or run_output.session_id
    phone = None
    if isinstance(session_state, dict):
        raw = session_state.get("telefone_whatsapp")
        if raw is not None:
            phone = str(raw).strip() or None

    uid = user_id or (session.user_id if session else None)

    ensure_auto_contact_stub_lead(
        source_external_session_id=str(ext) if ext else None,
        telefone=str(phone).strip() if phone else None,
        user_id=str(uid).strip() if uid else None,
    )
