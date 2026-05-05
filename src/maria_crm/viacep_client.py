"""Cliente HTTP para o webservice público ViaCEP (consulta de CEP)."""

from __future__ import annotations

import re
from typing import Any

import httpx

_VIACEP_URL = "https://viacep.com.br/ws/{cep}/json/"
_HEADERS = {"User-Agent": "Maria-CRM-Obra10Plus/1.0 (+https://viacep.com.br/)"}


def normalizar_cep_digits(cep: str) -> str | None:
    d = re.sub(r"\D", "", (cep or "").strip())
    if len(d) != 8:
        return None
    return d


def viacep_consultar_json(cep_digitos: str) -> tuple[dict[str, Any] | None, str | None]:
    """
    GET ViaCEP JSON. Retorna (payload, erro_curto).
    Documentação: https://viacep.com.br/
    """
    cep = normalizar_cep_digits(cep_digitos)
    if not cep:
        return None, "CEP inválido: informe 8 dígitos."
    try:
        r = httpx.get(_VIACEP_URL.format(cep=cep), headers=_HEADERS, timeout=15.0)
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, dict):
            return None, "Resposta ViaCEP inválida."
        if data.get("erro") is True:
            return None, "CEP não encontrado na base ViaCEP."
        return data, None
    except httpx.HTTPStatusError as e:
        if e.response is not None and e.response.status_code == 400:
            return None, "Formato de CEP inválido para ViaCEP."
        return None, f"Erro HTTP ViaCEP: {e.response.status_code if e.response else '?'}"
    except Exception as e:  # noqa: BLE001
        return None, str(e)[:300]


def formatar_resumo_viacep_pt(data: dict[str, Any]) -> str:
    log = (data.get("logradouro") or "").strip()
    bai = (data.get("bairro") or "").strip()
    loc = (data.get("localidade") or "").strip()
    uf = (data.get("uf") or "").strip()
    cep_f = (data.get("cep") or "").strip()
    partes = [p for p in (log, bai, f"{loc}/{uf}".strip("/"), f"CEP {cep_f}") if p]
    return " · ".join(partes) if partes else str(data)
