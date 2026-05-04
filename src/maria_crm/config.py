from __future__ import annotations

import os


def supabase_url() -> str | None:
    v = os.getenv("SUPABASE_URL", "").strip()
    return v or None


def supabase_service_role_key() -> str | None:
    v = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    return v or None


def webhook_maria_leads_url() -> str | None:
    v = os.getenv("WEBHOOK_MARIA_LEADS_URL", "").strip()
    return v or None


def crm_configured() -> bool:
    return bool(supabase_url() and supabase_service_role_key())
