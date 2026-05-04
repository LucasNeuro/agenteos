"""Carrega os playbooks Markdown de docs/playbooks/ e monta o prompt do Agent."""

from __future__ import annotations

from pathlib import Path

_SEPARATOR = "\n\n---\n\n"


def _playbooks_directory() -> Path:
    return Path(__file__).resolve().parent.parent / "docs" / "playbooks"


def load_maria_playbook() -> str:
    directory = _playbooks_directory()
    if not directory.is_dir():
        msg = (
            f"Pasta de playbooks inexistente: {directory}. "
            "Crie docs/playbooks/ com ficheiros .md (ver 00_router.md)."
        )
        raise FileNotFoundError(msg)

    chunks: list[str] = []
    for path in sorted(directory.glob("*.md")):
        name = path.name.lower()
        if name == "readme.md":
            continue
        text = path.read_text(encoding="utf-8").strip()
        if text:
            chunks.append(text)

    if not chunks:
        raise ValueError(f"Nenhum playbook .md encontrado em {directory}")

    return _SEPARATOR.join(chunks)
