"""Memória persistente Agno (SQLite via ``SqliteDb``) — instruções de domínio e skips seguros."""

from __future__ import annotations

from textwrap import dedent
from typing import List, Optional

from agno.memory.manager import MemoryManager
from agno.models.message import Message
from agno.utils.log import log_debug

# Mesmo prefixo que ``maria_imovel_auto_enrich`` (corrida interna; não extrair como memória do cliente).
_INTERNAL_USER_PREFIXES = (
    "[instrução interna",
    "[instrucao interna",
)

MARIA_MEMORY_CAPTURE_INSTRUCTIONS_PT = dedent(
    """
    Contexto: atendimento HUB Obra 10+ (Brasil), mercado imobiliário e projetos de arquitetura/reforma.

    Extrai apenas factos **explícitos** na conversa. Escreve em português claro, terceira pessoa ou neutro (ex.: "O cliente prefere…").
    Prioridade de campos quando existirem no texto:
    - Nome ou como prefere ser tratado
    - Intenção (comprar, alugar, vender, anunciar, parceria corretor, projeto arquitetura/interiores)
    - Local (cidade, bairro) e tipo de imóvel / metragem se mencionados
    - Prazo ou urgência se mencionados

    **Não** inventes preços, disponibilidade, dados de imóvel ou conteúdo de imagens.
    **Não** grave instruções técnicas, JSON, IDs internos ou ferramentas.
    Memórias curtas e úteis; funde com memórias existentes quando for o mesmo facto.
    """
).strip()


def _maria_skip_memory_from_messages(messages: Optional[List[Message]]) -> bool:
    if not messages:
        return True
    for m in messages:
        try:
            raw = m.get_content_string()
        except Exception:  # noqa: BLE001
            raw = ""
        if not isinstance(raw, str):
            continue
        head = raw.lstrip()[:32].lower()
        if any(head.startswith(p) for p in _INTERNAL_USER_PREFIXES):
            return True
    return False


class MariaMemoryManager(MemoryManager):
    """``MemoryManager`` que ignora turnos sintéticos internos (auto-enrich, etc.)."""

    def create_user_memories(
        self,
        message: Optional[str] = None,
        messages: Optional[List[Message]] = None,
        agent_id: Optional[str] = None,
        team_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> str:
        resolved = messages
        if message and not resolved:
            resolved = [Message(role="user", content=message)]
        if _maria_skip_memory_from_messages(resolved):
            log_debug("MariaMemoryManager: extract skipped (internal/synthetic user turn)")
            return "Memórias Agno: ignorado (turno interno / sintético)."
        return super().create_user_memories(
            message=message,
            messages=messages,
            agent_id=agent_id,
            team_id=team_id,
            user_id=user_id,
        )

    async def acreate_user_memories(
        self,
        message: Optional[str] = None,
        messages: Optional[List[Message]] = None,
        agent_id: Optional[str] = None,
        team_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> str:
        resolved = messages
        if message and not resolved:
            resolved = [Message(role="user", content=message)]
        if _maria_skip_memory_from_messages(resolved):
            log_debug("MariaMemoryManager: extract skipped (internal/synthetic user turn)")
            return "Memórias Agno: ignorado (turno interno / sintético)."
        return await super().acreate_user_memories(
            message=message,
            messages=messages,
            agent_id=agent_id,
            team_id=team_id,
            user_id=user_id,
        )


def build_maria_memory_manager() -> MariaMemoryManager:
    """Factory para o ``Agent`` — modelo e ``db`` são preenchidos pelo Agno em runtime."""
    return MariaMemoryManager(
        memory_capture_instructions=MARIA_MEMORY_CAPTURE_INSTRUCTIONS_PT,
        delete_memories=False,
        clear_memories=False,
        update_memories=True,
        add_memories=True,
    )
