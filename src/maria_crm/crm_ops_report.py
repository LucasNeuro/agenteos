"""Endpoint operacional do CRM (contagens e saúde básica)."""

from __future__ import annotations

import hmac
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Header, HTTPException, Query

from .config import crm_configured, maria_crm_ops_secret, supabase_service_role_key, supabase_url


def _headers_count() -> dict[str, str]:
    key = supabase_service_role_key()
    if not key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY em falta")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Prefer": "count=exact",
    }


def _parse_count_header(content_range: str | None) -> int:
    if not content_range or "/" not in content_range:
        return 0
    tail = content_range.rsplit("/", 1)[-1].strip()
    if not tail.isdigit():
        return 0
    return int(tail)


def _count_table(table: str, *, params: dict[str, str] | None = None) -> int:
    base = supabase_url()
    if not base:
        raise RuntimeError("SUPABASE_URL em falta")
    url = f"{base.rstrip('/')}/rest/v1/{table}"
    merged = {"select": "id", "limit": "1"}
    if params:
        merged.update(params)
    r = httpx.get(url, headers=_headers_count(), params=merged, timeout=30.0)
    r.raise_for_status()
    return _parse_count_header(r.headers.get("content-range"))


def _require_secret_if_configured(
    *,
    query_token: str | None,
    header_token: str | None,
) -> None:
    expected = maria_crm_ops_secret()
    if not expected:
        return
    got = (query_token or header_token or "").strip().encode("utf-8")
    exp = expected.encode("utf-8")
    if len(got) != len(exp) or not hmac.compare_digest(got, exp):
        raise HTTPException(status_code=401, detail="Unauthorized")


def build_crm_ops_router() -> APIRouter:
    router = APIRouter(tags=["CRM Ops"])

    @router.get("/admin/crm/ops")
    def crm_ops(
        t: str | None = Query(default=None, description="Token opcional igual a MARIA_CRM_OPS_SECRET"),
        x_maria_crm_ops_secret: str | None = Header(default=None, alias="X-Maria-Crm-Ops-Secret"),
    ) -> dict[str, Any]:
        _require_secret_if_configured(query_token=t, header_token=x_maria_crm_ops_secret)
        if not crm_configured():
            return {"ok": False, "reason": "crm_not_configured"}

        now = datetime.now(timezone.utc)
        since_24h = (now - timedelta(hours=24)).isoformat()
        since_1h = (now - timedelta(hours=1)).isoformat()

        sessions_total = _count_table("maria_sessions")
        messages_total = _count_table("maria_messages")
        leads_total = _count_table("maria_leads")

        sessions_24h = _count_table("maria_sessions", params={"created_at": f"gte.{since_24h}"})
        messages_24h = _count_table("maria_messages", params={"created_at": f"gte.{since_24h}"})
        leads_24h = _count_table("maria_leads", params={"created_at": f"gte.{since_24h}"})

        stubs_24h = _count_table(
            "maria_leads",
            params={
                "created_at": f"gte.{since_24h}",
                "caracteristicas_adicionais": "like.*[AUTO_STUB]*",
            },
        )
        messages_1h = _count_table("maria_messages", params={"created_at": f"gte.{since_1h}"})

        return {
            "ok": True,
            "generated_at_utc": now.isoformat(),
            "totals": {
                "sessions": sessions_total,
                "messages": messages_total,
                "leads": leads_total,
            },
            "last_24h": {
                "sessions": sessions_24h,
                "messages": messages_24h,
                "leads": leads_24h,
                "auto_stubs": stubs_24h,
            },
            "last_1h": {
                "messages": messages_1h,
            },
        }

    return router
