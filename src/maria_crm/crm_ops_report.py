"""Relatório operacional simples do CRM (JSON), protegido por segredo."""

from __future__ import annotations

import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Header, HTTPException, Query

from .config import crm_configured, supabase_service_role_key, supabase_url


def _secret() -> str | None:
    raw = os.getenv("MARIA_CRM_REPORT_SECRET", "").strip()
    return raw or None


def _headers_count() -> dict[str, str]:
    key = supabase_service_role_key()
    if not key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY em falta")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Prefer": "count=exact",
    }


def _assert_secret(provided: str | None, expected: str) -> None:
    got = (provided or "").strip().encode("utf-8")
    exp = expected.encode("utf-8")
    if len(got) != len(exp) or not hmac.compare_digest(got, exp):
        raise HTTPException(status_code=401, detail="Token inválido.")


def _parse_content_range_total(value: str | None) -> int:
    if not value:
        return 0
    # Ex.: "0-0/42" ou "*/0"
    if "/" not in value:
        return 0
    tail = value.rsplit("/", 1)[-1].strip()
    try:
        return int(tail)
    except ValueError:
        return 0


def _count_rows(table: str, params: dict[str, str] | None = None) -> int:
    base = supabase_url()
    if not base:
        raise RuntimeError("SUPABASE_URL em falta")
    query = {
        "select": "id",
        "limit": "1",
    }
    if params:
        query.update(params)
    url = f"{base.rstrip('/')}/rest/v1/{table}"
    r = httpx.get(url, headers=_headers_count(), params=query, timeout=30.0)
    r.raise_for_status()
    return _parse_content_range_total(r.headers.get("content-range"))


def build_crm_ops_router() -> APIRouter | None:
    secret = _secret()
    if not secret:
        return None
    router = APIRouter(tags=["CRM Ops"])

    @router.get("/admin/crm/report")
    def crm_ops_report(
        t: str = Query(..., description="Igual a MARIA_CRM_REPORT_SECRET"),
        hours: int = Query(24, ge=1, le=24 * 30),
        x_maria_crm_report_secret: str | None = Header(default=None, alias="X-Maria-Crm-Report-Secret"),
    ) -> dict[str, Any]:
        _assert_secret(t or x_maria_crm_report_secret, secret)
        if not crm_configured():
            raise HTTPException(status_code=503, detail="CRM não configurado.")

        now = datetime.now(timezone.utc)
        since = now - timedelta(hours=hours)
        since_iso = since.isoformat()

        sessions_total = _count_rows("maria_sessions")
        sessions_window = _count_rows("maria_sessions", {"created_at": f"gte.{since_iso}"})
        messages_window = _count_rows("maria_messages", {"created_at": f"gte.{since_iso}"})
        user_messages_window = _count_rows(
            "maria_messages",
            {"created_at": f"gte.{since_iso}", "role": "eq.user"},
        )
        assistant_messages_window = _count_rows(
            "maria_messages",
            {"created_at": f"gte.{since_iso}", "role": "eq.assistant"},
        )
        leads_total = _count_rows("maria_leads")
        leads_window = _count_rows("maria_leads", {"created_at": f"gte.{since_iso}"})
        leads_without_session = _count_rows("maria_leads", {"session_id": "is.null"})
        leads_with_source_ext = _count_rows("maria_leads", {"source_external_session_id": "not.is.null"})
        leads_auto_stub_window = _count_rows(
            "maria_leads",
            {
                "created_at": f"gte.{since_iso}",
                "caracteristicas_adicionais": "ilike.*[AUTO_STUB]*",
            },
        )
        webhook_errors_window = _count_rows(
            "maria_leads",
            {
                "created_at": f"gte.{since_iso}",
                "webhook_error": "not.is.null",
            },
        )

        leads_by_kind = {
            "cliente_imobiliario": _count_rows("maria_leads", {"lead_kind": "eq.cliente_imobiliario"}),
            "cliente_projetos": _count_rows("maria_leads", {"lead_kind": "eq.cliente_projetos"}),
            "prestador_servico": _count_rows("maria_leads", {"lead_kind": "eq.prestador_servico"}),
            "imobiliaria_corretor": _count_rows("maria_leads", {"lead_kind": "eq.imobiliaria_corretor"}),
        }

        return {
            "ok": True,
            "generated_at_utc": now.replace(microsecond=0).isoformat(),
            "window_hours": hours,
            "window_since_utc": since.replace(microsecond=0).isoformat(),
            "sessions": {
                "total": sessions_total,
                "created_in_window": sessions_window,
            },
            "messages": {
                "total_in_window": messages_window,
                "user_in_window": user_messages_window,
                "assistant_in_window": assistant_messages_window,
            },
            "leads": {
                "total": leads_total,
                "created_in_window": leads_window,
                "without_session": leads_without_session,
                "with_source_external_session_id": leads_with_source_ext,
                "auto_stub_in_window": leads_auto_stub_window,
                "webhook_errors_in_window": webhook_errors_window,
                "by_kind_total": leads_by_kind,
            },
        }

    return router
