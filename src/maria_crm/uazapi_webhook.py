"""Webhook HTTP UAZAPI → run do ``hub_agent`` → resposta WhatsApp (texto ou botões)."""

from __future__ import annotations

import json
from typing import Any

from agno.agent import Agent
from fastapi import APIRouter, Body, Header, Response, status

from .config import uazapi_configured, uazapi_webhook_secret_expected
from .rich_logging import get_maria_logger
from .uazapi_client import uaz_send_button_menu, uaz_send_text
from .uazapi_ids import (
    maria_user_id_from_uaz_message,
    uaz_incoming_user_turn,
    uaz_send_number_from_message,
    uaz_session_id_for_maria,
    uaz_should_ignore_for_chatbot,
)
from .uazapi_parse import split_maria_reply_for_uaz


def _webhook_event_from_body(body: dict[str, Any]) -> str | None:
    for key in ("event", "EventType", "eventType", "event_type"):
        v = body.get(key)
        if v is not None and str(v).strip():
            return str(v).strip()
    return None


def _merge_chat_into_message(msg: dict[str, Any], chat: dict[str, Any]) -> None:
    """Preenche ``chatid`` / remetente a partir do objeto ``chat`` (webhook plano Bubble/UAZ)."""
    if not msg.get("chatid"):
        for k in ("chatid", "id", "jid", "wa_chatid"):
            v = chat.get(k)
            if isinstance(v, str) and v.strip():
                msg["chatid"] = v.strip()
                break
    if not msg.get("sender_pn"):
        for k in ("sender_pn", "phone", "pn", "senderPhone"):
            v = chat.get(k)
            if isinstance(v, str) and v.strip():
                msg["sender_pn"] = v.strip()
                break
    if not msg.get("sender") and isinstance(chat.get("sender"), str) and chat["sender"].strip():
        msg["sender"] = chat["sender"].strip()
    if not msg.get("isGroup") and chat.get("isGroup") is not None:
        msg["isGroup"] = chat["isGroup"]


def _message_dict_from_flat_uaz_body(body: dict[str, Any]) -> dict[str, Any] | None:
    """
    Formato comum em integrações UAZ/Bubble: ``message`` e ``chat`` no root (sem ``data``).
    ``message`` por vezes vem ``null``; nesse caso usa-se só ``chat`` quando possível.
    """
    raw = body.get("message")
    if isinstance(raw, str) and raw.strip().startswith("{"):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = None
    msg: dict[str, Any] = dict(raw) if isinstance(raw, dict) else {}
    chat = body.get("chat")
    if isinstance(chat, dict):
        if msg:
            _merge_chat_into_message(msg, chat)
        else:
            msg = {}
            _merge_chat_into_message(msg, chat)
        if not (msg.get("text") or "").strip():
            for k in ("lastMessageText", "wa_lastMessageText", "text"):
                v = chat.get(k) if isinstance(chat, dict) else None
                if isinstance(v, str) and v.strip():
                    msg["text"] = v.strip()
                    break
    if isinstance(msg, dict) and not (msg.get("text") or "").strip():
        root_txt = body.get("text")
        if isinstance(root_txt, str) and root_txt.strip():
            msg["text"] = root_txt.strip()
    if not msg:
        return None
    return msg


def _normalize_payload(body: Any) -> tuple[str | None, dict[str, Any] | None]:
    """
    UAZAPI envia ``event: "messages"`` para mensagens novas (OpenAPI); o schema
    WebhookEvent também permite ``event: "message"``. Às vezes vem ``EventType``.
    Bubble/UAZ pode enviar ``message`` + ``chat`` no root sem ``data``.
    """
    if not isinstance(body, dict):
        return None, None
    ev = _webhook_event_from_body(body)
    data = body.get("data")
    if isinstance(data, list):
        # Alguns POSTs enviam ``data: [ { Message }, ... ]`` — sem isto,
        # ``not isinstance(data, dict)`` devolve ``no data`` com HTTP 200.
        chosen: dict[str, Any] | None = None
        for item in data:
            if isinstance(item, dict):
                chosen = item
                break
        data = chosen
    if isinstance(data, dict):
        # Alguns payloads aninham a mensagem em ``data.message``
        inner = data.get("message")
        if isinstance(inner, dict) and (inner.get("chatid") is not None or inner.get("text") is not None):
            return (str(ev) if ev is not None else None, inner)
        return (str(ev) if ev is not None else None, data)
    if body.get("chatid") is not None or body.get("fromMe") is not None or "text" in body:
        return (str(ev) if ev is not None else "message", body)
    flat = _message_dict_from_flat_uaz_body(body)
    if flat is not None:
        return (str(ev) if ev is not None else "message", flat)
    return None, None


