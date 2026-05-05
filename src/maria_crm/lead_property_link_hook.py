"""Após `registrar_lead_no_crm`, associa imóveis-rascunho da mesma sessão ao `lead_id`."""

from __future__ import annotations

import re
from typing import Any

from agno.session.agent import AgentSession
from agno.run.agent import RunOutput

from .channel_context import _session_state_from_hook_kwargs
from .property_ingest import link_imoveis_rascunho_to_lead
from .rich_logging import get_maria_logger

_LEAD_ID_RE = re.compile(r"\(id=([0-9a-fA-F-]{36})\)")


def _run_called_registrar_lead(run_output: RunOutput) -> bool:
    for t in run_output.tools or []:
        name = getattr(t, "tool_name", None) or getattr(t, "name", None)
        if name == "registrar_lead_no_crm":
            return True
    return False


def _lead_id_from_tool_results(run_output: RunOutput) -> str | None:
    for t in run_output.tools or []:
        name = getattr(t, "tool_name", None) or getattr(t, "name", None)
        if name != "registrar_lead_no_crm":
            continue
        for attr in ("result", "content", "output", "tool_output"):
            v = getattr(t, attr, None)
            if isinstance(v, str):
                m = _LEAD_ID_RE.search(v)
                if m:
                    return m.group(1)
    return None


def post_link_maria_imoveis_to_lead(
    run_output: RunOutput,
    session: AgentSession,
    session_state: dict[str, Any] | None = None,
    **kwargs: Any,
) -> None:
    log = get_maria_logger()
    if not _run_called_registrar_lead(run_output):
        return
    lead_id = _lead_id_from_tool_results(run_output)
    if not lead_id:
        log.debug("[dim]Maria imóvel[/] link skip — não foi possível extrair lead_id da tool")
        return

    _ = session_state if isinstance(session_state, dict) else _session_state_from_hook_kwargs(kwargs)
    ext = (session.session_id if session is not None else None) or run_output.session_id
    if not ext:
        return
    try:
        link_imoveis_rascunho_to_lead(external_session_id=str(ext), lead_id=lead_id)
        log.info(
            "[green]Maria imóvel ✓[/] rascunhos ligados ao lead [cyan]%s[/]",
            lead_id[:8],
        )
    except Exception as e:  # noqa: BLE001
        log.warning("[yellow]Maria imóvel[/] falha ao ligar imóveis ao lead: %s", e)
