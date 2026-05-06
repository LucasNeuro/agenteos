"""Evita processar o mesmo messageid do WhatsApp duas vezes (webhook duplicado)."""

from __future__ import annotations

import threading
import time

from .config import uazapi_webhook_message_dedupe_ttl_sec

_lock = threading.Lock()
_seen: dict[str, float] = {}
_MAX_KEYS = 5000


def _allow_key_once(key: str | None, *, ttl_seconds: float) -> bool:
    if ttl_seconds <= 0:
        return True
    if key is None:
        return True
    raw = str(key).strip()
    if not raw:
        return True
    now = time.monotonic()
    with _lock:
        stale = [k for k, t in _seen.items() if now - t > ttl_seconds]
        for k in stale:
            del _seen[k]
        if raw in _seen:
            return False
        if len(_seen) >= _MAX_KEYS:
            for k, _ in sorted(_seen.items(), key=lambda x: x[1])[: _MAX_KEYS // 2]:
                del _seen[k]
        _seen[raw] = now
        return True


def webhook_allow_message_id(message_id: str | None) -> bool:
    ttl = uazapi_webhook_message_dedupe_ttl_sec()
    return _allow_key_once(f"mid:{(message_id or '').strip()}", ttl_seconds=ttl)


def webhook_allow_fingerprint(fingerprint: str | None) -> bool:
    """
    Dedupe de fallback para payload sem messageid.

    Usa TTL curto para reduzir falso positivo em mensagens iguais legítimas.
    """
    ttl = min(15.0, max(2.0, uazapi_webhook_message_dedupe_ttl_sec()))
    return _allow_key_once(f"fp:{(fingerprint or '').strip()}", ttl_seconds=ttl)
