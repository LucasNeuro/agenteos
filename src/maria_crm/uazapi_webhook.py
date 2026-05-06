"""Webhook HTTP UAZAPI → run do ``hub_agent`` → resposta WhatsApp (texto ou botões)."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from agno.agent import Agent
from fastapi import APIRouter, Body, Header, Response, status

from .config import (
    maria_media_batch_flush_after_sec,
    uazapi_configured,
    uazapi_send_reply_to_incoming_message,
    uazapi_webhook_secret_expected,
)
from .rich_logging import get_maria_logger
from .uazapi_client import uaz_send_button_menu, uaz_send_list_menu, uaz_send_text
from .property_ingest import ingest_property_image_from_uaz
from .uazapi_dedupe import webhook_allow_event_key
from .uazapi_ids import (
    maria_expand_whatsapp_triage_turn,
    maria_user_id_from_uaz_message,
    uaz_incoming_user_turn,
    uaz_send_number_from_message,
    uaz_session_id_for_maria,
    uaz_should_ignore_for_chatbot,
)
from .uazapi_media import uaz_message_is_probably_image
from .uazapi_parse import parse_maria_reply_for_uaz

_MEDIA_BATCH_TTL_SEC = 20 * 60
_media_batch_lock = threading.Lock()


@dataclass
class _MediaBatchState:
    imovel_id: str | None = None
    total: int = 0
    accepted: int = 0
    rejected: int = 0
    unknown: int = 0
    last_reason: str | None = None
    last_valid_summary: str | None = None
    updated_at_monotonic: float = 0.0


_media_batches_by_session: dict[str, _MediaBatchState] = {}


def _cleanup_old_media_batches(now: float) -> None:
    stale = [k for k, v in _media_batches_by_session.items() if now - v.updated_at_monotonic > _MEDIA_BATCH_TTL_SEC]
    for k in stale:
        del _media_batches_by_session[k]


def _media_batch_add(session_id: str, media_ingest: Any) -> None:
    now = time.monotonic()
    with _media_batch_lock:
        _cleanup_old_media_batches(now)
        st = _media_batches_by_session.get(session_id)
        if st is None:
            st = _MediaBatchState()
            _media_batches_by_session[session_id] = st
        st.total += 1
        st.updated_at_monotonic = now
        if media_ingest is not None:
            st.imovel_id = media_ingest.imovel_id
            vp = media_ingest.valid_property_photo
            if vp is True:
                st.accepted += 1
                if media_ingest.vision_summary:
                    st.last_valid_summary = str(media_ingest.vision_summary)[:500]
            elif vp is False:
                st.rejected += 1
            else:
                st.unknown += 1
            if media_ingest.validation_reason:
                st.last_reason = str(media_ingest.validation_reason)[:500]


def _media_batch_consume(session_id: str) -> _MediaBatchState | None:
    now = time.monotonic()
    with _media_batch_lock:
        _cleanup_old_media_batches(now)
        return _media_batches_by_session.pop(session_id, None)


_session_gates_guard = threading.Lock()
_session_gates: dict[str, threading.Lock] = {}

_batch_flush_registry_lock = threading.Lock()
_batch_flush_timers: dict[str, threading.Timer] = {}


def _session_run_gate(session_id: str) -> threading.Lock:
    sid = str(session_id)
    with _session_gates_guard:
        gate = _session_gates.get(sid)
        if gate is None:
            gate = threading.Lock()
            _session_gates[sid] = gate
        return gate


@contextmanager
def _holding_session_run_gate(session_id: str):
    gate = _session_run_gate(session_id)
    gate.acquire()
    try:
        yield
    finally:
        gate.release()


def _cancel_media_batch_flush(session_id: str) -> None:
    sid = str(session_id)
    with _batch_flush_registry_lock:
        t = _batch_flush_timers.pop(sid, None)
    if t is not None:
        t.cancel()


def _base_maria_session_state(user_id: str) -> dict[str, Any]:
    session_state: dict[str, Any] = {
        "current_user_id": user_id,
        "origem_canal": "WhatsApp",
    }
    if user_id.startswith("wa_"):
        digits = user_id[3:]
        if digits.isdigit():
            session_state["telefone_whatsapp"] = digits
    return session_state


def _merge_media_batch_into_session_state(session_state: dict[str, Any], batch: _MediaBatchState) -> None:
    if batch.imovel_id:
        session_state["maria_rascunho_imovel_id"] = batch.imovel_id
    if batch.accepted > 0:
        session_state["maria_ultima_imagem_valida_imovel"] = True
        if batch.last_valid_summary:
            session_state["maria_ultima_imagem_resumo"] = batch.last_valid_summary
    elif batch.rejected > 0 and batch.unknown == 0:
        session_state["maria_ultima_imagem_valida_imovel"] = False
        session_state.pop("maria_ultima_imagem_resumo", None)
    else:
        session_state["maria_ultima_imagem_valida_imovel"] = None
    session_state["maria_ultima_imagem_validacao_motivo"] = (
        f"Lote de fotos recebido: {batch.total} arquivo(s), "
        f"{batch.accepted} aceito(s), {batch.rejected} rejeitado(s), {batch.unknown} sem validação."
    )[:500]
    if batch.last_reason:
        session_state["maria_ultima_imagem_validacao_motivo"] = (
            f"{session_state['maria_ultima_imagem_validacao_motivo']} Último motivo: {batch.last_reason}"
        )[:500]


def _merge_single_ingest_into_session_state(session_state: dict[str, Any], media_ingest: Any) -> None:
    session_state["maria_rascunho_imovel_id"] = media_ingest.imovel_id
    session_state["maria_ultima_imagem_valida_imovel"] = media_ingest.valid_property_photo
    if media_ingest.validation_reason:
        session_state["maria_ultima_imagem_validacao_motivo"] = str(
            media_ingest.validation_reason
        )[:500]
    if media_ingest.valid_property_photo is True and media_ingest.vision_summary:
        session_state["maria_ultima_imagem_resumo"] = media_ingest.vision_summary
    elif media_ingest.valid_property_photo is False:
        session_state.pop("maria_ultima_imagem_resumo", None)


@dataclass(frozen=True)
class _UazAgentRunResult:
    kind: str  # sent | skipped_empty | error
    http_status: int = 200
    error: str | None = None


def _run_uazapi_agent_reply(
    *,
    agent: Agent,
    user_id: str,
    session_id: str | int,
    session_state: dict[str, Any],
    user_turn: str,
    number: str,
    reply_id_str: str | None,
    log: Any,
) -> _UazAgentRunResult:
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
        return _UazAgentRunResult(
            kind="error",
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error=str(e),
        )

    content = getattr(run_output, "content", None)
    reply_raw = content if isinstance(content, str) else (str(content) if content is not None else "")
    parsed = parse_maria_reply_for_uaz(reply_raw)
    log.info(
        "[cyan]UAZAPI[/] parse · kind=%s · buttons=%d · list_items=%d",
        parsed.send_kind,
        len(parsed.button_choices),
        len(parsed.list_choices),
    )
    if not parsed.body.strip() and not parsed.has_interactive:
        log.info("[cyan]UAZAPI[/] ignorado · resposta do agente vazia após parse")
        return _UazAgentRunResult(kind="skipped_empty")

    try:
        if parsed.send_kind == "list" and parsed.list_button and parsed.list_choices:
            uaz_send_list_menu(
                number,
                parsed.body or "Escolha uma opção:",
                parsed.list_button,
                list(parsed.list_choices),
                footer_text=parsed.footer_text,
                replyid=reply_id_str,
            )
        elif parsed.send_kind == "button" and parsed.button_choices:
            uaz_send_button_menu(
                number,
                parsed.body or "Escolha uma opção:",
                list(parsed.button_choices),
                replyid=reply_id_str,
            )
        else:
            uaz_send_text(number, parsed.body.strip() or reply_raw.strip(), replyid=reply_id_str)
    except Exception as e:  # noqa: BLE001
        log.exception("[red]UAZAPI[/] falha ao enviar resposta — %s", e)
        return _UazAgentRunResult(
            kind="error",
            http_status=status.HTTP_502_BAD_GATEWAY,
            error=str(e),
        )

    return _UazAgentRunResult(kind="sent")


def _schedule_media_batch_flush(
    *,
    agent: Agent,
    user_id: str,
    session_id: str,
    number: str,
    reply_id_str: str | None,
    log: Any,
) -> None:
    delay = maria_media_batch_flush_after_sec()
    if delay <= 0:
        return
    sid = str(session_id)

    def fire() -> None:
        try:
            with _holding_session_run_gate(sid):
                batch = _media_batch_consume(sid)
                if batch is None:
                    log.info(
                        "[cyan]UAZAPI[/] flush lote · já consumido ou vazio · sessão=%s",
                        sid[:32],
                    )
                    return
                session_state = _base_maria_session_state(user_id)
                _merge_media_batch_into_session_state(session_state, batch)
                user_turn = (
                    f"Acabei de enviar {batch.total} foto(s) do imóvel pelo WhatsApp (só imagens, sem texto). "
                    "Trata o registo e responde com o próximo passo para o cliente."
                )
                res = _run_uazapi_agent_reply(
                    agent=agent,
                    user_id=user_id,
                    session_id=session_id,
                    session_state=session_state,
                    user_turn=user_turn,
                    number=number,
                    reply_id_str=reply_id_str,
                    log=log,
                )
                if res.kind == "error":
                    log.warning("[yellow]UAZAPI[/] flush lote · falha · %s", res.error)
        finally:
            with _batch_flush_registry_lock:
                _batch_flush_timers.pop(sid, None)

    with _batch_flush_registry_lock:
        old = _batch_flush_timers.pop(sid, None)
        if old is not None:
            old.cancel()
        timer = threading.Timer(delay, fire)
        timer.daemon = True
        _batch_flush_timers[sid] = timer
    timer.start()
    log.info(
        "[cyan]UAZAPI[/] mídia em lote · flush agendado · sessão=%s · em %.1fs",
        sid[:24],
        delay,
    )


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


def _event_dedupe_key(data: dict[str, Any]) -> str | None:
    """
    Chave estável para idempotência:
    1) usa ``messageid`` quando existir;
    2) fallback fingerprint para payloads sem id.
    """
    raw_mid = data.get("messageid")
    if raw_mid is not None and str(raw_mid).strip():
        return f"mid:{str(raw_mid).strip()}"

    parts: list[str] = []
    for key in ("chatid", "sender_pn", "sender", "text", "body", "buttonOrListid", "convertOptions", "fileURL", "fileUrl"):
        v = data.get(key)
        if v is None:
            continue
        s = str(v).strip()
        if s:
            parts.append(s[:160])
    for key in ("sendertime", "timestamp", "date", "time"):
        v = data.get(key)
        if v is None:
            continue
        s = str(v).strip()
        if s:
            parts.append(s)
            break
    if not parts:
        return None
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()  # noqa: S324
    return f"fp:{digest}"


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

        try:
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

            dedupe_key = _event_dedupe_key(data)
            if dedupe_key and not webhook_allow_event_key(dedupe_key):
                log.info("[cyan]UAZAPI[/] ignorado · evento duplicado (%s)", dedupe_key[:48])
                return {"ok": True, "skipped": "duplicate_event"}

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

            probably_image = uaz_message_is_probably_image(data)
            media_ingest = None
            if probably_image:
                try:
                    digits_for_sess: str | None = None
                    if user_id.startswith("wa_"):
                        d = user_id[3:]
                        if d.isdigit():
                            digits_for_sess = d
                    media_ingest = ingest_property_image_from_uaz(
                        data,
                        external_session_id=str(session_id),
                        phone_digits=digits_for_sess,
                    )
                except Exception as e:  # noqa: BLE001
                    log.exception("[red]UAZAPI[/] falha ingestão imóvel/mídia — %s", e)

            user_turn = uaz_incoming_user_turn(data)
            expanded = maria_expand_whatsapp_triage_turn(user_turn)
            if expanded != user_turn:
                log.info(
                    "[cyan]UAZAPI[/] triagem expandida · era=%s · agora=%s…",
                    (user_turn[:48] + "…") if len(user_turn) > 48 else user_turn,
                    (expanded[:72] + "…") if len(expanded) > 72 else expanded,
                )
                user_turn = expanded

            reply_id_str: str | None = None
            if uazapi_send_reply_to_incoming_message():
                reply_id = data.get("messageid")
                reply_id_str = str(reply_id).strip() if reply_id is not None and str(reply_id).strip() else None

            if probably_image and not user_turn.strip():
                _media_batch_add(str(session_id), media_ingest)
                log.info("[cyan]UAZAPI[/] mídia em lote · sessão=%s · aguardando fim do envio", str(session_id)[:24])
                _schedule_media_batch_flush(
                    agent=agent,
                    user_id=user_id,
                    session_id=str(session_id),
                    number=number,
                    reply_id_str=reply_id_str,
                    log=log,
                )
                return {"ok": True, "skipped": "image_only_buffered"}
            if not user_turn.strip():
                log.info("[cyan]UAZAPI[/] ignorado · turno vazio (sem text/content/button)")
                return {"ok": True, "skipped": "empty_turn"}

            with _holding_session_run_gate(str(session_id)):
                _cancel_media_batch_flush(str(session_id))
                session_state = _base_maria_session_state(user_id)
                batch = _media_batch_consume(str(session_id))
                if batch is not None:
                    _merge_media_batch_into_session_state(session_state, batch)
                if media_ingest is not None:
                    _merge_single_ingest_into_session_state(session_state, media_ingest)

                run_res = _run_uazapi_agent_reply(
                    agent=agent,
                    user_id=user_id,
                    session_id=session_id,
                    session_state=session_state,
                    user_turn=user_turn,
                    number=number,
                    reply_id_str=reply_id_str,
                    log=log,
                )
        except Exception as e:  # noqa: BLE001
            log.exception("[red]UAZAPI[/] erro inesperado no webhook — %s", e)
            response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            return {"ok": False, "error": "internal_webhook_error"}

        if run_res.kind == "error":
            response.status_code = run_res.http_status
            return {"ok": False, "error": run_res.error}
        if run_res.kind == "skipped_empty":
            return {"ok": True, "skipped": "empty_assistant"}
        return {"ok": True}

    return router
