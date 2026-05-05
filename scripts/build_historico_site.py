#!/usr/bin/env python3
"""
Gera _site/index.html a partir de HISTORICO_TRABALHO_MARIA.md (GitHub Pages).

Dependencia (CI instala com pip): PyPI `markdown`.
"""

from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MD = ROOT / "HISTORICO_TRABALHO_MARIA.md"
OUT_DIR = ROOT / "_site"


def _wrap_page(title: str, inner_html: str) -> str:
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
      background: #fafafa;
    }}
    body {{
      margin: 0;
      padding: 1.25rem;
    }}
    main {{
      max-width: 44rem;
      margin: 0 auto;
      background: #fff;
      padding: 1.75rem 2rem;
      border-radius: 10px;
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
    hr {{ border: none; border-top: 1px solid #e5e5e5; margin: 1.75rem 0; }}
    a {{ color: #0b63d6; }}
    footer {{
      max-width: 44rem;
      margin: 1.25rem auto 0;
      font-size: 0.88rem;
      color: #555;
    }}
  </style>
</head>
<body>
  <main>
{inner_html}
  </main>
  <footer>
    Gerado automaticamente a partir do Markdown no repositorio. Para a versao editavel, ver o ficheiro na raiz do projeto no GitHub.
  </footer>
</body>
</html>
"""


def main() -> int:
    try:
        import markdown
    except ImportError:
        print("Instale: pip install markdown", file=sys.stderr)
        return 2

    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, default=DEFAULT_MD)
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = ap.parse_args()

    if not args.input.is_file():
        print(f"Ficheiro nao encontrado: {args.input}", file=sys.stderr)
        return 2

    md_text = args.input.read_text(encoding="utf-8")
    first_line = md_text.strip().split("\n", 1)[0].lstrip("# ").strip() or "Historico de trabalho"
    inner = markdown.markdown(
        md_text,
        extensions=["extra", "sane_lists"],
        output_format="html5",
    )
    page = _wrap_page(first_line, inner)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "index.html").write_text(page, encoding="utf-8")
    print(f"Escrito: {args.out_dir / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
