"""Extrai corpo + interativo UAZAPI — botões (``type: button``) ou lista (``type: list``)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

# Até 3 botões de resposta — limite WhatsApp / UAZ para `type: "button"`.
_MAX_BUTTONS = 3

_BTN_START = "<<<UAZ_BUTTONS>>>"
_BTN_END = "<<<END_UAZ_BUTTONS>>>"

_LIST_START = "<<<UAZ_LIST>>>"
_LIST_END = "<<<END_UAZ_LIST>>>"

# Triagem POP: o modelo por vezes usa negrito Markdown em vez do bloco UAZ.
_TRIAGE_IDS = frozenset({"fluxo1", "fluxo2", "fluxo3"})


@dataclass(frozen=True)
class MariaUazParsedReply:
    """Resultado do parse da resposta da Mari para envio WhatsApp."""

    body: str
    send_kind: Literal["text", "button", "list"] = "text"
    button_choices: tuple[str, ...] = ()
    list_button: str | None = None
    list_choices: tuple[str, ...] = ()
    footer_text: str | None = None

    @property
    def has_interactive(self) -> bool:
        return self.send_kind != "text"


def _normalize_line_for_triage(line: str) -> str:
    s = line.strip().lower()
    s = re.sub(r"^\s*[-–—•]+\s*", "", s)
    s = s.replace("*", "").replace("_", "").strip()
    return s


def _line_looks_like_option_row(line: str) -> bool:
    """Evita ler a frase longa da triagem («quer anunciar um imóvel?») como botão."""
    if any(ch in line for ch in "*_"):
        return True
    s = line.strip()
    if not s or s.endswith("?"):
        return False
    return len(s) <= 55


def _line_to_triage_choice(line: str) -> str | None:
    c = _normalize_line_for_triage(line)
    if not c:
        return None
    if re.search(r"\bbuscar\b", c) and ("imóvel" in c or "imovel" in c):
        return "Buscar imóvel|fluxo1"
    if re.search(r"\banunciar\b", c) and ("imóvel" in c or "imovel" in c):
        return "Anunciar imóvel|fluxo2"
    if "corretor" in c or "imobiliária" in c or "imobiliaria" in c:
        return "Sou corretor/imobiliária|fluxo3"
    return None


def _infer_triage_buttons_from_markdown(raw: str) -> tuple[str, list[str]] | None:
    """Se a Mari listar as 3 opções de triagem (mesmo em ***negrito***), monta choices UAZ."""
    lines = raw.splitlines()
    ordered: list[str] = []
    seen: set[str] = set()
    first_opt_idx: int | None = None
    for i, line in enumerate(lines):
        if not _line_looks_like_option_row(line):
            continue
        ch = _line_to_triage_choice(line)
        if ch is None:
            continue
        bid = ch.rsplit("|", 1)[-1]
        if bid in seen:
            continue
        seen.add(bid)
        if first_opt_idx is None:
            first_opt_idx = i
        ordered.append(ch)
        if len(ordered) == _MAX_BUTTONS:
            break
    if len(ordered) != _MAX_BUTTONS or seen != _TRIAGE_IDS or first_opt_idx is None:
        return None
    body_lines = lines[:first_opt_idx]
    while body_lines and not body_lines[-1].strip():
        body_lines.pop()
    while body_lines and body_lines[-1].strip() in ("---", "—", "–", "-"):
        body_lines.pop()
    body = "\n".join(body_lines).strip()
    return (body, ordered)


def _strip_option_bullet_prefix(line: str) -> str:
    s = line.strip()
    # 1) Opção / 1. Opção / 1 - Opção
    s = re.sub(r"^\d{1,2}\s*[\)\.\-:]\s*", "", s)
    # - Opção / * Opção / • Opção
    s = re.sub(r"^[-–—*•]+\s*", "", s)
    # a) Opção / A. Opção
    s = re.sub(r"^[A-Za-z]\s*[\)\.\-:]\s*", "", s)
    return s.strip()


def _normalize_label_for_id(label: str) -> str:
    s = label.lower().strip()
    s = (
        s.replace("á", "a")
        .replace("à", "a")
        .replace("ã", "a")
        .replace("â", "a")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("õ", "o")
        .replace("ú", "u")
        .replace("ç", "c")
    )
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s[:40] or "opcao"


def _infer_generic_options_from_markdown(raw: str) -> tuple[str, list[str]] | None:
    """
    Fallback genérico:
    - se a resposta terminar com 2-3 linhas de opções (bullet/numeração), envia botões;
    - com 4+ opções, envia lista.
    """
    lines = raw.splitlines()
    candidates: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        # Só considera linhas com cara clara de item.
        if not re.match(r"^\s*(\d{1,2}\s*[\)\.\-:]|[-–—*•]+|[A-Za-z]\s*[\)\.\-:])\s+", line):
            continue
        label = _strip_option_bullet_prefix(line)
        if not label or len(label) > 60 or label.endswith("?"):
            continue
        if label.startswith("[") and label.endswith("]"):
            # Parece secção de lista UAZ; não inferir aqui.
            continue
        candidates.append((i, label))

    if len(candidates) < 2:
        return None

    # Garante bloco contíguo no final da mensagem (mais previsível para UX).
    block: list[tuple[int, str]] = [candidates[-1]]
    for item in reversed(candidates[:-1]):
        if block[0][0] - item[0] <= 1:
            block.insert(0, item)
        else:
            break
    if len(block) < 2:
        return None

    first_idx = block[0][0]
    tail_has_text = any(ln.strip() for ln in lines[block[-1][0] + 1 :])
    if tail_has_text:
        return None

    unique_labels: list[str] = []
    seen_labels: set[str] = set()
    for _, lb in block:
        key = lb.lower().strip()
        if key in seen_labels:
            continue
        seen_labels.add(key)
        unique_labels.append(lb)

    if len(unique_labels) < 2:
        return None

    body_lines = lines[:first_idx]
    while body_lines and not body_lines[-1].strip():
        body_lines.pop()
    body = "\n".join(body_lines).strip()
    if not body:
        return None

    ids_seen: set[str] = set()
    choices: list[str] = []
    for label in unique_labels:
        cid = _normalize_label_for_id(label)
        base = cid
        n = 2
        while cid in ids_seen:
            cid = f"{base}_{n}"
            n += 1
        ids_seen.add(cid)
        choices.append(f"{label}|{cid}")
    return (body, choices)


def _infer_buttons_from_question(raw: str) -> tuple[str, list[str]] | None:
    """
    Fallback por intenção (quando o modelo pergunta, mas não lista opções em linhas):
    - triagem inicial (buscar/anunciar/corretor);
    - proprietário (vender/alugar);
    - parceiro (cadastrar imóvel/parceria).
    """
    text = raw.strip()
    if not text:
        return None
    norm = text.lower().replace("imobiliária", "imobiliaria")

    has_busca = re.search(r"\bbusc\w*\b", norm) is not None
    has_anuncio = re.search(r"\banunci\w*\b", norm) is not None
    has_imovel = "imovel" in (
        norm.replace("ó", "o")
        .replace("í", "i")
        .replace("ê", "e")
        .replace("á", "a")
        .replace("â", "a")
        .replace("ã", "a")
    )
    triage_hit = (has_busca and has_anuncio and has_imovel) and (
        "corretor" in norm or "imobiliaria" in norm or "parceria" in norm
    )
    if triage_hit:
        return (
            text,
            [
                "Buscar imóvel|fluxo1",
                "Anunciar imóvel|fluxo2",
                "Sou corretor/imobiliária|fluxo3",
            ],
        )

    if ("vender" in norm and "alugar" in norm and "imovel" in norm.replace("ó", "o")):
        return (text, ["Vender|vender", "Alugar|alugar"])

    if ("cadastrar" in norm and "imovel" in norm.replace("ó", "o")) and "parceria" in norm:
        return (text, ["Cadastrar imóvel|cadastro_imovel", "Parceria|parceria"])

    return None


def _parse_explicit_list_block(before: str, middle: str) -> MariaUazParsedReply | None:
    """
    ``<<<UAZ_LIST>>>``
    Texto do botão que abre a lista (ex.: Selecione a Unidade)
    FOOTER: rodapé opcional
    [Secção]
    Item|id|descrição opcional
    ``<<<END_UAZ_LIST>>>``
    """
    lines = [ln.strip() for ln in middle.strip().splitlines() if ln.strip()]
    if not lines:
        return None
    footer: str | None = None
    list_button = lines[0]
    idx = 1
    if idx < len(lines) and lines[idx].upper().startswith("FOOTER:"):
        footer = lines[idx].split(":", 1)[1].strip()
        idx += 1
    choices = lines[idx:]
    if not choices:
        return None
    return MariaUazParsedReply(
        body=before.strip(),
        send_kind="list",
        list_button=list_button,
        list_choices=tuple(choices),
        footer_text=footer,
    )


def _parse_explicit_button_block(before: str, middle: str) -> MariaUazParsedReply:
    lines = [ln.strip() for ln in middle.strip().splitlines() if ln.strip()]
    body = before.strip()
    if not lines:
        return MariaUazParsedReply(body=body or middle.strip(), send_kind="text")
    if len(lines) > _MAX_BUTTONS:
        # Mais de 3 opções: WhatsApp reply-buttons não suportam; usar lista com secção única.
        list_choices: list[str] = ["[Opções]"] + lines
        return MariaUazParsedReply(
            body=body,
            send_kind="list",
            list_button="Ver opções",
            list_choices=tuple(list_choices),
        )
    return MariaUazParsedReply(
        body=body,
        send_kind="button",
        button_choices=tuple(lines[:_MAX_BUTTONS]),
    )


def parse_maria_reply_for_uaz(raw: str) -> MariaUazParsedReply:
    """
    Interpreta blocos ``UAZ_LIST`` (menu tipo lista / “Selecione…” — como no exemplo Clube do Auto)
    ou ``UAZ_BUTTONS`` (até 3 botões). Mais de 3 linhas no bloco de botões vira lista automaticamente.

    Fallback: triagem em Markdown (3 opções em negrito).
    """
    if _LIST_START in raw and _LIST_END in raw:
        before, rest = raw.split(_LIST_START, 1)
        middle, after = rest.split(_LIST_END, 1)
        parsed = _parse_explicit_list_block(before, middle)
        if parsed is not None:
            return parsed
        return MariaUazParsedReply(body=(before.strip() + "\n" + after.strip()).strip() or raw.strip(), send_kind="text")

    if _BTN_START in raw and _BTN_END in raw:
        before, rest = raw.split(_BTN_START, 1)
        middle, after = rest.split(_BTN_END, 1)
        return _parse_explicit_button_block(before, middle)

    inferred = _infer_triage_buttons_from_markdown(raw)
    if inferred is not None:
        body, choices = inferred
        return MariaUazParsedReply(body=body, send_kind="button", button_choices=tuple(choices))

    inferred_generic = _infer_generic_options_from_markdown(raw)
    if inferred_generic is not None:
        body, choices = inferred_generic
        if len(choices) <= _MAX_BUTTONS:
            return MariaUazParsedReply(body=body, send_kind="button", button_choices=tuple(choices))
        list_choices: list[str] = ["[Opções]"] + choices
        return MariaUazParsedReply(
            body=body,
            send_kind="list",
            list_button="Selecione uma opção",
            list_choices=tuple(list_choices),
        )

    inferred_question = _infer_buttons_from_question(raw)
    if inferred_question is not None:
        body, choices = inferred_question
        return MariaUazParsedReply(body=body, send_kind="button", button_choices=tuple(choices[:_MAX_BUTTONS]))

    return MariaUazParsedReply(body=raw.strip(), send_kind="text")


def split_maria_reply_for_uaz(raw: str) -> tuple[str, list[str] | None]:
    """Compatível com chamadas antigas: só expõe botões ``type: button`` (não listas)."""
    p = parse_maria_reply_for_uaz(raw)
    if p.send_kind == "button" and p.button_choices:
        return (p.body, list(p.button_choices))
    return (p.body if p.send_kind == "text" else p.body, None)
