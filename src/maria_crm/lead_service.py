from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from zoneinfo import ZoneInfo

import httpx

from .config import (
    auto_stub_webhook_enabled,
    crm_configured,
    supabase_service_role_key,
    supabase_url,
    webhook_maria_leads_url,
)
from .rich_logging import get_maria_logger

LeadKind = Literal[
    "cliente_imobiliario",
    "cliente_projetos",
    "prestador_servico",
    "imobiliaria_corretor",
]
Potencial = Literal["ALTO", "MEDIO", "BAIXO"]

_ALLOWED_KINDS = frozenset(
    {"cliente_imobiliario", "cliente_projetos", "prestador_servico", "imobiliaria_corretor"}
)
_ALLOWED_POT = frozenset({"ALTO", "MEDIO", "BAIXO"})


def _now_brasilia_iso() -> str:
    tz = ZoneInfo("America/Sao_Paulo")
    return datetime.now(tz).replace(microsecond=0).isoformat()


def _supabase_headers() -> dict[str, str]:
    key = supabase_service_role_key()
    if not key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY em falta")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _rest_insert(table: str, row: dict[str, Any]) -> list[dict[str, Any]]:
    base = supabase_url().rstrip("/")
    url = f"{base}/rest/v1/{table}"
    r = httpx.post(url, headers=_supabase_headers(), json=row, timeout=30.0)
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else [data]


def _rest_get(
    table: str,
    *,
    params: dict[str, str],
) -> list[dict[str, Any]]:
    base = supabase_url().rstrip("/")
    url = f"{base}/rest/v1/{table}"
    r = httpx.get(url, headers=_supabase_headers(), params=params, timeout=30.0)
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else []


def _session_uuid_from_external_id(external_session_id: str | None) -> str | None:
    ext = (external_session_id or "").strip()
    if not ext:
        return None
    rows = _rest_get(
        "maria_sessions",
        params={
            "external_session_id": f"eq.{ext}",
            "select": "id",
            "limit": "1",
        },
    )
    if not rows:
        return None
    sid = rows[0].get("id")
    return str(sid).strip() if sid is not None and str(sid).strip() else None


def _build_card_payload(
    *,
    nome: str,
    telefone: str,
    email: str,
    servico_solicitado: str,
    dados_imovel: dict[str, Any],
    resumo_necessidade: str,
    potencial: str,
    potencial_justificativa: str,
    caracteristicas_adicionais: str,
) -> dict[str, Any]:
    return {
        "nome": nome,
        "telefone": telefone,
        "email": email,
        "servico_solicitado": servico_solicitado,
        "dados_imovel": dados_imovel,
        "resumo_necessidade": resumo_necessidade,
        "analise_potencial": {
            "potencial": potencial,
            "justificativa": potencial_justificativa,
        },
        "caracteristicas_adicionais": caracteristicas_adicionais,
        "timestamp": _now_brasilia_iso(),
    }


def _insert_lead_row_best_effort(lead_row: dict[str, Any], *, log: Any) -> list[dict[str, Any]]:
    """
    Compatibilidade com instalações antigas sem migração 002 (source_external_session_id).
    """
    try:
        return _rest_insert("maria_leads", lead_row)
    except Exception as e:  # noqa: BLE001
        msg = str(e).lower()
        if "source_external_session_id" not in msg:
            raise
        fallback = dict(lead_row)
        fallback.pop("source_external_session_id", None)
        log.warning(
            "[yellow]registrar_lead[/] coluna source_external_session_id ausente (migração 002). "
            "Lead será inserido sem essa coluna."
        )
        return _rest_insert("maria_leads", fallback)


