"""Extrai corpo + botões UAZAPI (`POST /send/menu` type button) da resposta da Mari."""

from __future__ import annotations

# Até 3 botões de resposta — limite prático WhatsApp / UAZ para `type: "button"`.
_MAX_BUTTONS = 3

_START = "<<<UAZ_BUTTONS>>>"
_END = "<<<END_UAZ_BUTTONS>>>"


def split_maria_reply_for_uaz(raw: str) -> tuple[str, list[str] | None]:
    """
    Se a resposta incluir o bloco opcional, devolve texto principal + lista ``choices`` UAZ.

    Cada linha do bloco: ``Rótulo|id`` ou só ``Rótulo`` (id = rótulo). Máx. 3 linhas.
    """
    if _START not in raw or _END not in raw:
        return (raw.strip(), None)
    before, rest = raw.split(_START, 1)
    middle, _after = rest.split(_END, 1)
    lines = [ln.strip() for ln in middle.strip().splitlines() if ln.strip()]
    choices = lines[:_MAX_BUTTONS]
    body = before.strip()
    if not choices:
        return (raw.strip(), None)
    return (body, choices)
