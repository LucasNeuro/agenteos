"""Upload de objectos para Supabase Storage (API REST)."""

from __future__ import annotations

from urllib.parse import quote

import httpx

from .config import supabase_service_role_key, supabase_url


def _headers_upload(content_type: str) -> dict[str, str]:
    key = supabase_service_role_key()
    if not key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY em falta")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": content_type,
    }


def _encode_object_path(path: str) -> str:
    return "/".join(quote(part, safe="") for part in path.strip("/").split("/"))


def supabase_upload_bytes(
    *,
    bucket: str,
    object_path: str,
    data: bytes,
    content_type: str,
    upsert: bool = True,
) -> None:
    base = supabase_url().rstrip("/")
    enc_bucket = quote(bucket.strip(), safe="")
    enc_path = _encode_object_path(object_path)
    url = f"{base}/storage/v1/object/{enc_bucket}/{enc_path}"
    params = {"upsert": "true"} if upsert else {}
    r = httpx.post(
        url,
        params=params,
        headers=_headers_upload(content_type),
        content=data,
        timeout=120.0,
    )
    r.raise_for_status()
