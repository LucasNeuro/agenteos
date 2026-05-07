"""
Contrato Maria ↔ UAZAPI (uazapiGO).

Usar estas funções no handler do webhook HTTP para alinhar com:
- Mem0 / post-hooks (`user_id` estável por contacto)
- Supabase (`maria_sessions` / mensagens — mesmo external_session_id por contacto)
- Envio de resposta (`POST /send/text`, campo ``number``)

Referência: ``docs/uazapi-openapi-spec (12).yaml`` (Webhook, Message, ``/send/text``, ``/send/menu``).
Handlers: ``uazapi_webhook.py``, ``uazapi_client.py``, ``uazapi_parse.py``.
"""

from __future__ import annotations

import json
import re
from typing import Any, Mapping

# IDs de botão/lista da triagem e subfluxos (resposta imediata; sem debounce de texto).
MARIA_WHATSAPP_IMMEDIATE_TRIAGE_IDS: frozenset[str] = frozenset(
    {
        "fluxo1",
        "fluxo2",
        "fluxo3",
        "fluxo_arquitetura",
        "vender",
        "alugar",
        "cadastro_imovel",
        "parceria",
        "arq_m2_50_100",
        "arq_m2_100_200",
        "arq_m2_200_mais",
        "arq_prazo_imediato",
        "arq_prazo_90",
        "arq_prazo_depois",
    }
)


def _digits_from_jid_or_phone(raw: str) -> str:
    base = raw.strip().split("@", 1)[0]
    return re.sub(r"\D", "", base)


def maria_user_id_from_uaz_message(data: Mapping[str, Any]) -> str | None:
    """
    Identificador estável para AgentOS / Mem0: ``wa_<E.164 só dígitos>``.

    Preferência UAZAPI: ``sender_pn``, depois ``sender``, depois ``chatid`` (1:1).
    """
    for key in ("sender_pn", "sender", "chatid"):
        val = data.get(key)
        if not isinstance(val, str) or not val.strip():
            continue
        digits = _digits_from_jid_or_phone(val)
        if len(digits) >= 10:
            return f"wa_{digits}"
    return None


def uaz_session_id_for_maria(data: Mapping[str, Any]) -> str | None:
    """
    ``session_id`` externo único por contacto (recomendado: igual ao ``user_id`` Maria).
    Assim o histórico Agno e o CRM alinham com um chat WhatsApp.
    """
    return maria_user_id_from_uaz_message(data)


def uaz_send_number_from_message(data: Mapping[str, Any]) -> str | None:
    """
    Valor do campo ``number`` em ``POST /send/text`` (OpenAPI ``sendText``).

    Mantém JID completo quando disponível (ex.: ``5511...@s.whatsapp.net``), senão dígitos.
    """
    chatid = data.get("chatid")
    if isinstance(chatid, str) and chatid.strip():
        return chatid.strip()
    uid = maria_user_id_from_uaz_message(data)
    if uid and uid.startswith("wa_"):
        return uid[3:]
    return None


def uaz_incoming_text(data: Mapping[str, Any]) -> str:
    """Texto legível do utilizador (``text``, ``content`` string/obj, ``body``)."""
    t = data.get("text")
    if isinstance(t, str) and t.strip():
        return t
    c = data.get("content")
    if isinstance(c, str) and c.strip():
        return c
    if isinstance(c, dict):
        for key in ("text", "body", "caption", "message"):
            v = c.get(key)
            if isinstance(v, str) and v.strip():
                return v
    b = data.get("body")
    if isinstance(b, str) and b.strip():
        return b
    return ""


