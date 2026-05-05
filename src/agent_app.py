"""
Runtime AgentOS local — Mari / HUB Obra 10+.

Variáveis de ambiente (ficheiro .env na raiz, opcional — carregado com python-dotenv):
  MISTRAL_API_KEY — obrigatória para o modelo Mistral (ver https://docs.agno.com)
  AGNO_MODEL — opcional; padrão: mistral:mistral-large-latest
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY — CRM (opcional)
  WEBHOOK_MARIA_LEADS_URL — POST do cartão lead (opcional; ex.: n8n CARTÕES_LEADS-MARIA-WENDEL)
  MEM0_API_KEY — Mem0 na nuvem (ligado automaticamente se definido; MARIA_USE_MEM0=0 para desligar)
  UAZAPI_TOKEN, UAZAPI_BASE_URL — WhatsApp via UAZAPI (envio); webhook interno POST /webhooks/uazapi
  UAZAPI_WEBHOOK_SECRET — opcional; header X-Maria-Webhook-Secret no webhook
  MARIA_MEM0_APPEND_INFER — opcional; `1` para inferência Mem0 no arquivo de turnos (padrão: desligado = mais visível no dashboard)
  MARIA_AUTO_STUB_WEBHOOK — se `1`, envia também o lead mínimo automático (stub) ao webhook (opcional)
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
from .maria_crm.channel_context import maria_pre_hook_canal_contacto
from .maria_crm.config import mem0_api_key, mem0_configured, use_mem0_integration
from .maria_crm.lead_stub_hook import post_ensure_maria_contact_stub_lead
from .maria_crm.lead_tool import registrar_lead_no_crm
from .maria_crm.message_log import post_log_maria_conversation_turn

# Pastas relativas à raiz do projeto (executar uvicorn a partir da raiz)
_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "tmp", "agentos.db")
os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)

db = SqliteDb(db_file=os.path.normpath(_DB_PATH))

# Mistral via string — parse em MistralChat; chave em MISTRAL_API_KEY
MODEL = os.getenv("AGNO_MODEL", "mistral:mistral-large-latest")

_ag_tools = [registrar_lead_no_crm]
_ag_pre_hooks: list = [maria_pre_hook_canal_contacto]
_ag_post_hooks = [
    post_log_maria_conversation_turn,
    post_ensure_maria_contact_stub_lead,
]

if use_mem0_integration():
    from .maria_crm.mem0_maria import MariaMem0Tools, maria_mem0_post_append_turn, maria_mem0_pre_hook

    _ag_tools.append(
        MariaMem0Tools(
            api_key=mem0_api_key(),
            enable_delete_all_memories=False,
        )
    )
    _ag_pre_hooks.append(maria_mem0_pre_hook)
    _ag_post_hooks = [
        maria_mem0_post_append_turn,
        post_log_maria_conversation_turn,
        post_ensure_maria_contact_stub_lead,
    ]
elif mem0_configured():
    get_maria_logger().warning(
        "[yellow]Mem0[/]: [cyan]MEM0_API_KEY[/] definida mas integração desligada "
        "([dim]MARIA_USE_MEM0=0[/]). Não há add/search de memórias — altera para [bold]1[/] ou remove a variável."
    )

# Memórias Agno: só Mistral — memória **agentica** (`update_user_memory` na conversa),
# em vez do extrator em background (mesmo modelo, tool-calling mais fiável no passo principal).
hub_agent = Agent(
    name="HUB Obra 10+ (Mari)",
    model=MODEL,
    db=db,
    instructions=load_maria_playbook(),
    tools=_ag_tools,
    pre_hooks=_ag_pre_hooks or None,
    post_hooks=_ag_post_hooks,
    enable_user_memories=False,
    enable_agentic_memory=True,
    add_memories_to_context=True,
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
    tracing=True,
)

app = agent_os.get_app()

from .maria_crm.uazapi_webhook import build_uazapi_router  # noqa: E402
from .maria_crm.historico_report import build_historico_router  # noqa: E402

app.include_router(build_uazapi_router(hub_agent))
app.include_router(build_historico_router())
