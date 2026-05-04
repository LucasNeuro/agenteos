"""
Runtime AgentOS local — Maria (HUB Obra 10+).

Variáveis de ambiente (ficheiro .env na raiz, opcional — carregado com python-dotenv):
  MISTRAL_API_KEY — obrigatória para o modelo Mistral (ver https://docs.agno.com)
  AGNO_MODEL — opcional; padrão: mistral:mistral-large-latest
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY — CRM (opcional)
  WEBHOOK_MARIA_LEADS_URL — POST do cartão lead (opcional; ex.: n8n CARTÕES_LEADS-MARIA-WENDEL)
"""

from __future__ import annotations

import os

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None  # type: ignore[misc, assignment]

if load_dotenv:
    load_dotenv()

from .maria_crm.rich_logging import setup_maria_rich_logging

setup_maria_rich_logging()

from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.os import AgentOS

from .playbook_loader import load_maria_playbook
from .maria_crm.lead_tool import registrar_lead_no_crm
from .maria_crm.message_log import post_log_maria_conversation_turn

# Pastas relativas à raiz do projeto (executar uvicorn a partir da raiz)
_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "tmp", "agentos.db")
os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)

db = SqliteDb(db_file=os.path.normpath(_DB_PATH))

# Mistral via string — parse em MistralChat; chave em MISTRAL_API_KEY
MODEL = os.getenv("AGNO_MODEL", "mistral:mistral-large-latest")

hub_agent = Agent(
    name="HUB Obra 10+ (Maria)",
    model=MODEL,
    db=db,
    instructions=load_maria_playbook(),
    tools=[registrar_lead_no_crm],
    post_hooks=[post_log_maria_conversation_turn],
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
    tracing_db=db,
)

app = agent_os.get_app()