def _content_as_dict(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip().startswith("{"):
        try:
            o = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return o if isinstance(o, dict) else None
    return None


def _first_non_empty_str(*candidates: Any) -> str:
    for v in candidates:
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _list_button_id_from_mapping(obj: Mapping[str, Any]) -> str:
    """Extrai id de botão/lista em payloads UAZ/WhatsApp (chaves comuns)."""
    return _first_non_empty_str(
        obj.get("buttonOrListid"),
        obj.get("button_or_list_id"),
        obj.get("selectedRowId"),
        obj.get("selectedId"),
        obj.get("rowId"),
        obj.get("listRowId"),
    )


def _dig_interactive_reply(obj: Any, depth: int = 0) -> str:
    """Procura reply id em estruturas aninhadas (ex.: interactive / listResponse)."""
    if depth > 5 or obj is None:
        return ""
    if isinstance(obj, dict):
        got = _list_button_id_from_mapping(obj)
        if got:
            return got
        for v in obj.values():
            got = _dig_interactive_reply(v, depth + 1)
            if got:
                return got
    if isinstance(obj, list):
        for item in obj:
            got = _dig_interactive_reply(item, depth + 1)
            if got:
                return got
    return ""


def uaz_incoming_user_turn(data: Mapping[str, Any]) -> str:
    """
    Texto a passar ao agente: mensagem normal, ID de botão/lista, ou ``convertOptions``.

    A UAZ às vezes envia o id **só** dentro de ``content`` (JSON); o root pode vir sem ``text``.
    """
    t = uaz_incoming_text(data).strip()
    if t:
        return t

    bid = _first_non_empty_str(
        data.get("buttonOrListid"),
        data.get("button_or_list_id"),
        data.get("selectedRowId"),
        data.get("selectedId"),
    )
    if bid:
        return bid

    co = data.get("convertOptions")
    if isinstance(co, str) and co.strip():
        return co.strip()

    content = _content_as_dict(data.get("content"))
    if content:
        bid = _list_button_id_from_mapping(content)
        if bid:
            return bid
        bid = _dig_interactive_reply(content.get("interactive"))
        if bid:
            return bid
        bid = _dig_interactive_reply(content)
        if bid:
            return bid

    vote_raw = data.get("vote")
    vote_obj = _content_as_dict(vote_raw) if vote_raw is not None else None
    if vote_obj:
        bid = _dig_interactive_reply(vote_obj)
        if bid:
            return bid

    return ""


# Reforço no prompt quando o webhook expande IDs UAZ — evita repetir triagem/menus errados.
_WHATSAPP_FLOW_CONTEXT_TAIL = (
    " Observa o **histórico** da conversa: **não** voltar ao menu de triagem de 4 opções nem repetir "
    "botões/listas de outro passo já concluído; usa `<<<UAZ_BUTTONS>>>` / `<<<UAZ_LIST>>>` só na **decisão actual** do fluxo."
)


def maria_expand_whatsapp_triage_turn(user_turn: str) -> str:
    """
    Converte IDs de lista/botão da triagem UAZ numa instrução explícita para o modelo.

    Assim o playbook de arquitetura (e os fluxos 1–3) é **activado** mesmo quando o utilizador
    só envia ``fluxo_arquitetura`` (sem texto natural).
    """
    s = (user_turn or "").strip()
    if not s:
        return s
    if s.startswith("[Triagem WhatsApp]"):
        return s

    hints: dict[str, str] = {
        "fluxo1": (
            "[Triagem WhatsApp] O cliente escolheu Buscar imóvel (id fluxo1). "
            "Aplicar o Fluxo 1 em `01_mari_mercado_imobiliario_fluxos.md` — cliente final compra/locação, modo rápido; não pedir e-mail."
            + _WHATSAPP_FLOW_CONTEXT_TAIL
        ),
        "fluxo2": (
            "[Triagem WhatsApp] O cliente escolheu Anunciar imóvel (id fluxo2). "
            "Aplicar o Fluxo 2 (proprietário) em `01_mari_mercado_imobiliario_fluxos.md`."
            + _WHATSAPP_FLOW_CONTEXT_TAIL
        ),
        "fluxo3": (
            "[Triagem WhatsApp] O cliente escolheu Sou corretor/imobiliária (id fluxo3). "
            "Aplicar o Fluxo 3 em `01_mari_mercado_imobiliario_fluxos.md`."
            + _WHATSAPP_FLOW_CONTEXT_TAIL
        ),
        "fluxo_arquitetura": (
            "[Triagem WhatsApp] O cliente escolheu Projeto de arquitetura / interiores (id fluxo_arquitetura). "
            "Seguir `02_mari_arquitetura_cliente_final.md` — **§5.2 continuidade**: se no histórico **já** usaste o nome do cliente "
            "(ex.: Olá, [Nome]) ou ele já o disse, **não** repetir saudação POP nem pedir nome de novo; "
            "**ponte curta** + ir direto a **§6.1** (botões m²). Se o nome **ainda** não existe no histórico, **uma** pergunta curta pelo nome "
            "(sem repetir bem-vindo/Mari). Depois qualificação (m², prazo, cidade), encaminhamento curto, "
            "**registrar_lead_no_crm** com **cliente_projetos** ao fechar. **Não** tratar como compra/aluguel pronto; **não** voltar à triagem mercado."
            + _WHATSAPP_FLOW_CONTEXT_TAIL
        ),
        "vender": (
            "[Triagem WhatsApp] O cliente escolheu Vender (id vender), passo proprietário. "
            "Continuar Fluxo 2 com operação venda."
            + _WHATSAPP_FLOW_CONTEXT_TAIL
        ),
        "alugar": (
            "[Triagem WhatsApp] O cliente escolheu Alugar (id alugar), passo proprietário. "
            "Continuar Fluxo 2 com operação locação."
            + _WHATSAPP_FLOW_CONTEXT_TAIL
        ),
        "cadastro_imovel": (
            "[Triagem WhatsApp] O cliente escolheu Cadastrar imóvel (id cadastro_imovel). "
            "Continuar subfluxo Cadastrar imóvel do Fluxo 3."
            + _WHATSAPP_FLOW_CONTEXT_TAIL
        ),
        "parceria": (
            "[Triagem WhatsApp] O cliente escolheu Parceria (id parceria). "
            "Continuar subfluxo Parceria do Fluxo 3."
            + _WHATSAPP_FLOW_CONTEXT_TAIL
        ),
    }

    if s in hints:
        return hints[s]

    first = s.split()[0]
    if first in hints:
        return hints[first]

    low = s.lower()
    if "fluxo_arquitetura" in low:
        return hints["fluxo_arquitetura"]
    if "projeto de arquitetura" in low and "interiores" in low:
        return hints["fluxo_arquitetura"]

    return s


_FULL_DEBOUNCE_ACK_RE = re.compile(
    r"(?i)^(ok|beleza|sim|não|nao|obrigad|vlw|valeu|perfeito|certo|combinado|pode ser)\b"
)
_GREETING_OR_SHORT_CHAT_RE = re.compile(
    r"(?i)^(bom|boa)\s+(dia|tarde|noite)\b|^(oi|ol[aá]|ola|hey)\b"
)

# Uma palavra curta — debounce rápido ainda faz sentido (evita esperar em «sim» / «oi»).
_SINGLE_WORD_DEBOUNCE_SHORT_OK = frozenset(
    {
        "sim",
        "nao",
        "não",
        "ok",
        "oi",
        "ola",
        "olá",
        "hey",
        "ta",
        "tá",
    }
)


def maria_text_fragment_prefers_full_debounce(fragment: str) -> bool:
    """
    Quando ``True``, um único fragmento **não** usa o debounce «curto» (ex.: 0,55s):
    o utilizador costuma estar a enviar mais bolhas a seguir (dados de imóvel, cidade+m², etc.).
    """
    t = (fragment or "").strip()
    if not t:
        return False
    if any(ch.isdigit() for ch in t):
        return True
    low = t.casefold()
    markers = (
        "metro",
        "metros",
        "m²",
        "m2",
        "mm2",
        "mil",
        "reais",
        "real",
        "r$",
        "bairro",
        "valor",
        "preço",
        "preco",
        "imóvel",
        "imovel",
        "rua",
        "cep",
        "apto",
        "apartamento",
        "casa",
        "sala",
        "quarto",
        "são paulo",
        "sao paulo",
        "rio de janeiro",
    )
    if any(m in low for m in markers):
        return True
    parts = t.split()
    if len(parts) >= 2:
        if _GREETING_OR_SHORT_CHAT_RE.match(t):
            return False
        if _FULL_DEBOUNCE_ACK_RE.match(t):
            return False
        return True
    if len(parts) == 1:
        w = low
        if w in _SINGLE_WORD_DEBOUNCE_SHORT_OK:
            return False
        # Bairros e nomes próprios picados («Pirajussara» sozinho, etc.)
        if len(t) >= 4:
            return True
    return False


def maria_whatsapp_text_should_debounce(
    raw_turn: str, expanded_turn: str, debounce_after_sec: float
) -> bool:
    """
    Free-text (ex.: «Olá» em várias bolhas) usa debounce quando ``debounce_after_sec > 0``.
    Cliques de botão/lista (IDs conhecidos ou turno já expandido para triagem) respondem já.
    """
    if debounce_after_sec <= 0:
        return False
    exp = (expanded_turn or "").strip()
    if exp.startswith("[Triagem WhatsApp]"):
        return False
    raw = (raw_turn or "").strip()
    if raw in MARIA_WHATSAPP_IMMEDIATE_TRIAGE_IDS:
        return False
    parts = raw.split()
    if parts and parts[0] in MARIA_WHATSAPP_IMMEDIATE_TRIAGE_IDS:
        return False
    return True


def uaz_should_ignore_for_chatbot(data: Mapping[str, Any]) -> bool:
    """
    Mensagens a ignorar antes de chamar o agente (ajustar conforme regras de negócio).

    - ``fromMe``: mensagem enviada pela própria instância
    - ``wasSentByApi`` com loop: pré-filtrar no webhook UAZ com ``excludeMessages``
    """
    if data.get("fromMe") is True:
        return True
    if data.get("isGroup") is True:
        return True
    return False