def persist_lead_and_webhook(
    lead_kind: LeadKind,
    nome: str,
    telefone: str,
    *,
    email: str = "Não informado",
    servico_solicitado: str = "",
    resumo_necessidade: str = "",
    potencial: Potencial = "MEDIO",
    potencial_justificativa: str = "",
    caracteristicas_adicionais: str = "",
    tipo_imovel: str = "",
    tamanho_imovel: str = "",
    bairro_regiao: str = "",
    prazo: str = "",
    # Detalhes opcionais por playbook (passar o que fizer sentido)
    modo_imobiliario: str = "",
    intencao_imobiliario: str = "",
    tipo_servico_projeto: str = "",
    cidade_bairro_projeto: str = "",
    segmento_prestador: str = "",
    captacao_prestador: str = "",
    empresa_b2b: str = "",
    intencao_b2b: str = "",
    email_corporativo_b2b: str = "",
    source_external_session_id: str | None = None,
) -> str:
    """
    Insere lead no Supabase (tabela principal + detalhe por tipo), envia POST ao webhook se configurado.
    Chamada pela tool do Agno quando a qualificação estiver concluída.
    """
    log = get_maria_logger()
    if not crm_configured():
        log.warning("[yellow]registrar_lead[/] — Supabase não configurado; lead não gravado")
        return (
            "Interno: Supabase não configurado (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY). "
            "Nada foi guardado. Ao cliente: pede desculpa breve e diz que pode tentar mais tarde — "
            "sem detalhe técnico."
        )

    if lead_kind not in _ALLOWED_KINDS:
        log.warning("[yellow]registrar_lead[/] — lead_kind inválido: [red]%s[/]", lead_kind)
        return (
            f"lead_kind inválido: {lead_kind!r}. "
            "Use: cliente_imobiliario, cliente_projetos, prestador_servico ou imobiliaria_corretor."
        )
    if potencial not in _ALLOWED_POT:
        log.warning("[yellow]registrar_lead[/] — potencial inválido: [red]%s[/]", potencial)
        return f"potencial inválido: {potencial!r}. Use ALTO, MEDIO ou BAIXO."

    dados_imovel: dict[str, str] = {
        "tipo": tipo_imovel or "Não informado",
        "tamanho": tamanho_imovel or "Não informado",
        "bairro_regiao": bairro_regiao or "Não informado",
        "prazo": prazo or "Não informado",
    }

    card = _build_card_payload(
        nome=nome.strip(),
        telefone=telefone.strip(),
        email=email.strip() or "Não informado",
        servico_solicitado=servico_solicitado.strip() or lead_kind,
        dados_imovel=dados_imovel,
        resumo_necessidade=resumo_necessidade.strip(),
        potencial=potencial,
        potencial_justificativa=potencial_justificativa.strip(),
        caracteristicas_adicionais=caracteristicas_adicionais.strip(),
    )
    source_ext = (source_external_session_id or "").strip() or None
    session_uuid = _session_uuid_from_external_id(source_ext) if source_ext else None

    lead_row = {
        "lead_kind": lead_kind,
        "nome": nome.strip() or None,
        "telefone": telefone.strip() or None,
        "email": email.strip() or "Não informado",
        "servico_solicitado": servico_solicitado.strip() or None,
        "dados_imovel": dados_imovel,
        "resumo_necessidade": resumo_necessidade.strip() or None,
        "potencial": potencial,
        "potencial_justificativa": potencial_justificativa.strip() or None,
        "caracteristicas_adicionais": caracteristicas_adicionais.strip() or None,
        "webhook_payload": card,
        "session_id": session_uuid,
        "source_external_session_id": source_ext,
    }

    inserted = _insert_lead_row_best_effort(lead_row, log=log)
    if not inserted:
        log.error("[red]registrar_lead[/] — Supabase não devolveu id do lead")
        return (
            "Interno: erro ao guardar na base. Ao cliente: mensagem breve de desculpa, "
            "oferece tentar de novo — sem «lead» nem «Supabase»."
        )
    lead_id = inserted[0]["id"]

    detail: dict[str, Any] = {"lead_id": lead_id}
    if lead_kind == "cliente_imobiliario":
        detail.update(
            {
                "modo": modo_imobiliario or None,
                "intencao": intencao_imobiliario or None,
                "tipo_imovel_resumo": tipo_imovel or None,
                "bairro_regiao": bairro_regiao or None,
                "prazo_necessidade": prazo or None,
            }
        )
        _rest_insert("maria_lead_cliente_imobiliario", detail)
    elif lead_kind == "cliente_projetos":
        detail.update(
            {
                "tipo_servico": tipo_servico_projeto or servico_solicitado or None,
                "tipo_imovel": tipo_imovel or None,
                "faixa_m2": tamanho_imovel or None,
                "cidade_bairro": cidade_bairro_projeto or bairro_regiao or None,
                "prazo_inicio": prazo or None,
            }
        )
        _rest_insert("maria_lead_cliente_projetos", detail)
    elif lead_kind == "prestador_servico":
        detail.update(
            {
                "segmento": segmento_prestador or servico_solicitado or None,
                "captacao": captacao_prestador or None,
            }
        )
        _rest_insert("maria_lead_prestador", detail)
    elif lead_kind == "imobiliaria_corretor":
        detail.update(
            {
                "empresa_ou_carteira": empresa_b2b or None,
                "intencao_b2b": intencao_b2b or servico_solicitado or None,
                "email_corporativo": email_corporativo_b2b or email or None,
            }
        )
        _rest_insert("maria_lead_imobiliaria_b2b", detail)

    webhook_url = webhook_maria_leads_url()
    webhook_status: int | None = None
    webhook_err: str | None = None
    if webhook_url:
        try:
            wr = httpx.post(
                webhook_url,
                headers={"Content-Type": "application/json"},
                json=card,
                timeout=45.0,
            )
            webhook_status = wr.status_code
            wr.raise_for_status()
            _patch_lead_webhook_status(lead_id, webhook_status, None, sent_ok=True)
            log.info(
                "[bold green]Maria CRM ✓ lead[/] id=[cyan]%s[/] kind=[magenta]%s[/] · webhook HTTP [green]%s[/]",
                lead_id,
                lead_kind,
                webhook_status,
            )
        except Exception as e:  # noqa: BLE001
            webhook_err = str(e)[:500]
            _patch_lead_webhook_status(lead_id, webhook_status, webhook_err, sent_ok=False)
            log.exception(
                "[bold red]Maria CRM ✗ lead[/] id=[cyan]%s[/] webhook falhou",
                lead_id,
            )
            return (
                f"Interno: dados guardados na base (ref. {str(lead_id)[:8]}…), mas a notificação à equipa falhou "
                f"({webhook_err[:200]}). Corrigir WEBHOOK_MARIA_LEADS_URL se necessário. "
                "Ao cliente: mensagem calma — informações recebidas, equipa em contacto em breve — "
                "sem «webhook», «Supabase» nem códigos de erro."
            )
    else:
        log.info(
            "[bold green]Maria CRM ✓ lead[/] id=[cyan]%s[/] kind=[magenta]%s[/] · [dim]sem webhook (.env)[/]",
            lead_id,
            lead_kind,
        )

    return (
        "Dados do cliente guardados — a equipa pode dar seguimento ao pedido. "
        "Ao responder **ao cliente**: usa português simples e acolhedor; **não** repitas esta mensagem, "
        "**não** uses «lead», «CRM», «cadastrado no sistema», «registo técnico» nem IDs. "
        "Preferir: que já recebeste as informações, que estão com a equipa, que um corretor especialista "
        "entra em contacto em breve — conforme o fluxo."
    )


