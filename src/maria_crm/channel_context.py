"""
Contexto do canal no estado de sessão — para o modelo usar em `registrar_lead_no_crm`.

Com `user_id` no formato `wa_5511...` (ver `uazapi_ids`), preenche telefone e origem
sem depender do texto da conversa.
"""

from __future__ import annotations

from typing import Any


def _session_state_from_hook_kwargs(kwargs: dict[str, Any]) -> dict[str, Any] | None:
    """Compatível com Agno que passa ``run_context`` sem ``session_state`` explícito no filtro."""
    st = kwargs.get("session_state")
    if isinstance(st, dict):
        return st
    rc = kwargs.get("run_context")
    if rc is not None:
        st2 = getattr(rc, "session_state", None)
        if isinstance(st2, dict):
            return st2
    return None


def maria_internal_background_run_from_kwargs(
    kwargs: dict[str, Any],
    session_state: dict[str, Any] | None = None,
) -> bool:
    """``True`` para corridas internas (ex.: auto-enrich) que não devem ir a Mem0 / maria_messages / stub lead."""
    st = session_state if isinstance(session_state, dict) else _session_state_from_hook_kwargs(kwargs)
    return isinstance(st, dict) and bool(st.get("maria_internal_background_run"))


def maria_pre_hook_canal_contacto(**kwargs: Any) -> None:
    session_state = _session_state_from_hook_kwargs(kwargs)
    if session_state is None:
        return
    user_id = kwargs.get("user_id")
    uid = user_id or session_state.get("current_user_id")
    if not isinstance(uid, str) or not uid.startswith("wa_"):
        return
    digits = uid[3:].strip()
    if digits.isdigit() and len(digits) >= 10:
        session_state["telefone_whatsapp"] = digits
        session_state["origem_canal"] = "WhatsApp"
