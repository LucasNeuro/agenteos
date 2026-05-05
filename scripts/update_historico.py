#!/usr/bin/env python3
"""
Atualiza HISTORICO_TRABALHO_MARIA.md com um bloco legivel para nao tecnicos.

Uso local (preview):
  python scripts/update_historico.py --dry-run

CI na branch main:
  python scripts/update_historico.py --write
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FILE = ROOT / "HISTORICO_TRABALHO_MARIA.md"
MARKER_COMMITS = "## Commits recentes considerados"
SECTION_AUTO = "## Registro automatico (CI)"


def _run_git(args: list[str]) -> str:
    return subprocess.check_output(
        ["git", *args],
        cwd=ROOT,
        text=True,
        stderr=subprocess.DEVNULL,
    ).strip()


def _now_stamp() -> str:
    try:
        from zoneinfo import ZoneInfo

        z = ZoneInfo("America/Sao_Paulo")
        return datetime.now(z).strftime("%Y-%m-%d %H:%M") + " (UTC-3)"
    except Exception:
        return datetime.utcnow().strftime("%Y-%m-%d %H:%M") + " UTC"


def _event_plain_pt(event_name: str) -> str:
    if event_name == "push":
        return (
            "Novo codigo foi enviado (push) para o repositorio. "
            "Isto significa que ha alteracoes guardadas no historico do projeto."
        )
    if event_name == "pull_request":
        return (
            "Correu uma verificacao automatica numa proposta de mudanca (Pull Request). "
            "Neste modo o relatorio nao e gravado no ficheiro; apenas se mostra aqui o que seria acrescentado."
        )
    return f"Evento CI: `{event_name}`."


def _run_url() -> str:
    server = os.environ.get("GITHUB_SERVER_URL", "").rstrip("/")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    run = os.environ.get("GITHUB_RUN_ID", "")
    if server and repo and run:
        return f"{server}/{repo}/actions/runs/{run}"
    return "n/d (execucao local ou fora do GitHub Actions)"


def _git_tip() -> tuple[str, str, str]:
    full = _run_git(["rev-parse", "HEAD"])
    short = full[:7]
    subject = _run_git(["log", "-1", "--format=%s"])
    return full, short, subject


def _git_files(limit: int = 40) -> tuple[list[str], int]:
    raw = _run_git(["show", "--pretty=format:", "--name-only", "HEAD"])
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    return lines[:limit], len(lines)


def _replace_ultima(content: str, stamp: str) -> str:
    pat = r"^Ultima atualizacao:.*$"
    if re.search(pat, content, flags=re.MULTILINE):
        return re.sub(pat, f"Ultima atualizacao: {stamp}", content, count=1, flags=re.MULTILINE)
    return f"Ultima atualizacao: {stamp}\n\n" + content


def _ensure_section(content: str) -> tuple[str, int]:
    """Garante SECTION_AUTO antes de MARKER_COMMITS. Retorna (content, index onde inserir novo bloco)."""
    idx_marker = content.find(MARKER_COMMITS)
    if idx_marker == -1:
        idx_marker = len(content)

    sec = content.find(SECTION_AUTO)
    if sec == -1 or sec > idx_marker:
        intro = (
            f"{SECTION_AUTO}\n\n"
            "Esta secao e gerada automaticamente pelo GitHub Actions. Cada entrada resume **o que mudou no codigo** "
            "em linguagem simples. Para testes no Render (botoes, logs WhatsApp), continue a acrescentar notas manualmente "
            "na secao do dia acima.\n\n"
        )
        content = content[:idx_marker] + intro + content[idx_marker:]
        idx_marker = content.find(MARKER_COMMITS)
        sec = content.find(SECTION_AUTO)

    # Inserir novos blocos imediatamente apois o paragrafo introdutorio da secao (apos primeira linha em branco dupla apos titulo)
    insert_at = sec + len(SECTION_AUTO)
    # Saltar ate fim do bloco introdutorio (primeiro "---" opcional - usamos apenas procurar MARKER)
    next_heading = content.find("\n### ", insert_at)
    if next_heading == -1 or next_heading > idx_marker:
        next_heading = idx_marker
    return content, next_heading


def build_block() -> str:
    stamp = _now_stamp()
    event = os.environ.get("GITHUB_EVENT_NAME", "local")
    ref = os.environ.get("GITHUB_REF_NAME") or os.environ.get("GITHUB_HEAD_REF") or "unknown"
    actor = os.environ.get("GITHUB_ACTOR", "local")
    try:
        full_sha, short_sha, subject = _git_tip()
        files, n_files = _git_files()
    except subprocess.CalledProcessError:
        full_sha = short_sha = subject = "(git indisponivel)"
        files, n_files = [], 0

    lines_files = "\n".join(f"  - `{f}`" for f in files) if files else "  - (nenhum ficheiro listado)"
    extra = ""
    if n_files > len(files):
        extra = f"\n  - ... e mais **{n_files - len(files)}** ficheiro(s) (lista truncada)."

    return (
        f"### {stamp} - Atividade no repositorio\n\n"
        f"- **Para nao tecnicos:** {_event_plain_pt(event)}\n"
        f"- **Branch:** `{ref}`\n"
        f"- **Commit:** `{short_sha}` ({(full_sha[:12] + '...') if len(full_sha) >= 12 else full_sha}) - {subject}\n"
        f"- **Quem:** {actor}\n"
        f"- **Detalhe tecnico (CI):** { _run_url() }\n"
        f"- **Ficheiros alterados neste envio:**\n{lines_files}{extra}\n\n"
    )


def maybe_skip_duplicate(content: str, short_sha: str) -> bool:
    start = content.find(SECTION_AUTO)
    if start == -1:
        return False
    window = content[start : start + 200_000]
    return f"`{short_sha}`" in window


def main() -> int:
    ap = argparse.ArgumentParser(description="Atualiza historico do projeto com bloco legivel (CI/local).")
    ap.add_argument("--path", type=Path, default=DEFAULT_FILE, help="Ficheiro Markdown alvo")
    ap.add_argument("--write", action="store_true", help="Grava alteracoes no ficheiro")
    ap.add_argument("--dry-run", action="store_true", help="Mostra o bloco e nao grava")
    args = ap.parse_args()

    block = build_block()
    if args.dry_run:
        print(block)
        return 0
    if not args.write:
        print(block)
        print("\n(Modo preview: use --write para gravar.)\n", file=sys.stderr)
        return 0

    path: Path = args.path
    if not path.is_file():
        print(f"Ficheiro inexistente: {path}", file=sys.stderr)
        return 2

    content = path.read_text(encoding="utf-8")
    try:
        _, short, _ = _git_tip()
    except subprocess.CalledProcessError:
        short = ""

    if short and maybe_skip_duplicate(content, short):
        print(f"Commit {short} ja consta no relatorio automatico — nada a atualizar.")
        return 0

    content = _replace_ultima(content, _now_stamp())
    content, pos = _ensure_section(content)
    content = content[:pos] + "\n" + block + content[pos:]
    path.write_text(content, encoding="utf-8")
    print(f"Atualizado: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
