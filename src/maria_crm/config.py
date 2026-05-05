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


def auto_stub_webhook_enabled() -> bool:
    """Se true, o lead mínimo automático (stub) também dispara POST no webhook."""
    return os.getenv("MARIA_AUTO_STUB_WEBHOOK", "").strip().lower() in ("1", "true", "yes")


def crm_configured() -> bool:
    return bool(supabase_url() and supabase_service_role_key())


def mem0_api_key() -> str | None:
    v = os.getenv("MEM0_API_KEY", "").strip()
    return v or None


def mem0_configured() -> bool:
    return bool(mem0_api_key())


def use_mem0_integration() -> bool:
    """
    Mem0 (nuvem): **ligado** quando existe MEM0_API_KEY.

    Define MARIA_USE_MEM0=0 (ou false/no) para forçar desligar mesmo com chave
    (ex.: ambiente local sem Mem0).
    """
    if not mem0_configured():
        return False
    raw = os.getenv("MARIA_USE_MEM0", "").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    return True


def mem0_recall_days() -> int:
    raw = os.getenv("MARIA_MEM0_RECALL_DAYS", "15").strip()
    try:
        n = int(raw)
    except ValueError:
        return 15
    return max(1, min(n, 90))


def uazapi_base_url() -> str:
    v = os.getenv("UAZAPI_BASE_URL", "").strip().rstrip("/")
    return v or "https://free.uazapi.com"


def uazapi_token() -> str | None:
    v = os.getenv("UAZAPI_TOKEN", "").strip()
    return v or None


def uazapi_configured() -> bool:
    return bool(uazapi_token())


def uazapi_webhook_secret_expected() -> str | None:
    """Se definido, o POST /webhooks/uazapi deve enviar o mesmo valor no header X-Maria-Webhook-Secret."""
    v = os.getenv("UAZAPI_WEBHOOK_SECRET", "").strip()
    return v or None


def uazapi_send_reply_to_incoming_message() -> bool:
    """
    Se true, ``/send/text`` e ``/send/menu`` recebem ``replyid`` (mensagem citada no WhatsApp).

    Por omissão **false** — respostas em bolha normal; define ``MARIA_UAZAPI_REPLY_TO_USER_MESSAGE=1`` para citar a mensagem do utilizador.
    """
    raw = os.getenv("MARIA_UAZAPI_REPLY_TO_USER_MESSAGE", "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def mem0_append_infer() -> bool:
    """
    Pós-hook Mem0 (`maria_mem0_post_append_turn`): usar inferência do Mem0 para
    extrair factos a partir do turno.

    Por omissão **desligado** (`infer=False`): grava o resumo do turno de forma
    mais previsível no dashboard Mem0. Define `MARIA_MEM0_APPEND_INFER=1` para
    voltar ao modo com extração automática.
    """
    raw = os.getenv("MARIA_MEM0_APPEND_INFER", "").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    return False


def maria_imovel_storage_bucket() -> str:
    return os.getenv("MARIA_IMOVEL_STORAGE_BUCKET", "maria-imoveis").strip() or "maria-imoveis"


def mistral_api_key() -> str | None:
    v = os.getenv("MISTRAL_API_KEY", "").strip()
    return v or None


def maria_vision_enabled() -> bool:
    raw = os.getenv("MARIA_VISION_ENABLED", "1").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    return bool(mistral_api_key())


def maria_vision_model() -> str:
    return os.getenv("MARIA_VISION_MODEL", "pixtral-12b-2409").strip() or "pixtral-12b-2409"


def maria_property_ingest_enabled() -> bool:
    raw = os.getenv("MARIA_PROPERTY_INGEST_ENABLED", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")

