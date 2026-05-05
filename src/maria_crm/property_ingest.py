"""Ingestão de imagens WhatsApp → Storage + `maria_imoveis` / `maria_imovel_midias` + visão opcional."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

import httpx

from .config import (
    crm_configured,
    maria_imovel_storage_bucket,
    maria_property_ingest_enabled,
    maria_vision_enabled,
    maria_vision_model,
    supabase_service_role_key,
    supabase_url,
    uazapi_token,
)
from .rich_logging import get_maria_logger
from .supabase_storage import supabase_upload_bytes
from .uazapi_media import (
    uaz_message_caption,
    uaz_message_image_mime,
    uaz_message_image_url,
    uaz_message_is_probably_image,
)
from .vision_mistral import mistral_describe_image_bytes

_MAX_DOWNLOAD = 12 * 1024 * 1024


def _sb_headers() -> dict[str, str]:
    key = supabase_service_role_key()
    if not key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY em falta")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _rest_get(table: str, params: dict[str, str]) -> list[dict[str, Any]]:
    base = supabase_url().rstrip("/")
    url = f"{base}/rest/v1/{table}"
    r = httpx.get(url, headers=_sb_headers(), params=params, timeout=45.0)
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else []


def _rest_insert(table: str, row: dict[str, Any]) -> list[dict[str, Any]]:
    base = supabase_url().rstrip("/")
    url = f"{base}/rest/v1/{table}"
    r = httpx.post(url, headers=_sb_headers(), json=row, timeout=45.0)
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else [data]


def _rest_patch(table: str, filters: dict[str, str], patch: dict[str, Any]) -> None:
    base = supabase_url().rstrip("/")
    q = "&".join(f"{k}=eq.{v}" for k, v in filters.items())
    url = f"{base}/rest/v1/{table}?{q}"
    r = httpx.patch(url, headers=_sb_headers(), json=patch, timeout=45.0)
    r.raise_for_status()


def _internal_session_id(external_session_id: str) -> str | None:
    rows = _rest_get(
        "maria_sessions",
        {
            "external_session_id": f"eq.{external_session_id}",
            "select": "id",
            "limit": "1",
        },
    )
    if not rows:
        return None
    rid = rows[0].get("id")
    return str(rid) if rid else None


def _ensure_session_row(external_session_id: str, phone_digits: str | None) -> str:
    """Garante linha em `maria_sessions` e devolve UUID interno."""
    found = _internal_session_id(external_session_id)
    if found:
        return found
    row: dict[str, Any] = {
        "external_session_id": external_session_id,
        "channel": "whatsapp",
        "metadata": {},
    }
    if phone_digits:
        row["phone"] = phone_digits
    out = _rest_insert("maria_sessions", row)
    return str(out[0]["id"])


def _get_or_create_draft_imovel(session_uuid: str) -> str:
    rows = _rest_get(
        "maria_imoveis",
        {
            "session_id": f"eq.{session_uuid}",
            "status": "eq.rascunho",
            "select": "id,updated_at",
            "order": "updated_at.desc",
            "limit": "1",
        },
    )
    if rows:
        return str(rows[0]["id"])
    inserted = _rest_insert(
        "maria_imoveis",
        {
            "session_id": session_uuid,
            "origem_canal": "whatsapp",
            "status": "rascunho",
            "metadata": {},
        },
    )
    return str(inserted[0]["id"])


def _safe_segment(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", s)[:120]


def _ext_for_mime(mime: str | None) -> str:
    m = (mime or "").lower()
    if m == "image/png":
        return "png"
    if m in ("image/webp",):
        return "webp"
    if m in ("image/gif",):
        return "gif"
    return "jpg"


def _download_image(url: str) -> tuple[bytes | None, str, str | None]:
    headers: dict[str, str] = {}
    tok = uazapi_token()
    if tok:
        headers["token"] = tok
    try:
        r = httpx.get(url, headers=headers, timeout=90.0, follow_redirects=True)
        r.raise_for_status()
        body = r.content
        if len(body) > _MAX_DOWNLOAD:
            return None, "image/jpeg", "ficheiro demasiado grande"
        ct = r.headers.get("content-type", "").split(";")[0].strip().lower() or "image/jpeg"
        if not ct.startswith("image/"):
            ct = "image/jpeg"
        return body, ct, None
    except Exception as e:  # noqa: BLE001
        return None, "image/jpeg", str(e)[:300]


@dataclass(frozen=True)
class PropertyMediaIngestResult:
    imovel_id: str
    midia_id: str
    storage_path: str
    vision_summary: str | None
    vision_error: str | None


def ingest_property_image_from_uaz(
    data: Mapping[str, Any],
    *,
    external_session_id: str,
    phone_digits: str | None = None,
) -> PropertyMediaIngestResult | None:
    """
    Descarrega imagem (se possível), grava no bucket, linhas nas tabelas, corre visão se ligada.
    """
    log = get_maria_logger()
    if not crm_configured() or not maria_property_ingest_enabled():
        return None
    if not uaz_message_is_probably_image(data):
        return None

    image_url = uaz_message_image_url(data)
    if not image_url:
        log.info("[yellow]Maria imóvel[/] imagem sem URL utilizável (fileURL/content)")
        return None

    session_uuid = _ensure_session_row(external_session_id, phone_digits)
    imovel_id = _get_or_create_draft_imovel(session_uuid)
    bucket = maria_imovel_storage_bucket()

    msg_id = data.get("messageid") or data.get("id") or uuid.uuid4().hex
    msg_key = _safe_segment(str(msg_id))
    sess_key = _safe_segment(external_session_id)

    image_body, resolved_mime, down_err = _download_image(image_url)
    mime_hint = uaz_message_image_mime(data)
    if image_body is None:
        log.warning("[yellow]Maria imóvel[/] falha download mídia: %s · %s", down_err, image_url[:80])
        fail_path = f"_failed/{sess_key}/{msg_key}_{uuid.uuid4().hex[:8]}"
        mid_row = _rest_insert(
            "maria_imovel_midias",
            {
                "imovel_id": imovel_id,
                "storage_bucket": bucket,
                "storage_path": fail_path,
                "mime_type": mime_hint or "image/jpeg",
                "byte_size": 0,
                "source_channel": "whatsapp",
                "whatsapp_message_id": str(msg_id)[:200] if msg_id else None,
                "vision_error": down_err or "download_failed",
            },
        )
        mid = str(mid_row[0]["id"])
        return PropertyMediaIngestResult(
            imovel_id=imovel_id,
            midia_id=mid,
            storage_path=fail_path,
            vision_summary=None,
            vision_error=down_err,
        )

    ext = _ext_for_mime(resolved_mime or mime_hint)
    object_path = f"{sess_key}/{imovel_id}/{msg_key}.{ext}"

    try:
        supabase_upload_bytes(
            bucket=bucket,
            object_path=object_path,
            data=image_body,
            content_type=resolved_mime,
            upsert=True,
        )
    except Exception as e:  # noqa: BLE001
        log.exception("[red]Maria imóvel[/] upload Storage falhou")
        mid_row = _rest_insert(
            "maria_imovel_midias",
            {
                "imovel_id": imovel_id,
                "storage_bucket": bucket,
                "storage_path": object_path,
                "mime_type": resolved_mime,
                "byte_size": len(image_body),
                "source_channel": "whatsapp",
                "whatsapp_message_id": str(msg_id)[:200] if msg_id else None,
                "vision_error": str(e)[:500],
            },
        )
        return PropertyMediaIngestResult(
            imovel_id=imovel_id,
            midia_id=str(mid_row[0]["id"]),
            storage_path=object_path,
            vision_summary=None,
            vision_error=str(e)[:500],
        )

    vision_summary: str | None = None
    vision_error: str | None = None
    vision_model: str | None = None
    if maria_vision_enabled():
        vision_summary, vision_error = mistral_describe_image_bytes(
            image_body,
            mime_type=resolved_mime,
        )
        vision_model = maria_vision_model()

    mid_insert: dict[str, Any] = {
        "imovel_id": imovel_id,
        "storage_bucket": bucket,
        "storage_path": object_path,
        "file_name": f"{msg_key}.{ext}",
        "mime_type": resolved_mime,
        "byte_size": len(image_body),
        "source_channel": "whatsapp",
        "whatsapp_message_id": str(msg_id)[:200] if msg_id else None,
        "vision_provider": "mistral" if maria_vision_enabled() else None,
        "vision_model": vision_model,
        "vision_summary": vision_summary,
        "vision_labels": [],
        "vision_error": vision_error,
        "vision_at": datetime.now(timezone.utc).isoformat()
        if vision_summary or vision_error
        else None,
    }
    mid_row = _rest_insert("maria_imovel_midias", mid_insert)
    mid_id = str(mid_row[0]["id"])

    cap = uaz_message_caption(data)
    summary_bits = []
    if vision_summary:
        summary_bits.append(vision_summary.strip())
    if cap:
        summary_bits.append(f"Legenda WhatsApp: {cap}")
    if summary_bits:
        merged = " · ".join(summary_bits)
        _rest_patch(
            "maria_imoveis",
            {"id": imovel_id},
            {"descricao_resumo": merged[:8000]},
        )

    log.info(
        "[bold green]Maria imóvel ✓[/] imovel=[cyan]%s[/] path=[dim]%s[/]",
        imovel_id[:8],
        object_path[:60],
    )
    return PropertyMediaIngestResult(
        imovel_id=imovel_id,
        midia_id=mid_id,
        storage_path=object_path,
        vision_summary=vision_summary,
        vision_error=vision_error,
    )


def link_imoveis_rascunho_to_lead(*, external_session_id: str, lead_id: str) -> None:
    """Associa imóveis em rascunho da sessão ao lead criado pela tool."""
    if not crm_configured():
        return
    session_uuid = _internal_session_id(external_session_id)
    if not session_uuid:
        return
    base = supabase_url().rstrip("/")
    key = supabase_service_role_key()
    if not key:
        return

    perfil: str | None = None
    try:
        rows = _rest_get(
            "maria_leads",
            {"id": f"eq.{lead_id}", "select": "lead_kind", "limit": "1"},
        )
        if rows:
            lk = rows[0].get("lead_kind")
            if isinstance(lk, str) and lk.strip():
                perfil = lk.strip()
    except Exception:  # noqa: BLE001
        perfil = None

    q = (
        f"session_id=eq.{session_uuid}"
        "&lead_id=is.null"
        "&status=eq.rascunho"
    )
    url = f"{base}/rest/v1/maria_imoveis?{q}"
    patch: dict[str, Any] = {"lead_id": lead_id}
    if perfil:
        patch["perfil_solicitante"] = perfil
    hdr = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    r = httpx.patch(url, headers=hdr, json=patch, timeout=45.0)
    r.raise_for_status()
