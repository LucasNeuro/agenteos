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
      --bg: #f5f7fb;
      --bg-soft: #eef2f9;
      --surface: #ffffff;
      --surface-2: #f8faff;
      --text: #151a25;
      --muted: #5b6475;
      --border: #dde3ef;
      --primary: #2b6de0;
      --primary-soft: #eaf1ff;
      --shadow: 0 10px 26px rgba(15, 30, 64, 0.08);
      color-scheme: light;
    }}
    html[data-theme="dark"] {{
      --bg: #0f131c;
      --bg-soft: #151c29;
      --surface: #171f2d;
      --surface-2: #1d2637;
      --text: #e7edf7;
      --muted: #aab4c8;
      --border: #2a364d;
      --primary: #78a9ff;
      --primary-soft: #202e46;
      --shadow: 0 14px 34px rgba(0, 0, 0, 0.35);
      color-scheme: dark;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, sans-serif;
      line-height: 1.58;
      color: var(--text);
      background: radial-gradient(1200px 420px at top, var(--bg-soft), var(--bg));
      min-height: 100vh;
    }}
    .progress {{
      position: fixed;
      top: 0;
      left: 0;
      height: 3px;
      width: 100%;
      background: transparent;
      z-index: 60;
    }}
    .progress > span {{
      display: block;
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, var(--primary), #55c2ff);
      transition: width 120ms linear;
    }}
    .layout {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 1.25rem;
      display: grid;
      gap: 1rem;
      grid-template-columns: 300px minmax(0, 1fr);
      align-items: start;
    }}
    .toc {{
      position: sticky;
      top: 1rem;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 14px;
      box-shadow: var(--shadow);
      max-height: calc(100vh - 2rem);
      overflow: auto;
      padding: 1rem;
    }}
    .toc h2 {{
      margin: 0 0 0.65rem 0;
      font-size: 0.98rem;
      letter-spacing: 0.01em;
    }}
    .toc .tools {{
      display: flex;
      gap: 0.5rem;
      margin-bottom: 0.8rem;
    }}
    .toc input {{
      width: 100%;
      border: 1px solid var(--border);
      background: var(--surface-2);
      color: var(--text);
      border-radius: 10px;
      padding: 0.52rem 0.62rem;
      outline: none;
      font-size: 0.92rem;
    }}
    .toc button {{
      border: 1px solid var(--border);
      background: var(--surface-2);
      color: var(--text);
      border-radius: 10px;
      padding: 0.52rem 0.62rem;
      cursor: pointer;
      font-size: 0.86rem;
    }}
    .toc button:hover {{ border-color: var(--primary); }}
    .toc ul {{
      list-style: none;
      margin: 0;
      padding: 0;
      display: grid;
      gap: 0.22rem;
    }}
    .toc li a {{
      display: block;
      text-decoration: none;
      color: var(--muted);
      font-size: 0.89rem;
      padding: 0.36rem 0.46rem;
      border-radius: 8px;
      border: 1px solid transparent;
      word-break: break-word;
    }}
    .toc li a:hover {{
      color: var(--primary);
      background: var(--primary-soft);
      border-color: var(--border);
    }}
    .toc li a.active {{
      color: var(--primary);
      border-color: var(--primary);
      background: var(--primary-soft);
      font-weight: 600;
    }}
    .toc li.level-h3 a {{
      padding-left: 1rem;
      font-size: 0.84rem;
    }}
    .content {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 14px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }}
    .topbar {{
      position: sticky;
      top: 0;
      z-index: 20;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 0.75rem;
      padding: 0.78rem 1rem;
      border-bottom: 1px solid var(--border);
      background: color-mix(in srgb, var(--surface) 92%, transparent);
      backdrop-filter: blur(6px);
    }}
    .topbar .title {{
      font-size: 0.95rem;
      color: var(--muted);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .topbar .actions {{
      display: flex;
      gap: 0.5rem;
    }}
    .topbar .actions button {{
      border: 1px solid var(--border);
      background: var(--surface-2);
      color: var(--text);
      border-radius: 10px;
      padding: 0.48rem 0.62rem;
      cursor: pointer;
      font-size: 0.82rem;
    }}
    .topbar .actions button:hover {{
      border-color: var(--primary);
      color: var(--primary);
    }}
    .article {{
      padding: 1.35rem 1.35rem 1.8rem;
    }}
    h1, h2, h3 {{
      line-height: 1.24;
      scroll-margin-top: 88px;
    }}
    h1 {{
      font-size: clamp(1.45rem, 3vw, 2rem);
      margin-top: 0.15rem;
      margin-bottom: 0.85rem;
    }}
    h2 {{
      margin-top: 1.6rem;
      padding-top: 0.4rem;
      border-top: 1px solid var(--border);
    }}
    h3 {{ margin-top: 1.2rem; }}
    p, li {{
      font-size: 0.97rem;
      color: var(--text);
    }}
    li {{ margin-bottom: 0.2rem; }}
    .anchor-link {{
      opacity: 0;
      margin-left: 0.35rem;
      text-decoration: none;
      font-size: 0.82em;
      color: var(--primary);
      transition: opacity 0.18s ease;
    }}
    h1:hover .anchor-link, h2:hover .anchor-link, h3:hover .anchor-link {{
      opacity: 1;
    }}
    code, pre {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.91em;
      background: var(--surface-2);
      border: 1px solid var(--border);
      border-radius: 8px;
    }}
    pre {{
      padding: 0.75rem 1rem;
      overflow: auto;
      box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--border) 60%, transparent);
    }}
    code {{ padding: 0.1em 0.35em; }}
    pre code {{ padding: 0; border: 0; background: none; }}
    hr {{ border: none; border-top: 1px solid var(--border); margin: 1.5rem 0; }}
    a {{ color: var(--primary); }}
    .meta {{
      margin: 0 0 1rem;
      padding: 0.72rem 0.82rem;
      border: 1px solid var(--border);
      border-radius: 10px;
      font-size: 0.87rem;
      color: var(--muted);
      background: var(--surface-2);
    }}
    mark {{
      background: #ffe08a;
      color: #2a1f00;
      border-radius: 3px;
      padding: 0.02em 0.12em;
    }}
    .empty {{
      color: var(--muted);
      font-size: 0.86rem;
      margin-top: 0.6rem;
      display: none;
    }}
    .fab-top {{
      position: fixed;
      right: 1rem;
      bottom: 1rem;
      z-index: 40;
      border: 1px solid var(--border);
      background: var(--surface);
      color: var(--text);
      width: 42px;
      height: 42px;
      border-radius: 50%;
      cursor: pointer;
      box-shadow: var(--shadow);
      display: none;
    }}
    .fab-top.show {{ display: inline-flex; align-items: center; justify-content: center; }}
    @media (max-width: 1000px) {{
      .layout {{
        grid-template-columns: 1fr;
      }}
      .toc {{
        position: static;
        max-height: none;
      }}
    }}
    @media (max-width: 640px) {{
      .layout {{ padding: 0.7rem; }}
      .article {{ padding: 1rem 0.95rem 1.3rem; }}
      .topbar .title {{ font-size: 0.84rem; }}
      .topbar .actions button {{ padding: 0.45rem 0.56rem; }}
    }}
  </style>
