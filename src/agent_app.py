"""
Runtime AgentOS local — Mari / HUB Obra 10+.

Variáveis de ambiente (ficheiro .env na raiz, opcional — carregado com python-dotenv):
  MISTRAL_API_KEY — obrigatória para o modelo Mistral (ver https://docs.agno.com)
  AGNO_MODEL — opcional; padrão: mistral:mistral-large-latest
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY — CRM (opcional)
  MARIA_DATABASE_URL — Postgres directo (opcional; RAG com MARIA_KNOWLEDGE_ENABLED=1 — ver .env.example)
  MARIA_KNOWLEDGE_ENABLED — 1 para Agentic RAG (Knowledge + pgvector no Supabase; migração 005)
  WEBHOOK_MARIA_LEADS_URL — POST do cartão lead (opcional; ex.: n8n CARTÕES_LEADS-MARIA-WENDEL)
  MEM0_API_KEY — Mem0 na nuvem (ligado automaticamente se definido; MARIA_USE_MEM0=0 para desligar)
  MARIA_AGNO_ALWAYS_USER_MEMORIES — extração automática de memórias Agno (SQLite); ver .env.example
  MARIA_AGNO_SESSION_SUMMARIES — resumo de sessão no contexto (padrão ligado); 0 para desligar
  UAZAPI_TOKEN, UAZAPI_BASE_URL — WhatsApp via UAZAPI (envio); webhook interno POST /webhooks/uazapi
  UAZAPI_WEBHOOK_SECRET — opcional; header X-Maria-Webhook-Secret no webhook
  AGENTOS_TRACING — 1 para ligar tracing OpenTelemetry do Agno (padrão: desligado; requer pacotes extras)
  SERP_API_KEY — SerpAPI para pesquisa web (Google via Agno SerpApiTools; opcional — ver requirements)
"""

from __future__ import annotations

import os

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None  # type: ignore[misc, assignment]

if load_dotenv:
    load_dotenv()

from .maria_crm.rich_logging import get_maria_logger, setup_maria_rich_logging

setup_maria_rich_logging()

from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.os import AgentOS

from .playbook_loader import load_maria_playbook
from .maria_crm.knowledge_maria import try_build_maria_knowledge_optional
from .maria_crm.channel_context import maria_pre_hook_canal_contacto
from .maria_crm import config as maria_config
from .maria_crm.imovel_endereco_tool import consultar_cep_viacep, gravar_endereco_imovel_crm
from .maria_crm.lead_property_link_hook import post_link_maria_imoveis_to_lead
from .maria_crm.lead_stub_hook import post_ensure_maria_contact_stub_lead
from .maria_crm.lead_tool import registrar_lead_no_crm
from .maria_crm.message_log import post_log_maria_conversation_turn
from .maria_crm.agno_memory_maria import build_maria_memory_manager

# Pastas relativas à raiz do projeto (executar uvicorn a partir da raiz)
_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "tmp", "agentos.db")
os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)

db = SqliteDb(db_file=os.path.normpath(_DB_PATH))

# Mistral via string — parse em MistralChat; chave em MISTRAL_API_KEY
MODEL = os.getenv("AGNO_MODEL", "mistral:mistral-large-latest")

_ag_tools = [registrar_lead_no_crm, consultar_cep_viacep, gravar_endereco_imovel_crm]

if maria_config.crm_configured():
    from .maria_crm.imovel_assessment_tool import gravar_avaliacao_imovel_rascunho

    _ag_tools.append(gravar_avaliacao_imovel_rascunho)

if maria_config.serp_api_configured():
    try:
        from agno.tools.serpapi import SerpApiTools

        _ag_tools.append(
            SerpApiTools(
                api_key=maria_config.serp_api_key(),
                enable_search_google=True,
                enable_search_youtube=False,
            )
        )
    except ImportError:
        get_maria_logger().warning(
            "[yellow]SerpAPI[/]: define [cyan]SERP_API_KEY[/] mas falta o pacote — "
            "`pip install google-search-results` (ver doc Agno SerpApiTools)."
        )

_ag_pre_hooks: list = [maria_pre_hook_canal_contacto]
_ag_post_hooks = [
    post_log_maria_conversation_turn,
    post_link_maria_imoveis_to_lead,
    post_ensure_maria_contact_stub_lead,
]

if maria_config.use_mem0_integration():
    from .maria_crm.mem0_maria import MariaMem0Tools, maria_mem0_post_append_turn, maria_mem0_pre_hook

    _ag_tools.append(
        MariaMem0Tools(
            api_key=maria_config.mem0_api_key(),
            enable_delete_all_memories=False,
        )
    )
    _ag_pre_hooks.append(maria_mem0_pre_hook)
    _ag_post_hooks = [
        maria_mem0_post_append_turn,
        post_log_maria_conversation_turn,
        post_link_maria_imoveis_to_lead,
        post_ensure_maria_contact_stub_lead,
    ]
elif maria_config.mem0_configured():
    get_maria_logger().warning(
        "[yellow]Mem0[/]: [cyan]MEM0_API_KEY[/] definida mas integração desligada "
        "([dim]MARIA_USE_MEM0=0[/]). Não há add/search de memórias — altera para [bold]1[/] ou remove a variável."
    )

# Memórias Agno (SQLite): memória **agentica** (tool ``update_user_memory``) + extração **Always**
# opcional (``MARIA_AGNO_ALWAYS_USER_MEMORIES`` / padrão sem Mem0) e resumos de sessão (``MARIA_AGNO_SESSION_SUMMARIES``).
_maria_knowledge = try_build_maria_knowledge_optional()

hub_agent = Agent(
    name="HUB Obra 10+ (Mari)",
    model=MODEL,
    db=db,
    memory_manager=build_maria_memory_manager(),
    instructions=load_maria_playbook(),
    tools=_ag_tools,
    pre_hooks=_ag_pre_hooks or None,
    post_hooks=_ag_post_hooks,
    knowledge=_maria_knowledge,
    search_knowledge=bool(_maria_knowledge),
    enable_user_memories=maria_config.maria_agno_always_user_memories_enabled(),
    enable_agentic_memory=True,
    add_memories_to_context=True,
    enable_session_summaries=maria_config.maria_agno_session_summaries_enabled(),
    add_session_state_to_context=True,
    markdown=True,
    add_datetime_to_context=True,
    timezone_identifier="America/Sao_Paulo",
    add_history_to_context=True,
    num_history_runs=14,
)

agent_os = AgentOS(
    name="hub-obra-agentos",
    agents=[hub_agent],
    tracing=maria_config.agent_os_tracing_enabled(),
)

app = agent_os.get_app()

from .maria_crm.uazapi_webhook import build_uazapi_router  # noqa: E402
from .maria_crm.historico_report import build_historico_router  # noqa: E402
from .maria_crm.rag_ingest_webhook import build_maria_rag_ingest_router  # noqa: E402

from .maria_crm.rag_admin_ui import build_rag_admin_router  # noqa: E402
from .maria_crm.crm_ops_report import build_crm_ops_router  # noqa: E402

app.include_router(build_uazapi_router(hub_agent))
app.include_router(build_historico_router())
_rag_ingest = build_maria_rag_ingest_router()
if _rag_ingest is not None:
    app.include_router(_rag_ingest)
_rag_admin = build_rag_admin_router()
if _rag_admin is not None:
    app.include_router(_rag_admin)
_crm_ops = build_crm_ops_router()
if _crm_ops is not None:
    app.include_router(_crm_ops)
