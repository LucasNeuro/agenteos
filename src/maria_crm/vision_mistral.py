"""Análise de imagem com Mistral (Pixtral ou modelo multimodal configurável)."""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from typing import Any

import httpx

from .config import maria_vision_model, mistral_api_key


def mistral_describe_image_bytes(
    image_bytes: bytes,
    *,
    mime_type: str = "image/jpeg",
    prompt: str | None = None,
) -> tuple[str | None, str | None]:
    """
    Retorna (resumo em PT, erro_curto).
    Usa MISTRAL_API_KEY e MARIA_VISION_MODEL (padrão pixtral-12b-2409).
    """
    key = mistral_api_key()
    if not key:
        return None, "MISTRAL_API_KEY em falta"
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    data_url = f"data:{mime_type};base64,{b64}"
    model = maria_vision_model()
    text = prompt or (
        "Em português do Brasil, descreva em 2 a 4 frases objetivas o que esta imagem mostra "
        "no contexto de imóvel (ambientes, acabamentos aparentes, luminosidade, estado geral). "
        "Se não for um espaço interno/externo de imóvel, diga apenas o que observa. "
        "Não invente endereço, preço nem metragem."
    )
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": text},
                    {"type": "image_url", "image_url": data_url},
                ],
            }
        ],
        "max_tokens": 400,
        "temperature": 0.3,
    }
    try:
        r = httpx.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
            timeout=120.0,
        )
        r.raise_for_status()
        body = r.json()
        choices = body.get("choices")
        if isinstance(choices, list) and choices:
            msg = choices[0].get("message") or {}
            content = msg.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip(), None
            if isinstance(content, list):
                parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        t = block.get("text")
                        if isinstance(t, str):
                            parts.append(t)
                out = " ".join(parts).strip()
                if out:
                    return out, None
        return None, "Resposta Mistral sem texto"
    except httpx.HTTPStatusError as e:
        err = e.response.text[:500] if e.response is not None else str(e)
        return None, f"HTTP {e.response.status_code if e.response else '?'}: {err}"
    except Exception as e:  # noqa: BLE001
        return None, str(e)[:500]


def _extract_json_object(text: str) -> dict[str, Any] | None:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```\s*$", "", t)
    m = re.search(r"\{[\s\S]*\}", t)
    if not m:
        return None
    try:
        o = json.loads(m.group(0))
        return o if isinstance(o, dict) else None
    except json.JSONDecodeError:
        return None


@dataclass(frozen=True)
class PropertyImageAnalysis:
    """Resultado da validação + descrição numa única chamada de visão."""

    aceitavel_como_foto_imovel: bool
    motivo_validacao: str
    descricao_curta: str | None


def mistral_analyze_property_image_for_crm(
    image_bytes: bytes,
    *,
    mime_type: str = "image/jpeg",
) -> tuple[PropertyImageAnalysis | None, str | None]:
    """
    Valida se a imagem é adequada como foto de imóvel (evita tela, print de WhatsApp, etc.)
    e, se sim, devolve descrição curta para CRM. Retorna (análise, erro).
    """
    key = mistral_api_key()
    if not key:
        return None, "MISTRAL_API_KEY em falta"
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    data_url = f"data:{mime_type};base64,{b64}"
    model = maria_vision_model()
    instr = (
        "Analisa a imagem para cadastro de imóvel no WhatsApp.\n"
        "Responde APENAS com um JSON válido (sem markdown), exactamente neste formato:\n"
        '{"foto_imovel_aceitavel": true ou false, "motivo_validacao": "texto curto em português", '
        '"descricao_imovel": "2 a 4 frases em português sobre o imóvel ou null"}\n\n'
        "Define foto_imovel_aceitavel=true só se a imagem mostrar o imóvel ou parte dele: "
        "ambientes internos, fachada, área externa da propriedade, planta legível do imóvel.\n"
        "Define foto_imovel_aceitavel=false se for: foto de ecrã/tela, monitor, laptop ou telemóvel a mostrar "
        "WhatsApp ou outra app, conversa de chat visível, print da interface, documento genérico sem foco no espaço, "
        "selfie sem o imóvel, paisagem sem edifício habitável identificável, meme ou imagem irrelevante.\n"
        "Se for false, descricao_imovel deve ser null. Se for true, descreve só o que vês (sem inventar preço nem endereço)."
    )
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": instr},
                    {"type": "image_url", "image_url": data_url},
                ],
            }
        ],
        "max_tokens": 500,
        "temperature": 0.1,
    }
    try:
        r = httpx.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
            timeout=120.0,
        )
        r.raise_for_status()
        body = r.json()
        choices = body.get("choices")
        raw_text = ""
        if isinstance(choices, list) and choices:
            msg = choices[0].get("message") or {}
            content = msg.get("content")
            if isinstance(content, str):
                raw_text = content
            elif isinstance(content, list):
                parts: list[str] = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        t = block.get("text")
                        if isinstance(t, str):
                            parts.append(t)
                raw_text = " ".join(parts)
        obj = _extract_json_object(raw_text) if raw_text.strip() else None
        if not obj:
            return None, "JSON de validação ilisível"
        ok = obj.get("foto_imovel_aceitavel")
        aceitavel = bool(ok) if isinstance(ok, bool) else str(ok).lower() in ("true", "1", "yes")
        motivo = obj.get("motivo_validacao")
        motivo_s = motivo.strip() if isinstance(motivo, str) else "sem motivo"
        desc_v = obj.get("descricao_imovel")
        desc: str | None
        if desc_v is None or (isinstance(desc_v, str) and not desc_v.strip()):
            desc = None
        elif isinstance(desc_v, str):
            desc = desc_v.strip()
        else:
            desc = str(desc_v).strip() or None
        if aceitavel and not desc:
            desc = motivo_s
        return (
            PropertyImageAnalysis(
                aceitavel_como_foto_imovel=aceitavel,
                motivo_validacao=motivo_s[:500],
                descricao_curta=desc[:4000] if desc else None,
            ),
            None,
        )
    except httpx.HTTPStatusError as e:
        err = e.response.text[:500] if e.response is not None else str(e)
        return None, f"HTTP {e.response.status_code if e.response else '?'}: {err}"
    except Exception as e:  # noqa: BLE001
        return None, str(e)[:500]
