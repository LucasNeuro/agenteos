"""Carrega os playbooks Markdown de docs/playbooks/ e monta o prompt do Agent."""

from __future__ import annotations

from pathlib import Path

_SEPARATOR = "\n\n---\n\n"
_RUNTIME_PROMPT_GUARD = """
## Regras técnicas obrigatórias (WhatsApp/UAZAPI)

- Em perguntas de decisão com opções claras, envia sempre opções em bloco explícito.
- Triagem inicial: incluir sempre `<<<UAZ_BUTTONS>>>` com:
  - `Buscar imóvel|fluxo1`
  - `Anunciar imóvel|fluxo2`
  - `Sou corretor/imobiliária|fluxo3`
- Fluxo proprietário: na pergunta `vender` vs `alugar`, incluir sempre:
  - `Vender|vender`
  - `Alugar|alugar`
- Fluxo parceiro: na pergunta `cadastrar imóvel` vs `parceria`, incluir sempre:
  - `Cadastrar imóvel|cadastro_imovel`
  - `Parceria|parceria`
- Não usar Markdown para representar opções quando houver escolha; usar o bloco UAZ.
""".strip()

# Ordem fixa: persona global → núcleo → fluxos (POP Mercado Imobiliário).
_PLAYBOOK_ACTIVE: tuple[str, ...] = (
    "00_mari_persona_global.md",
    "00_mari_mercado_imobiliario_core.md",
    "01_mari_mercado_imobiliario_fluxos.md",
)


def _playbooks_directory() -> Path:
    return Path(__file__).resolve().parent.parent / "docs" / "playbooks"


def load_maria_playbook() -> str:
    directory = _playbooks_directory()
    if not directory.is_dir():
        msg = (
            f"Pasta de playbooks inexistente: {directory}. "
            "Crie docs/playbooks/ com os ficheiros POP Mercado Imobiliário."
        )
        raise FileNotFoundError(msg)

    chunks: list[str] = []
    for filename in _PLAYBOOK_ACTIVE:
        path = directory / filename
        if not path.is_file():
            raise FileNotFoundError(
                f"Playbook obrigatório em falta: {path}. "
                f"Esperados: {', '.join(_PLAYBOOK_ACTIVE)}"
            )
        text = path.read_text(encoding="utf-8").strip()
        if text:
            chunks.append(text)

    if not chunks:
        raise ValueError(f"Playbooks vazios em {directory}")

    return _SEPARATOR.join([_RUNTIME_PROMPT_GUARD, *chunks])