</head>
<body>
  <div class="progress"><span id="reading-progress"></span></div>
  <div class="layout">
    <aside class="toc" aria-label="Indice do relatorio">
      <h2>Indice</h2>
      <div class="tools">
        <input id="search-input" type="search" placeholder="Buscar no relatorio..." />
      </div>
      <ul id="toc-list"></ul>
      <p id="toc-empty" class="empty">Nenhuma secao encontrada para essa busca.</p>
    </aside>

    <main class="content">
      <div class="topbar">
        <div class="title">{safe_title}</div>
        <div class="actions">
          <button id="btn-expand-code" type="button" title="Expandir/recolher blocos de codigo">Codigo</button>
          <button id="btn-theme" type="button" title="Alternar tema">Tema</button>
        </div>
      </div>
      <article class="article" id="report-content">
        <p class="meta">Relatorio do projeto Mari (somente leitura). O conteudo e lido do ficheiro no servidor a cada pedido. Apos alterar o Markdown, faca um novo deploy no Render para ver a versao nova.</p>
        {body_html}
      </article>
    </main>
  </div>
  <button id="fab-top" class="fab-top" type="button" aria-label="Voltar ao topo">↑</button>
  <script>
    (function() {{
      const root = document.documentElement;
      const content = document.getElementById("report-content");
      const tocList = document.getElementById("toc-list");
      const searchInput = document.getElementById("search-input");
      const tocEmpty = document.getElementById("toc-empty");
      const progress = document.getElementById("reading-progress");
      const btnTheme = document.getElementById("btn-theme");
      const btnCode = document.getElementById("btn-expand-code");
      const fabTop = document.getElementById("fab-top");

      if (!content || !tocList || !searchInput || !tocEmpty || !progress || !btnTheme || !btnCode || !fabTop) return;

      function slugify(s) {{
        return String(s || "")
          .toLowerCase()
          .normalize("NFD")
          .replace(/[\\u0300-\\u036f]/g, "")
          .replace(/[^a-z0-9\\s-]/g, "")
          .trim()
          .replace(/\\s+/g, "-")
          .replace(/-+/g, "-")
          .slice(0, 80);
      }}

      const themeKey = "maria_report_theme";
      const savedTheme = localStorage.getItem(themeKey);
      if (savedTheme === "dark" || savedTheme === "light") {{
        root.setAttribute("data-theme", savedTheme);
      }} else if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {{
        root.setAttribute("data-theme", "dark");
      }}

      btnTheme.addEventListener("click", function() {{
        const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
        root.setAttribute("data-theme", next);
        localStorage.setItem(themeKey, next);
      }});

      const headings = Array.from(content.querySelectorAll("h1, h2, h3"));
      const used = new Set();
      headings.forEach(function(h) {{
        const text = (h.textContent || "").trim();
        if (!text) return;
        let id = h.id || slugify(text) || "secao";
        while (used.has(id)) {{
          id = id + "-x";
        }}
        used.add(id);
        h.id = id;
        const a = document.createElement("a");
        a.href = "#" + id;
        a.className = "anchor-link";
        a.textContent = "#";
        a.setAttribute("aria-label", "Link desta secao");
        h.appendChild(a);
      }});

      const tocItems = headings.map(function(h) {{
        const li = document.createElement("li");
        li.className = "level-" + h.tagName.toLowerCase();
        const a = document.createElement("a");
        a.href = "#" + h.id;
        a.textContent = (h.textContent || "").replace(/#\\s*$/, "").trim();
        li.appendChild(a);
        tocList.appendChild(li);
        return {{ heading: h, li: li, a: a }};
      }});

      function updateActiveToc() {{
        let active = null;
        const topOffset = 120;
        for (const item of tocItems) {{
          const rect = item.heading.getBoundingClientRect();
          if (rect.top - topOffset <= 0) {{
            active = item;
          }} else {{
            break;
          }}
        }}
        tocItems.forEach(function(item) {{
          item.a.classList.toggle("active", item === active);
        }});
      }}

      function updateReadingProgress() {{
        const doc = document.documentElement;
        const total = doc.scrollHeight - window.innerHeight;
        const pct = total > 0 ? Math.max(0, Math.min(100, (window.scrollY / total) * 100)) : 0;
        progress.style.width = pct.toFixed(1) + "%";
        fabTop.classList.toggle("show", window.scrollY > 320);
      }}

      function clearMarks() {{
        content.querySelectorAll("mark[data-hl='1']").forEach(function(mark) {{
          const t = document.createTextNode(mark.textContent || "");
          mark.replaceWith(t);
        }});
      }}

      function highlightTerm(term) {{
        clearMarks();
        if (!term) return;
        const escaped = term.replace(/[.*+?^${{}}()|[\\]\\\\]/g, "\\\\$&");
        const rgx = new RegExp(escaped, "gi");
        const walker = document.createTreeWalker(content, NodeFilter.SHOW_TEXT, null);
        const nodes = [];
        while (walker.nextNode()) {{
          const n = walker.currentNode;
          if (!n || !n.nodeValue) continue;
          const parent = n.parentElement;
          if (!parent) continue;
          if (["SCRIPT", "STYLE", "MARK"].includes(parent.tagName)) continue;
          nodes.push(n);
        }}
        nodes.forEach(function(n) {{
          const v = n.nodeValue;
          if (!v || !rgx.test(v)) return;
          rgx.lastIndex = 0;
          const frag = document.createDocumentFragment();
          let last = 0;
          v.replace(rgx, function(match, idx) {{
            if (idx > last) frag.appendChild(document.createTextNode(v.slice(last, idx)));
            const m = document.createElement("mark");
            m.setAttribute("data-hl", "1");
            m.textContent = match;
            frag.appendChild(m);
            last = idx + match.length;
            return match;
          }});
          if (last < v.length) frag.appendChild(document.createTextNode(v.slice(last)));
          n.parentNode.replaceChild(frag, n);
        }});
      }}

      function filterToc() {{
        const q = (searchInput.value || "").trim().toLowerCase();
        let visible = 0;
        tocItems.forEach(function(item) {{
          const text = (item.a.textContent || "").toLowerCase();
          const ok = !q || text.includes(q);
          item.li.style.display = ok ? "" : "none";
          if (ok) visible += 1;
        }});
        tocEmpty.style.display = visible ? "none" : "block";
        highlightTerm(q);
      }}

      const blocks = Array.from(content.querySelectorAll("pre"));
      let codeExpanded = true;
      function setCodeExpanded(next) {{
        codeExpanded = !!next;
        blocks.forEach(function(b) {{
          b.style.display = codeExpanded ? "" : "none";
        }});
        btnCode.textContent = codeExpanded ? "Codigo" : "Codigo oculto";
      }}
      btnCode.addEventListener("click", function() {{
        setCodeExpanded(!codeExpanded);
      }});

      searchInput.addEventListener("input", filterToc);
      window.addEventListener("scroll", function() {{
        updateActiveToc();
        updateReadingProgress();
      }}, {{ passive: true }});

      fabTop.addEventListener("click", function() {{
        window.scrollTo({{ top: 0, behavior: "smooth" }});
      }});

      updateActiveToc();
      updateReadingProgress();
      setCodeExpanded(true);
    }})();
  </script>
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
