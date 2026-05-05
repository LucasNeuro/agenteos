"""Rota publica (Render) para o relatorio `HISTORICO_TRABALHO_MARIA.md` em HTML."""

from __future__ import annotations

import html
import os
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

ROUTER_TAG = "Relatorio Maria"


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def historico_markdown_path() -> Path:
    """Caminho do ficheiro; override opcional no Render com MARIA_HISTORICO_PATH."""
    raw = os.getenv("MARIA_HISTORICO_PATH", "").strip()
    if raw:
        return Path(raw)
    return _project_root() / "HISTORICO_TRABALHO_MARIA.md"


def _require_secret_if_configured(
    request: Request,
    x_maria_historico_secret: str | None = Header(default=None, alias="X-Maria-Historico-Secret"),
    t: str | None = Query(default=None, description="Token igual a MARIA_HISTORICO_SECRET"),
) -> None:
    secret = os.getenv("MARIA_HISTORICO_SECRET", "").strip()
    if not secret:
        return
    if (t or "").strip() == secret:
        return
    if (x_maria_historico_secret or "").strip() == secret:
        return
    raise HTTPException(
        status_code=401,
        detail="Relatorio protegido: definir query ?t=... ou header X-Maria-Historico-Secret.",
    )


def _wrap_html(title: str, body_html: str) -> str:
    safe_title = html.escape(title, quote=True)
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{safe_title}</title>
  <style>
    :root {{
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, sans-serif;
      line-height: 1.55;
      color: #111;
      background: #f5f5f5;
    }}
    body {{ margin: 0; padding: 1rem; }}
    main {{
      max-width: 48rem;
      margin: 0 auto;
      background: #fff;
      padding: 1.75rem 2rem;
      border-radius: 8px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }}
    h1, h2, h3 {{ line-height: 1.25; }}
    code, pre {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.92em;
      background: #f4f4f5;
      border-radius: 4px;
    }}
    pre {{ padding: 0.75rem 1rem; overflow: auto; }}
    code {{ padding: 0.1em 0.35em; }}
    pre code {{ padding: 0; background: none; }}
    hr {{ border: none; border-top: 1px solid #e5e5e5; margin: 1.5rem 0; }}
    a {{ color: #0b63d6; }}
    .meta {{ font-size: 0.85rem; color: #666; margin-bottom: 1rem; }}
  </style>
</head>
<body>
  <main>
    <p class="meta">Relatorio do projeto Mari (somente leitura). O conteudo e lido do ficheiro no servidor a cada pedido — apos alterar o Markdown, faca um novo deploy no Render para ver a versao nova.</p>
    {body_html}
  </main>
</body>
</html>
"""


def build_historico_router() -> APIRouter:
    router = APIRouter(tags=[ROUTER_TAG])

    def _serve_relatorio(
        request: Request,
        x_maria_historico_secret: str | None,
        t: str | None,
    ) -> HTMLResponse:
        _require_secret_if_configured(request, x_maria_historico_secret, t)
        path = historico_markdown_path()
        if not path.is_file():
            raise HTTPException(
                status_code=404,
                detail=f"Ficheiro de historico nao encontrado: {path}",
            )
        try:
            import markdown
        except ImportError as e:  # pragma: no cover
            raise HTTPException(
                status_code=500,
                detail="Dependencia 'markdown' em falta no servidor.",
            ) from e

        md_text = path.read_text(encoding="utf-8")
        first_line = md_text.strip().split("\n", 1)[0].lstrip("# ").strip() or "Relatorio Mari"
        inner = markdown.markdown(
            md_text,
            extensions=["extra", "sane_lists"],
            output_format="html5",
        )
        page = _wrap_html(first_line, inner)
        return HTMLResponse(content=page, media_type="text/html; charset=utf-8")

    @router.get("/relatorio", response_class=HTMLResponse)
    def relatorio_maria(
        request: Request,
        x_maria_historico_secret: str | None = Header(default=None, alias="X-Maria-Historico-Secret"),
        t: str | None = Query(default=None),
    ) -> HTMLResponse:
        return _serve_relatorio(request, x_maria_historico_secret, t)

    @router.get("/relatorios", response_class=HTMLResponse)
    def relatorios_maria_alias(
        request: Request,
        x_maria_historico_secret: str | None = Header(default=None, alias="X-Maria-Historico-Secret"),
        t: str | None = Query(default=None),
    ) -> HTMLResponse:
        """Alias comum por engano (/relatorios em vez de /relatorio)."""
        return _serve_relatorio(request, x_maria_historico_secret, t)

    return router
