"""Upload de objectos para Supabase Storage (API REST)."""

from __future__ import annotations

from typing import Any, Mapping
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


def _headers_service_get() -> dict[str, str]:
    key = supabase_service_role_key()
    if not key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY em falta")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }


def supabase_storage_list_path(bucket: str, prefix: str = "") -> list[Mapping[str, Any]]:
    """
    Lista objectos num prefixo (API Storage v1). `prefix` deve ser `''` ou terminar em `/`.
    """
    base = supabase_url()
    if not base:
        raise RuntimeError("SUPABASE_URL em falta")
    enc_bucket = quote(bucket.strip(), safe="")
    url = f"{base.rstrip('/')}/storage/v1/object/list/{enc_bucket}"
    pf = prefix or ""
    all_rows: list[Mapping[str, Any]] = []
    offset = 0
    page = 1000
    while True:
        body: dict[str, Any] = {
            "prefix": pf,
            "limit": page,
            "offset": offset,
            "sortBy": {"column": "name", "order": "asc"},
        }
        r = httpx.post(
            url,
            headers={**_headers_service_get(), "Content-Type": "application/json"},
            json=body,
            timeout=120.0,
        )
        r.raise_for_status()
        data = r.json()
        batch = data if isinstance(data, list) else []
        if not batch:
            break
        all_rows.extend(batch)
        if len(batch) < page:
            break
        offset += page
    return all_rows


def supabase_storage_walk_file_paths(bucket: str, root_prefix: str = "") -> list[str]:
    """
    Percorre pastas no bucket e devolve caminhos de ficheiro (ex.: `politicas/guia.md`).
    Pastas: entradas com `id` null na resposta do list.
    """
    root = root_prefix.replace("\\", "/")
    if root and not root.endswith("/"):
        root = f"{root}/"

    files: list[str] = []

    def visit(list_prefix: str) -> None:
        for row in supabase_storage_list_path(bucket, list_prefix):
            name = (row.get("name") or "").strip()
            if not name:
                continue
            is_folder = row.get("id") is None
            if is_folder:
                visit(f"{list_prefix}{name}/")
            else:
                files.append(f"{list_prefix}{name}".rstrip("/"))

    visit(root)
    return files


def supabase_storage_download_bytes(*, bucket: str, object_path: str) -> bytes:
    """Descarrega ficheiro privado (service role)."""
    base = supabase_url()
    if not base:
        raise RuntimeError("SUPABASE_URL em falta")
    enc_bucket = quote(bucket.strip(), safe="")
    enc_path = _encode_object_path(object_path)
    url = f"{base.rstrip('/')}/storage/v1/object/{enc_bucket}/{enc_path}"
    r = httpx.get(url, headers=_headers_service_get(), timeout=120.0)
    r.raise_for_status()
    return r.content
