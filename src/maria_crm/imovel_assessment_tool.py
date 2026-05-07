"""
Grava pré-avaliação de imóvel (Mari + contexto Pixtral/sessão + opcional SerpAPI) na tabela
`maria_imovel_studio_assessments` (nome histórico; usada também para avaliações da própria Mari).
"""

from __future__ import annotations

import json
from typing import Any

from .channel_context import _session_state_from_hook_kwargs
from .config import crm_configured
from .property_ingest import _rest_insert
from .rich_logging import get_maria_logger


def gravar_avaliacao_imovel_rascunho(
    pre_classificacao_resumo: str,
    comparacao_mercado_resumo: str = "",
    detalhes_json: str = "",
    **kwargs: Any,
) -> str:
    """
    Regista no Supabase uma avaliação do **rascunho de imóvel** da conversa (`maria_rascunho_imovel_id`).

    Usa depois de sintetizar:
    - resumos das fotos (visão/Pixtral já gravados no CRM) e contexto da conversa;
    - resultados de pesquisa web (ferramenta SerpAPI), com linguagem conservadora.

    Args:
        pre_classificacao_resumo: Leitura do imóvel (tipologia aparente, estado, forças/fragilidades).
        comparacao_mercado_resumo: Notas de mercado a partir **só** de fontes encontradas na pesquisa.
        detalhes_json: Opcional — string JSON com campos extra (ex.: tags, confiança).
    """
    log = get_maria_logger()
    if not crm_configured():
        return (
            "Interno: não foi possível guardar a análise (ambiente sem base configurada). "
            "Ao cliente: não menciones detalhe técnico."
        )

    st = _session_state_from_hook_kwargs(kwargs)
    if not isinstance(st, dict):
        return "Erro: estado de sessão indisponível."
    iid = (str(st.get("maria_rascunho_imovel_id") or "")).strip()
    if not iid:
        return (
            "Interno: falta rascunho de imóvel na sessão (fotos/contexto). "
            "Ao cliente: pede o que falta no fluxo, sem «CRM»."
        )

    pre = (pre_classificacao_resumo or "").strip()
    if not pre:
        return "O campo pre_classificacao_resumo não pode estar vazio."

    extra: dict[str, Any] = {}
    dj = (detalhes_json or "").strip()
    if dj:
        try:
            parsed = json.loads(dj)
            if isinstance(parsed, dict):
                extra["detalhes"] = parsed
            else:
                extra["detalhes"] = {"valor": parsed}
        except json.JSONDecodeError:
            extra["detalhes_raw"] = dj[:8000]

    payload: dict[str, Any] = {
        "source": "mari_serp",
        "pre_classificacao": pre,
        "comparacao_mercado": (comparacao_mercado_resumo or "").strip(),
        **extra,
    }
    raw_text = json.dumps(payload, ensure_ascii=False)

    row: dict[str, Any] = {
        "imovel_id": iid,
        "trigger_midia_id": None,
        "raw_output": raw_text[:48_000],
        "payload": payload,
        "source_midia_ids": [],
        "source_image_urls": [],
        "status": "completed",
        "error": None,
        "assessment_source": "mari_serp",
    }

    try:
        ins = _rest_insert("maria_imovel_studio_assessments", row)
        aid = str(ins[0].get("id", ""))
    except Exception as e:  # noqa: BLE001
        row.pop("assessment_source", None)
        try:
            ins = _rest_insert("maria_imovel_studio_assessments", row)
            aid = str(ins[0].get("id", ""))
            log.info("[dim]Avaliação imóvel[/] gravada sem coluna assessment_source (aplica migração 008)")
        except Exception as e2:  # noqa: BLE001
            log.warning("[yellow]Avaliação imóvel[/] falha ao gravar — %s", e2)
            return f"Interno: falha ao guardar análise ({e2!s})"[:500]

    log.info("[green]Avaliação imóvel ✓[/] imovel=[cyan]%s[/] id=[cyan]%s[/]", iid[:8], aid[:8] or "?")
    return (
        "Análise guardada para a equipa rever. "
        "Ao cliente só menciona se fizer sentido, em linguagem simples — sem «CRM» nem códigos."
    )
