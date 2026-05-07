"""Corridas internas (sem WhatsApp) — pré-avaliação do rascunho (visão ± Serp) + gravar linha."""

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

_INTERNAL_TURN_WITH_SERP = """[Instrução interna — nada disto será enviado ao WhatsApp]
És a Mari numa tarefa de segundo plano. O estado de sessão tem o rascunho de imóvel (maria_rascunho_imovel_id, resumo da última foto, validação). Se existir maria_ultimo_turno_cliente_whatsapp, usa-o como contexto do cliente.

1) Usa search_google no máximo 2 vezes, com queries curtas e realistas (cidade, bairro, tipologia) à luz de maria_ultima_imagem_resumo e do turno do cliente; se faltar localização, termos genéricos conservadores para o mercado residencial no Brasil, sem inventar morada.
2) Chama gravar_avaliacao_imovel_rascunho com pre_classificacao_resumo (só o que o estado sustenta) e comparacao_mercado_resumo (só o que a pesquisa sustentar; vazio se não ajudar).
Não inventes preços. Resposta final: apenas `ok` (uma linha)."""

_INTERNAL_TURN_NO_SERP = """[Instrução interna — nada disto será enviado ao WhatsApp]
És a Mari numa tarefa de segundo plano. **Não** há ferramenta de pesquisa web neste ambiente.

1) Não tentes chamar search_google. comparacao_mercado_resumo deve ser **string vazia**, salvo se maria_ultimo_turno_cliente_whatsapp ou o resumo da foto mencionarem mercado/preços de forma explícita — nesse caso uma **frase** conservadora, sem inventar números.
2) Chama **gravar_avaliacao_imovel_rascunho** com pre_classificacao_resumo: síntese do imóvel a partir de maria_ultima_imagem_resumo, validação e maria_ultimo_turno_cliente_whatsapp (só factos sustentados).
Resposta final: apenas `ok` (uma linha)."""


def schedule_silent_mari_imovel_market_enrichment(
    *,
    agent: Agent,
    user_id: str,
    session_id: str | int,
    session_state: dict[str, Any],
    last_user_turn: str | None = None,
) -> None:
    log = get_maria_logger()
    if not maria_imovel_auto_enrich_enabled():
        log.debug("[dim]Auto-enrich imóvel[/] desligado (MARIA_IMOVEL_AUTO_ENRICH_ENABLED ou sem CRM)")
        return
    if not crm_configured():
        log.debug("[dim]Auto-enrich imóvel[/] skip — CRM não configurado")
        return

    iid = str(session_state.get("maria_rascunho_imovel_id") or "").strip()
    if not iid:
        log.info(
            "[cyan]Auto-enrich imóvel[/] skip — sem maria_rascunho_imovel_id (envia foto de imóvel para criar rascunho)"
        )
        return
    if session_state.get("maria_ultima_imagem_valida_imovel") is not True:
        log.info(
            "[cyan]Auto-enrich imóvel[/] skip — última imagem não válida ou sem foto (valid=%r)",
            session_state.get("maria_ultima_imagem_valida_imovel"),
        )
        return

    cooldown = maria_imovel_auto_enrich_cooldown_sec()
    now = time.monotonic()
    with _cooldown_lock:
        prev = _last_enrich_at_mono.get(iid)
        if prev is not None and (now - prev) < cooldown:
            log.info(
                "[cyan]Auto-enrich imóvel[/] skip cooldown · imovel=%s · %.0fs restantes",
                iid[:12],
                cooldown - (now - prev),
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
    st["maria_imovel_assessment_source"] = (
        "mari_serp_enrich" if serp_api_configured() else "mari_auto_enrich"
    )
    lut = (last_user_turn or "").strip()
    if lut:
        st["maria_ultimo_turno_cliente_whatsapp"] = lut[:4000]

    internal_turn = _INTERNAL_TURN_WITH_SERP if serp_api_configured() else _INTERNAL_TURN_NO_SERP

    log.info(
        "[cyan]Auto-enrich imóvel[/] agendado · imovel=%s · serp=%s",
        iid[:12],
        serp_api_configured(),
    )

    def _job() -> None:
        jlog = get_maria_logger()
        try:
            agent.run(
                internal_turn,
                user_id=user_id,
                session_id=enrich_sid,
                session_state=st,
            )
        except Exception as e:  # noqa: BLE001
            jlog.warning("[yellow]Auto-enrich imóvel[/] falha — %s", e)

    threading.Thread(
        target=_job,
        daemon=True,
        name="mari-imovel-auto-enrich",
    ).start()
