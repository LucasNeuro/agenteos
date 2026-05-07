"""Corridas internas (sem WhatsApp) — pesquisa mercado + gravar pré-avaliação do rascunho de imóvel."""

from __future__ import annotations

import copy
import threading
import time
from typing import Any

from agno.agent import Agent

from .config import (
    crm_configured,
    maria_imovel_auto_enrich_cooldown_sec,
    maria_imovel_auto_enrich_enabled,
    serp_api_configured,
)
from .rich_logging import get_maria_logger

_ENRICH_SESSION_MARK = "::__imovel_auto_enrich"
_last_enrich_at_mono: dict[str, float] = {}
_cooldown_lock = threading.Lock()

_INTERNAL_TURN = """[Instrução interna — nada disto será enviado ao WhatsApp]
És a Mari numa tarefa de segundo plano. O estado de sessão tem o rascunho de imóvel (maria_rascunho_imovel_id, resumo da última foto, validação). Se existir maria_ultimo_turno_cliente_whatsapp, usa-o como contexto do cliente (última mensagem deste contacto).

1) Usa search_google no máximo 2 vezes, com queries curtas e realistas (cidade, bairro, tipologia, palavras-chave de imóvel) à luz de maria_ultima_imagem_resumo e de maria_ultimo_turno_cliente_whatsapp; se faltar localização clara, usa termos genéricos conservadores para o mercado residencial brasileiro, sem inventar endereço.
2) Chama gravar_avaliacao_imovel_rascunho com pre_classificacao_resumo (imóvel, só o que o estado de sessão sustenta) e comparacao_mercado_resumo (só o que os resultados de pesquisa sustentam; string vazia se a pesquisa não ajudar).
Não inventes preços nem anúncios. Resposta final do modelo: apenas `ok` (minúsculas, uma linha)."""


def schedule_silent_mari_imovel_market_enrichment(
    *,
    agent: Agent,
    user_id: str,
    session_id: str | int,
    session_state: dict[str, Any],
    last_user_turn: str | None = None,
) -> None:
    if not maria_imovel_auto_enrich_enabled():
        return
    if not crm_configured() or not serp_api_configured():
        return

    iid = str(session_state.get("maria_rascunho_imovel_id") or "").strip()
    if not iid:
        return
    if session_state.get("maria_ultima_imagem_valida_imovel") is not True:
        return

    cooldown = maria_imovel_auto_enrich_cooldown_sec()
    now = time.monotonic()
    with _cooldown_lock:
        prev = _last_enrich_at_mono.get(iid)
        if prev is not None and (now - prev) < cooldown:
            get_maria_logger().debug(
                "[dim]Auto-enrich imóvel[/] em cooldown · imovel=%s",
                iid[:12],
            )
            return
        _last_enrich_at_mono[iid] = now

    base_sid = str(session_id).strip()
    enrich_sid = (
        base_sid
        if _ENRICH_SESSION_MARK in base_sid
        else f"{base_sid}{_ENRICH_SESSION_MARK}"
    )

    st = copy.copy(session_state)
    st["maria_internal_background_run"] = True
    lut = (last_user_turn or "").strip()
    if lut:
        st["maria_ultimo_turno_cliente_whatsapp"] = lut[:4000]

    def _job() -> None:
        log = get_maria_logger()
        try:
            agent.run(
                _INTERNAL_TURN,
                user_id=user_id,
                session_id=enrich_sid,
                session_state=st,
            )
        except Exception as e:  # noqa: BLE001
            log.warning("[yellow]Auto-enrich imóvel[/] falha — %s", e)

    threading.Thread(
        target=_job,
        daemon=True,
        name="mari-imovel-auto-enrich",
    ).start()
