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


def _truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes", "on")


def maria_database_url_raw() -> str | None:
    """URL Postgres directa (não confundir com SUPABASE_URL da API REST)."""
    for key in ("MARIA_DATABASE_URL", "SUPABASE_DATABASE_URL", "DATABASE_URL"):
        v = os.getenv(key, "").strip()
        if v:
            return v
    return None


def maria_postgres_url_for_agno() -> str | None:
    """
    Normaliza URL para SQLAlchemy + psycopg3 (`postgresql+psycopg://`).
    Preferir sessão directa (porta 5432) em Supabase para ORM; pooler 6543 pode dar stress em alguns drivers.
    """
    raw = maria_database_url_raw()
    if not raw:
        return None
    url = raw.strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and not url.startswith("postgresql+psycopg://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def maria_knowledge_enabled_flag() -> bool:
    return _truthy("MARIA_KNOWLEDGE_ENABLED")


def maria_knowledge_auto_enabled() -> bool:
    """RAG activo só com flag, URL Postgres e chave Mistral (embed + chat)."""
    if not maria_knowledge_enabled_flag():
        return False
    if not maria_postgres_url_for_agno():
        return False
    return bool(mistral_api_key())


def maria_rag_storage_bucket() -> str:
    return os.getenv("MARIA_RAG_STORAGE_BUCKET", "maria-rag-documents").strip() or "maria-rag-documents"


def maria_knowledge_ingest_mode() -> str:
    """`local` (pasta no repo) ou `storage` (bucket Supabase)."""
    v = os.getenv("MARIA_KNOWLEDGE_INGEST_MODE", "local").strip().lower()
    return v if v in ("local", "storage") else "local"


def maria_rag_storage_prefix() -> str:
    """Prefixo opcional dentro do bucket (ex.: `guardrails/`)."""
    raw = os.getenv("MARIA_RAG_STORAGE_PREFIX", "").strip().replace("\\", "/")
    if not raw:
        return ""
    return raw if raw.endswith("/") else f"{raw}/"


def maria_rag_admin_secret() -> str | None:
    """Se definido, activa a UI GET /admin/rag e POST /admin/rag/upload."""
    v = os.getenv("MARIA_RAG_ADMIN_SECRET", "").strip()
    return v or None


def maria_rag_admin_reindex_after_upload() -> bool:
    """Após upload na UI admin, fila reindex completa do bucket (modo storage)."""
    return _truthy("MARIA_RAG_ADMIN_REINDEX_AFTER_UPLOAD")


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


def uazapi_min_seconds_between_sends() -> float:
    """Espaço mínimo entre envios UAZ para o mesmo contacto (evita rajadas de bolhas)."""
    raw = os.getenv("MARIA_UAZAPI_MIN_SEC_BETWEEN_SENDS", "0.85").strip()
    try:
        v = float(raw)
    except ValueError:
        return 0.85
    return max(0.0, min(v, 30.0))


def uazapi_webhook_message_dedupe_ttl_sec() -> float:
    """Ignorar webhooks duplicados com o mesmo messageid durante N segundos (0 = desligado)."""
    raw = os.getenv("MARIA_UAZAPI_WEBHOOK_DEDUPE_SEC", "300").strip()
    try:
        v = float(raw)
    except ValueError:
        return 300.0
    return max(0.0, min(v, 86_400.0))


def maria_media_batch_flush_after_sec() -> float:
    """
    Depois da última foto (só mídia, sem texto), espera N segundos sem nova foto e encerra o lote
    (uma resposta da Mari). 0 = desligado; aí só há resposta quando o cliente mandar texto.
    """
    raw = os.getenv("MARIA_MEDIA_BATCH_FLUSH_SEC", "3.5").strip()
    try:
        v = float(raw)
    except ValueError:
        return 3.5
    return max(0.0, min(v, 45.0))


def maria_text_message_debounce_after_sec() -> float:
    """
    Após cada fragmento de texto (ou legenda de imagem), espera N segundos sem nova mensagem
    do mesmo chat antes de chamar o agente — agrupa «mensagens picadas» num único turno.
    0 = desligado (cada webhook responde na hora). Máx. 15 s.
    """
    raw = os.getenv("MARIA_TEXT_DEBOUNCE_SEC", "2.5").strip()
    try:
        v = float(raw)
    except ValueError:
        return 2.5
    return max(0.0, min(v, 15.0))

