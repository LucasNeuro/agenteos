"""
Contrato Maria ↔ UAZAPI (uazapiGO).

Usar estas funções no handler do webhook HTTP para alinhar com:
- Mem0 / post-hooks (`user_id` estável por contacto)
- Supabase (`maria_sessions` / mensagens — mesmo external_session_id por contacto)
- Envio de resposta (`POST /send/text`, campo ``number``)

Referência: ``docs/uazapi-openapi-spec (12).yaml`` (Webhook, Message, ``/send/text``, ``/send/menu``).
Handlers: ``uazapi_webhook.py``, ``uazapi_client.py``, ``uazapi_parse.py``.
"""

from __future__ import annotations

import re
from typing import Any, Mapping


def _digits_from_jid_or_phone(raw: str) -> str:
    base = raw.strip().split("@", 1)[0]
    return re.sub(r"\D", "", base)


def maria_user_id_from_uaz_message(data: Mapping[str, Any]) -> str | None:
    """
    Identificador estável para AgentOS / Mem0: ``wa_<E.164 só dígitos>``.

    Preferência UAZAPI: ``sender_pn``, depois ``sender``, depois ``chatid`` (1:1).
    """
    for key in ("sender_pn", "sender", "chatid"):
        val = data.get(key)
        if not isinstance(val, str) or not val.strip():
            continue
        digits = _digits_from_jid_or_phone(val)
        if len(digits) >= 10:
            return f"wa_{digits}"
    return None


def uaz_session_id_for_maria(data: Mapping[str, Any]) -> str | None:
    """
    ``session_id`` externo único por contacto (recomendado: igual ao ``user_id`` Maria).
    Assim o histórico Agno e o CRM alinham com um chat WhatsApp.
    """
    return maria_user_id_from_uaz_message(data)


def uaz_send_number_from_message(data: Mapping[str, Any]) -> str | None:
    """
    Valor do campo ``number`` em ``POST /send/text`` (OpenAPI ``sendText``).

    Mantém JID completo quando disponível (ex.: ``5511...@s.whatsapp.net``), senão dígitos.
    """
    chatid = data.get("chatid")
    if isinstance(chatid, str) and chatid.strip():
        return chatid.strip()
    uid = maria_user_id_from_uaz_message(data)
    if uid and uid.startswith("wa_"):
        return uid[3:]
    return None


def uaz_incoming_text(data: Mapping[str, Any]) -> str:
    """Texto legível do utilizador (``text``, ``content`` string/obj, ``body``)."""
    t = data.get("text")
    if isinstance(t, str) and t.strip():
        return t
    c = data.get("content")
    if isinstance(c, str) and c.strip():
        return c
    if isinstance(c, dict):
        for key in ("text", "body", "caption", "message"):
            v = c.get(key)
            if isinstance(v, str) and v.strip():
                return v
    b = data.get("body")
    if isinstance(b, str) and b.strip():
        return b
    return ""


def uaz_incoming_user_turn(data: Mapping[str, Any]) -> str:
    """
    Texto a passar ao agente: mensagem normal, ID de botão/lista, ou ``convertOptions``.
    """
    t = uaz_incoming_text(data).strip()
    if t:
        return t
    bid = data.get("buttonOrListid")
    if isinstance(bid, str) and bid.strip():
        return bid.strip()
    co = data.get("convertOptions")
    if isinstance(co, str) and co.strip():
        return co.strip()
    return ""


def uaz_should_ignore_for_chatbot(data: Mapping[str, Any]) -> bool:
    """
    Mensagens a ignorar antes de chamar o agente (ajustar conforme regras de negócio).

    - ``fromMe``: mensagem enviada pela própria instância
    - ``wasSentByApi`` com loop: pré-filtrar no webhook UAZ com ``excludeMessages``
    """
    if data.get("fromMe") is True:
        return True
    if data.get("isGroup") is True:
        return True
    return False