def attach_lead_to_session_by_external_id(*, lead_id: str, external_session_id: str) -> bool:
    """
    Mantém consistência `maria_leads.session_id` <-> `maria_sessions.external_session_id`.
    """
    if not crm_configured():
        return False
    lead = (lead_id or "").strip()
    ext = (external_session_id or "").strip()
    if not lead or not ext:
        return False
    sid = _session_uuid_from_external_id(ext)
    if not sid:
        return False
    base = supabase_url().rstrip("/")
    url = f"{base}/rest/v1/maria_leads?id=eq.{lead}"
    patch = {
        "session_id": sid,
        "source_external_session_id": ext,
    }
    r = httpx.patch(url, headers=_supabase_headers(), json=patch, timeout=30.0)
    r.raise_for_status()
    return True


def _patch_lead_webhook_status(
    lead_id: str,
    status: int | None,
    error: str | None,
    *,
    sent_ok: bool,
) -> None:
    base = supabase_url().rstrip("/")
    url = f"{base}/rest/v1/maria_leads?id=eq.{lead_id}"
    patch: dict[str, Any] = {
        "webhook_http_status": status,
        "webhook_error": error,
    }
    if sent_ok:
        patch["webhook_sent_at"] = datetime.now(timezone.utc).isoformat()
    r = httpx.patch(url, headers=_supabase_headers(), json=patch, timeout=30.0)
    r.raise_for_status()


_AUTO_STUB_TAG = "[AUTO_STUB]"