def _is_incoming_chat_event(event: str | None) -> bool:
    if event is None:
        return True
    e = str(event).strip().lower()
    if e in ("message", "messages"):
        return True
    return "message" in e


def build_uazapi_router(agent: Agent) -> APIRouter:
    router = APIRouter(tags=["Maria WhatsApp (UAZAPI)"])

    @router.post("/webhooks/uazapi")
    def uazapi_webhook(
        response: Response,
        payload: dict[str, Any] = Body(...),
        x_maria_webhook_secret: str | None = Header(default=None, alias="X-Maria-Webhook-Secret"),
    ) -> dict[str, Any]:
        log = get_maria_logger()
        expected = uazapi_webhook_secret_expected()
        if expected is not None and (x_maria_webhook_secret or "").strip() != expected:
            response.status_code = status.HTTP_401_UNAUTHORIZED
            return {"ok": False, "error": "unauthorized"}

        if not uazapi_configured():
            log.warning("[yellow]UAZAPI[/] webhook recebido sem [cyan]UAZAPI_TOKEN[/] — ignoro envio")
            # 200 para a UAZ não reencaminhar indefinidamente; diagnóstico nos logs.
            return {"ok": False, "reason": "uazapi_token not configured"}

        event, data = _normalize_payload(payload)
        log.info(
            "[cyan]UAZAPI[/] webhook · event=%s · data_keys=%s",
            event,
            sorted(data.keys()) if isinstance(data, dict) else type(data).__name__,
        )
        if not _is_incoming_chat_event(event):
            log.info("[cyan]UAZAPI[/] ignorado · evento não-chat · %s", event)
            return {"ok": True, "skipped": f"event:{event}"}
        if not isinstance(data, dict):
            log.warning(
                "[yellow]UAZAPI[/] sem objeto de mensagem (payload_keys=%s)",
                sorted(payload.keys()) if isinstance(payload, dict) else type(payload).__name__,
            )
            return {"ok": False, "reason": "no data"}

        if uaz_should_ignore_for_chatbot(data):
            log.info("[cyan]UAZAPI[/] ignorado · fromMe/grupo ou regra de skip")
            return {"ok": True, "skipped": "ignored_message"}

        user_turn = uaz_incoming_user_turn(data)
        if not user_turn.strip():
            log.info("[cyan]UAZAPI[/] ignorado · turno vazio (sem text/content/button)")
            return {"ok": True, "skipped": "empty_turn"}

        user_id = maria_user_id_from_uaz_message(data)
        session_id = uaz_session_id_for_maria(data)
        number = uaz_send_number_from_message(data)
        if not user_id or not session_id or not number:
            log.warning(
                "[yellow]UAZAPI[/] payload sem user/session/number resolvível · "
                "chatid=%s sender_pn=%s",
                str(data.get("chatid"))[:48] if data.get("chatid") else None,
                str(data.get("sender_pn"))[:48] if data.get("sender_pn") else None,
            )
            return {"ok": False, "reason": "missing_ids"}

        reply_id = data.get("messageid")
        reply_id_str = str(reply_id).strip() if reply_id is not None and str(reply_id).strip() else None

        session_state: dict[str, Any] = {
            "current_user_id": user_id,
            "origem_canal": "WhatsApp",
        }
        if user_id.startswith("wa_"):
            digits = user_id[3:]
            if digits.isdigit():
                session_state["telefone_whatsapp"] = digits

        log.info(
            "[cyan]UAZAPI[/] agente · user=%s · turn_preview=%s",
            str(user_id)[:32],
            (user_turn[:80] + "…") if len(user_turn) > 80 else user_turn,
        )
        try:
            run_output = agent.run(
                user_turn,
                user_id=user_id,
                session_id=session_id,
                session_state=session_state,
            )
        except Exception as e:  # noqa: BLE001
            log.exception("[red]UAZAPI[/] falha no agent.run — %s", e)
            response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            return {"ok": False, "error": str(e)}

        content = getattr(run_output, "content", None)
        reply_raw = content if isinstance(content, str) else (str(content) if content is not None else "")
        body_text, choices = split_maria_reply_for_uaz(reply_raw)
        if not body_text and not choices:
            log.info("[cyan]UAZAPI[/] ignorado · resposta do agente vazia após parse")
            return {"ok": True, "skipped": "empty_assistant"}

        try:
            if choices:
                uaz_send_button_menu(
                    number,
                    body_text or "Escolha uma opção:",
                    choices,
                    replyid=reply_id_str,
                )
            else:
                uaz_send_text(number, body_text, replyid=reply_id_str)
        except Exception as e:  # noqa: BLE001
            log.exception("[red]UAZAPI[/] falha ao enviar resposta — %s", e)
            response.status_code = status.HTTP_502_BAD_GATEWAY
            return {"ok": False, "error": str(e)}

        return {"ok": True}

    return router
