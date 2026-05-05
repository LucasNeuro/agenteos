"""Webhook HTTP UAZAPI → run do ``hub_agent`` → resposta WhatsApp (texto ou botões)."""

from __future__ import annotations

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


def _normalize_payload(body: Any) -> tuple[str | None, dict[str, Any] | None]:
    """
    UAZAPI envia ``event: "messages"`` para mensagens novas (OpenAPI); o schema
    WebhookEvent também permite ``event: "message"``. Às vezes vem ``EventType``.
    """
    if not isinstance(body, dict):
        return None, None
    ev = body.get("event") if body.get("event") is not None else body.get("EventType")
    data = body.get("data")
    if isinstance(data, dict):
        # Alguns payloads aninham a mensagem em ``data.message``
        inner = data.get("message")
        if isinstance(inner, dict) and (inner.get("chatid") is not None or inner.get("text") is not None):
            return (str(ev) if ev is not None else None, inner)
        return (str(ev) if ev is not None else None, data)
    if body.get("chatid") is not None or body.get("fromMe") is not None or "text" in body:
        return "message", body
    return None, None


def _is_incoming_chat_event(event: str | None) -> bool:
    if event is None:
        return True
    e = str(event).strip().lower()
    return e in ("message", "messages")


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
        if not _is_incoming_chat_event(event):
            return {"ok": True, "skipped": f"event:{event}"}
        if not isinstance(data, dict):
            return {"ok": False, "reason": "no data"}

        if uaz_should_ignore_for_chatbot(data):
            return {"ok": True, "skipped": "ignored_message"}

        user_turn = uaz_incoming_user_turn(data)
        if not user_turn.strip():
            return {"ok": True, "skipped": "empty_turn"}

        user_id = maria_user_id_from_uaz_message(data)
        session_id = uaz_session_id_for_maria(data)
        number = uaz_send_number_from_message(data)
        if not user_id or not session_id or not number:
            log.warning("[yellow]UAZAPI[/] payload sem user/session/number resolvível")
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