def ensure_auto_contact_stub_lead(
    *,
    source_external_session_id: str | None,
    telefone: str | None,
    user_id: str | None,
) -> None:
    """
    Garante **um** lead mínimo por sessão AgentOS / contacto quando a Mari responde mas a tool
    `registrar_lead_no_crm` **não** foi chamada — assim o contacto fica no CRM mesmo se o utilizador
    nunca mais responder.

    Deduplica por `source_external_session_id` (coluna da migração `002_maria_lead_source_session.sql`)
    ou, em último caso, por prefixo `uid:` + user_id.
    """
    log = get_maria_logger()
    if not crm_configured():
        return

    dedupe_key = (source_external_session_id or "").strip()
    if not dedupe_key and user_id:
        dedupe_key = f"uid:{user_id.strip()}"
    if not dedupe_key:
        log.debug("[dim]Maria CRM stub[/] sem session/user — ignorado")
        return

    try:
        existing = _rest_get(
            "maria_leads",
            params={
                "source_external_session_id": f"eq.{dedupe_key}",
                "select": "id",
                "limit": "1",
            },
        )
    except Exception as e:  # noqa: BLE001
        log.warning(
            "[yellow]Maria CRM stub[/] não foi possível consultar leads — a migração 002 está aplicada? %s",
            e,
        )
        return

    if existing:
        return

    tel = (telefone or "").strip()
    if not tel:
        tel = "Não informado"
    session_uuid = _session_uuid_from_external_id(dedupe_key)

    resumo = (
        "Contato registrado automaticamente após primeira (ou seguinte) resposta da Mari. "
        "Qualificação incompleta ou interlocutor pode não ter respondido de novo — fazer follow-up humano se necessário."
    )
    justificativa = (
        "Registo mínimo obrigatório por sessão; sem conclusão de fluxo nem chamada à tool de lead pelo modelo."
    )
    card = _build_card_payload(
        nome="Não informado",
        telefone=tel,
        email="Não informado",
        servico_solicitado="Mercado Imobiliário — registro automático de contato (stub)",
        dados_imovel={
            "tipo": "Não informado",
            "tamanho": "Não informado",
            "bairro_regiao": "Não informado",
            "prazo": "Não informado",
        },
        resumo_necessidade=resumo,
        potencial="BAIXO",
        potencial_justificativa=justificativa,
        caracteristicas_adicionais=f"{_AUTO_STUB_TAG} Sessão {dedupe_key}. user_id={user_id or '—'}",
    )
    card["mari_auto_contact_stub"] = True
    card["source_external_session_id"] = dedupe_key

    car_extra = f"{_AUTO_STUB_TAG} external_session={dedupe_key}" + (f" user_id={user_id}" if user_id else "")

    lead_row: dict[str, Any] = {
        "lead_kind": "cliente_imobiliario",
        "nome": "Não informado",
        "telefone": tel if tel != "Não informado" else None,
        "email": "Não informado",
        "servico_solicitado": "Mercado Imobiliário — stub contato",
        "dados_imovel": {
            "tipo": "Não informado",
            "tamanho": "Não informado",
            "bairro_regiao": "Não informado",
            "prazo": "Não informado",
        },
        "resumo_necessidade": resumo,
        "potencial": "BAIXO",
        "potencial_justificativa": justificativa,
        "caracteristicas_adicionais": car_extra,
        "webhook_payload": card,
        "session_id": session_uuid,
        "source_external_session_id": dedupe_key,
    }

    try:
        inserted = _insert_lead_row_best_effort(lead_row, log=log)
    except Exception as e:  # noqa: BLE001
        log.warning(
            "[yellow]Maria CRM stub[/] falha ao inserir — aplica `002_maria_lead_source_session.sql` no Supabase? %s",
            e,
        )
        return

    lead_id = inserted[0]["id"]
    detail = {
        "lead_id": lead_id,
        "modo": None,
        "intencao": "contato_auto_stub",
        "tipo_imovel_resumo": None,
        "bairro_regiao": None,
        "prazo_necessidade": None,
    }
    try:
        _rest_insert("maria_lead_cliente_imobiliario", detail)
    except Exception as e:  # noqa: BLE001
        log.warning("[yellow]Maria CRM stub[/] lead criado mas detalhe falhou — %s", e)

    send_wh = webhook_maria_leads_url() and auto_stub_webhook_enabled()
    if send_wh:
        try:
            wr = httpx.post(
                webhook_maria_leads_url() or "",
                headers={"Content-Type": "application/json"},
                json=card,
                timeout=45.0,
            )
            wr.raise_for_status()
            _patch_lead_webhook_status(lead_id, wr.status_code, None, sent_ok=True)
        except Exception as e:  # noqa: BLE001
            _patch_lead_webhook_status(lead_id, None, str(e)[:500], sent_ok=False)
            log.warning("[yellow]Maria CRM stub[/] webhook opcional falhou — %s", e)
    else:
        log.info(
            "[bold cyan]Maria CRM · stub[/] lead id=[cyan]%s[/] sessão=[dim]%s[/] — "
            "webhook só com MARIA_AUTO_STUB_WEBHOOK=1",
            lead_id,
            dedupe_key[:48],
        )
