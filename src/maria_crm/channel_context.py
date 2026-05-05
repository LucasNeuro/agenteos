"""
Contexto do canal no estado de sessão — para o modelo usar em `registrar_lead_no_crm`.

Com `user_id` no formato `wa_5511...` (ver `uazapi_ids`), preenche telefone e origem
sem depender do texto da conversa.
"""

from __future__ import annotations

from typing import Any


def maria_pre_hook_canal_contacto(
    *,
    session_state: dict[str, Any],
    user_id: str | None = None,
    **kwargs: Any,
) -> None:
    uid = user_id or session_state.get("current_user_id")
    if not isinstance(uid, str) or not uid.startswith("wa_"):
        return
    digits = uid[3:].strip()
    if digits.isdigit() and len(digits) >= 10:
        session_state["telefone_whatsapp"] = digits
        session_state["origem_canal"] = "WhatsApp"
