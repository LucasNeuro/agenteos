"""Cliente HTTP mínimo UAZAPI — /send/text e /send/menu (botões e listas interactivas)."""

from __future__ import annotations

from typing import Any

import httpx

from .config import uazapi_base_url, uazapi_token
from .rich_logging import get_maria_logger


def _headers() -> dict[str, str]:
    tok = uazapi_token()
    if not tok:
        raise RuntimeError("UAZAPI_TOKEN em falta")
    return {"token": tok, "Content-Type": "application/json"}


def uazapi_post(path: str, payload: dict[str, Any], *, timeout: float = 90.0) -> dict[str, Any]:
    base = uazapi_base_url().rstrip("/")
    url = f"{base}{path}" if path.startswith("/") else f"{base}/{path}"
    r = httpx.post(url, headers=_headers(), json=payload, timeout=timeout)
    r.raise_for_status()
    if r.content:
        try:
            out = r.json()
            return out if isinstance(out, dict) else {"raw": out}
        except Exception:  # noqa: BLE001
            return {"raw_text": r.text[:500]}
    return {}


def uaz_send_text(
    number: str,
    text: str,
    *,
    replyid: str | None = None,
    readchat: bool = True,
) -> None:
    log = get_maria_logger()
    body: dict[str, Any] = {"number": number, "text": text, "readchat": readchat}
    if replyid:
        body["replyid"] = replyid
    uazapi_post("/send/text", body)
    log.info("[bold green]UAZAPI ✓[/] /send/text · n=[cyan]%s[/]", str(number)[:28])


def uaz_send_button_menu(
    number: str,
    text: str,
    choices: list[str],
    *,
    footer_text: str | None = None,
    replyid: str | None = None,
    readchat: bool = True,
) -> None:
    log = get_maria_logger()
    body: dict[str, Any] = {
        "number": number,
        "type": "button",
        "text": text,
        "choices": choices,
        "readchat": readchat,
    }
    if footer_text:
        body["footerText"] = footer_text
    if replyid:
        body["replyid"] = replyid
    uazapi_post("/send/menu", body)
    log.info(
        "[bold green]UAZAPI ✓[/] /send/menu button · n=[cyan]%s[/] · opções=%d",
        str(number)[:28],
        len(choices),
    )


def uaz_send_list_menu(
    number: str,
    text: str,
    list_button: str,
    choices: list[str],
    *,
    footer_text: str | None = None,
    replyid: str | None = None,
    readchat: bool = True,
) -> None:
    """Menu tipo lista (botão estilo *Selecione a unidade* que abre opções — ver doc UAZ ``type: list``)."""
    log = get_maria_logger()
    body: dict[str, Any] = {
        "number": number,
        "type": "list",
        "text": text,
        "listButton": list_button.strip() or "Ver opções",
        "choices": choices,
        "readchat": readchat,
    }
    if footer_text:
        body["footerText"] = footer_text
    if replyid:
        body["replyid"] = replyid
    uazapi_post("/send/menu", body)
    log.info(
        "[bold green]UAZAPI ✓[/] /send/menu list · n=[cyan]%s[/] · itens=%d · botão=%s",
        str(number)[:28],
        len(choices),
        str(list_button)[:24],
    )
