"""Deteção de mídia (imagem) em payloads UAZAPI / Message."""

from __future__ import annotations

import json
from typing import Any, Mapping


def _as_dict(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip().startswith("{"):
        try:
            o = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return o if isinstance(o, dict) else None
    return None


def uaz_message_image_url(data: Mapping[str, Any]) -> str | None:
    """
    Devolve URL ou caminho HTTP(S) de imagem quando existir (``fileURL``, ``content``).
    """
    for key in ("fileURL", "fileUrl", "mediaUrl", "url"):
        v = data.get(key)
        if isinstance(v, str) and v.strip().lower().startswith("http"):
            return v.strip()
    content = _as_dict(data.get("content"))
    if content:
        for key in ("URL", "url", "fileURL", "mediaUrl", "directPath"):
            v = content.get(key)
            if isinstance(v, str) and v.strip().lower().startswith("http"):
                return v.strip()
    return None


def uaz_message_image_mime(data: Mapping[str, Any]) -> str | None:
    for key in ("mimetype", "mimeType", "mime"):
        v = data.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip().split(";")[0].lower()
    content = _as_dict(data.get("content"))
    if content:
        for key in ("mimetype", "mimeType"):
            v = content.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip().split(";")[0].lower()
    return None


def uaz_message_is_probably_image(data: Mapping[str, Any]) -> bool:
    """Heurística: tipo de mensagem ou mime de imagem ou URL de ficheiro de imagem."""
    mt = data.get("messageType")
    if isinstance(mt, str) and mt.strip().lower() in (
        "image",
        "imagemsg",
        "sticker",
        "ptv",
    ):
        return True
    mime = uaz_message_image_mime(data) or ""
    if mime.startswith("image/"):
        return True
    u = (uaz_message_image_url(data) or "").lower()
    if any(u.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif")):
        return True
    return bool(uaz_message_image_url(data)) and "image" in str(data.get("messageType", "")).lower()


def uaz_message_caption(data: Mapping[str, Any]) -> str:
    t = data.get("text")
    if isinstance(t, str) and t.strip():
        return t.strip()
    content = _as_dict(data.get("content"))
    if content:
        for key in ("caption", "text"):
            v = content.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return ""
