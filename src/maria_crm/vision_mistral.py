"""Análise de imagem com Mistral (Pixtral ou modelo multimodal configurável)."""

from __future__ import annotations

import base64
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
