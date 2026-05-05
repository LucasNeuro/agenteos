"""Tools Agno: ViaCEP + gravação de endereço no rascunho `maria_imoveis`."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from .config import crm_configured, supabase_service_role_key, supabase_url
from .rich_logging import get_maria_logger
from .viacep_client import formatar_resumo_viacep_pt, normalizar_cep_digits, viacep_consultar_json


def _sb_headers() -> dict[str, str]:
    key = supabase_service_role_key()
    if not key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY em falta")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _rest_get(table: str, params: dict[str, str]) -> list[dict[str, Any]]:
    base = supabase_url().rstrip("/")
    url = f"{base}/rest/v1/{table}"
    r = httpx.get(url, headers=_sb_headers(), params=params, timeout=45.0)
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else []


def _rest_patch_imovel(imovel_id: str, patch: dict[str, Any]) -> None:
    base = supabase_url().rstrip("/")
    url = f"{base}/rest/v1/maria_imoveis?id=eq.{imovel_id}"
    r = httpx.patch(url, headers=_sb_headers(), json=patch, timeout=45.0)
    r.raise_for_status()


def consultar_cep_viacep(cep: str) -> str:
    """
    Consulta o CEP na API pública ViaCEP (https://viacep.com.br/) e devolve um resumo em português
    para confirmares com o cliente. **Não grava** no CRM — só lê.

    Usa no fim do fluxo de cadastro de imóvel, depois do cliente informar o CEP (8 dígitos).
    """
    data, err = viacep_consultar_json(cep)
    if err:
        return f"ViaCEP: {err}"
    assert data is not None
    resumo = formatar_resumo_viacep_pt(data)
    ibge = data.get("ibge") or "—"
    return (
        f"Dados do ViaCEP para confirmares com o cliente: {resumo}. "
        f"Código IBGE (município): {ibge}. "
        f"Se bater com o que o cliente disse, chama gravar_endereco_imovel_crm com os mesmos dados."
    )


def gravar_endereco_imovel_crm(
    imovel_id: str,
    cep: str,
    numero: str = "",
    complemento: str = "",
    endereco_livre_cliente: str = "",
) -> str:
    """
    Grava endereço normalizado no rascunho `maria_imoveis` (id UUID), consultando ViaCEP e guardando
    o JSON em `viacep_payload`. O corretor/imobiliária deve **confirmar** antes do cadastro final.

    - **imovel_id**: usa o valor de `session_state.maria_rascunho_imovel_id` quando existir.
    - **cep**: com ou sem hífen; só os 8 dígitos são enviados ao ViaCEP.
    - **numero** / **complemento**: o que o cliente deu (logradouro vem do ViaCEP).
    - **endereco_livre_cliente**: texto completo opcional que o cliente digitou (auditoria).
    """
    log = get_maria_logger()
    if not crm_configured():
        return "CRM não configurado (Supabase). Não foi possível gravar o endereço."

    iid = (imovel_id or "").strip()
    if not iid:
        return "imovel_id em falta. Usa o id do estado da sessão (maria_rascunho_imovel_id)."

    rows = _rest_get("maria_imoveis", {"id": f"eq.{iid}", "select": "id", "limit": "1"})
    if not rows:
        return f"Imóvel rascunho não encontrado (id={iid[:8]}…)."

    data, err = viacep_consultar_json(cep)
    if err:
        return f"Não gravei endereço: ViaCEP — {err}"

    assert data is not None
    digits = normalizar_cep_digits(cep) or ""
    now = datetime.now(timezone.utc).isoformat()

    log_p = (data.get("logradouro") or "").strip()
    bai = (data.get("bairro") or "").strip()
    loc = (data.get("localidade") or "").strip()
    uf = (data.get("uf") or "").strip()
    ibge = str(data.get("ibge") or "").strip() or None
    cep_fmt = (data.get("cep") or "").strip() or digits

    ref_parts = [p for p in (log_p, (numero or "").strip(), bai, f"{loc} - {uf}".strip()) if p]
    endereco_ref = ", ".join(ref_parts) if ref_parts else None

    patch: dict[str, Any] = {
        "cep": cep_fmt,
        "logradouro": log_p or None,
        "numero": (numero or "").strip() or None,
        "complemento": (complemento or "").strip() or None,
        "bairro": bai or None,
        "cidade": loc or None,
        "uf": uf or None,
        "ibge": ibge,
        "endereco_referencia": endereco_ref,
        "endereco_livre_cliente": (endereco_livre_cliente or "").strip() or None,
        "viacep_payload": data,
        "viacep_consultado_em": now,
    }
    try:
        _rest_patch_imovel(iid, patch)
    except Exception as e:  # noqa: BLE001
        log.exception("[red]maria_imoveis[/] patch endereço falhou")
        return f"Erro ao gravar no CRM: {e}"[:500]

    resumo = formatar_resumo_viacep_pt(data)
    log.info("[green]Maria CRM ✓[/] endereço gravado · imovel=[cyan]%s[/]", iid[:8])
    return (
        f"Endereço gravado no rascunho do imóvel. ViaCEP: {resumo}. "
        f"Número: {(numero or 'Não informado').strip()}. "
        "Indica ao cliente que o corretor ou a imobiliária vai confirmar o cadastro final."
    )
