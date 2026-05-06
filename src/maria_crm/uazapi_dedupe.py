"""Evita reprocessar webhooks duplicados do WhatsApp/UAZAPI."""

from __future__ import annotations

import threading
import time

from .config import uazapi_webhook_message_dedupe_ttl_sec

_lock = threading.Lock()
_seen: dict[str, float] = {}
_MAX_KEYS = 5000


def _allow_key(key: str | None) -> bool:
    ttl = uazapi_webhook_message_dedupe_ttl_sec()
    if ttl <= 0:
        return True
    if key is None:
        return True
    mid = str(key).strip()
    if not mid:
        return True
    now = time.monotonic()
    with _lock:
        stale = [k for k, t in _seen.items() if now - t > ttl]
        for k in stale:
            del _seen[k]
        if mid in _seen:
            return False
        if len(_seen) >= _MAX_KEYS:
            for k, _ in sorted(_seen.items(), key=lambda x: x[1])[: _MAX_KEYS // 2]:
                del _seen[k]
        _seen[mid] = now
        return True


def webhook_allow_message_id(message_id: str | None) -> bool:
    """
    Compatibilidade com chamadas legadas (dedupe por ``messageid``).
    """
    if message_id is None:
        return True
    return _allow_key(f"mid:{str(message_id).strip()}")


def webhook_allow_event_key(event_key: str | None) -> bool:
    """
    Dedupe por chave estável do evento (messageid ou fingerprint de fallback).
    """
    return _allow_key(event_key)
