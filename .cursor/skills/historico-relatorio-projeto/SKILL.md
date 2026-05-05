---
name: historico-relatorio-projeto
description: Estabelece o padrao de relatorio Markdown na raiz (HISTORICO), script Python de atualizacao e GitHub Actions (preview em PR, commit automatico em main com anti-loop). Orienta replicacao em novos projetos e opcoes de pagina publica para a equipa. Usa quando o utilizador pede relatorio de trabalho, diario de projeto, CI de historico, GitHub Pages para partilhar relatorio, ou replicar o fluxo de agenteos noutro repositorio.
disable-model-invocation: false
---

# Historico de trabalho + relatorio (projeto e GitHub)

## Objetivo

Manter um **unico ficheiro Markdown** na **raiz** do repositorio com:

- notas **manuais** por dia (gestao, testes Render, decisoes);
- secao **Registro automatico (CI)** preenchida pelo GitHub Actions em **push a `main`**.

Referencias de implementacao neste monorepo: `HISTORICO_TRABALHO_MARIA.md`, `scripts/update_historico.py`, `.github/workflows/historico-ci.yml`, `scripts/build_historico_site.py`, `.github/workflows/pages-historico.yml`.

## GitHub Pages (repo publico - agenteos)

- Workflow: `.github/workflows/pages-historico.yml` gera `_site/index.html` a partir do Markdown e faz deploy via **GitHub Actions** (source Pages).
- **Primeira vez:** no GitHub, `Settings` - `Pages` - **Build and deployment** - **Source:** **GitHub Actions** (nao "Deploy from branch" a menos que mudem de estrategia).
- O URL publico aparece na mesma pagina de Settings e no sumario do job `deploy` (environment `github-pages`), normalmente `https://<owner>.github.io/<repo>/`.
- Pasta `_site` esta em `.gitignore`; o deploy usa apenas o artefacto em CI.

1. **Raiz:** `HISTORICO_TRABALHO_<NOME>.md` ou nome fixo acordado pela equipa (ex.: `HISTORICO_TRABALHO.md`).
2. **Script:** `scripts/update_historico.py` (adaptar `DEFAULT_FILE` / `MARKER_COMMITS` / `SECTION_AUTO` se mudar o nome do ficheiro ou marcadores).
3. **Workflow:** `.github/workflows/historico-ci.yml`
   - **Push `main`:** `python scripts/update_historico.py --write`, commit apenas se houver diff, mensagem com **`[historico-ci]`**, job **ignorado** quando o ultimo commit ja contem esse token (anti-loop).
   - **Pull Request:** `python scripts/update_historico.py --dry-run` apenas **log** (nao grava no PR).
4. **Permissoes:** job que faz push precisa `permissions: contents: write` nesse job.

## Checklist ao abrir um repositorio novo

- [ ] Criar o Markdown inicial na raiz com secao manual e, antes de `## Commits recentes considerados` (ou marcador equivalente), espaco para `## Registro automatico (CI)` (o script pode criar a primeira vez).
- [ ] Copiar e ajustar `scripts/update_historico.py` (nome do ficheiro e marcadores).
- [ ] Copiar `.github/workflows/historico-ci.yml` (branch `main` se for a producao).
- [ ] Garantir que o ficheiro de historico esta **trackeado** pelo git (`git add`).
- [ ] Em Settings - Actions - General, permitir **Workflow permissions: Read and write** (se o org bloquear, pedir excepcao).

## Pagina publica para a equipa (sem dar acesso ao Git a todos)

Objetivo: URL estavel com o **mesmo conteudo** do relatorio (ou subset), **sem** obrigar toda a gente a abrir o GitHub.

Opcoes (da mais simples para mais controlo):

1. **GitHub Pages** (repositorio **publico**): Pages publica o site; leitura do codigo continua publica. Bom para relatorio aberto.
2. **GitHub Pages + repositorio privado** (free/team): Pages de repo privado em **conta pessoal** pode ser publica por predefinicao; em **organizacao** muitas vezes Pages passa a requerer autenticacao ou plano. Validar em **Settings - Pages** e na documentacao actual da org.
3. **Hospedagem estatica** (Netlify, Cloudflare Pages, Vercel): workflow faz deploy de `HISTORICO*.md` convertido para HTML ou publica pasta `public/` com copia do MD; partilha-se so o URL; pode ter **password** / IP allowlist no servico.
4. **Portal interno** (Notion, Confluence, SharePoint): workflow opcional com `curl`/API a publicar o texto de `HISTORICO` para uma pagina; a equipa usa o URL do portal.

Fluxo minimo com Pages no **agenteos** (repo publico): usar `.github/workflows/pages-historico.yml` + `scripts/build_historico_site.py`. Noutros projectos, copiar estes ficheiros e ajustar o nome do `.md` no script de build.

- O SKILL nao fixa hostname; o URL e atribuido pelo GitHub em Settings - Pages.

## Comportamento esperado do agente

- Ao pedir "igual ao agenteos noutro repo": replicar os **tres** artefactos (MD + script + workflow) e listar ajustes obrigatorios (nome do ficheiro, branch, marcadores).
- Ao pedir "partilhar com publico": perguntar se o **codigo** pode ser publico; se nao, recomendar Netlify/Cloudflare com deploy a partir de CI e **sem** expor o repositorio.
- Preferir **linguagem simples** nas entradas manuais; a CI ja acrescenta texto para **nao tecnicos** na secao automatica.

## Anti-padroes

- Nao guardar skills em `~/.cursor/skills-cursor/` (reservado ao Cursor).
- Nao usar caminhos estilo Windows (`\`) nos exemplos de comandos do SKILL; usar `scripts/update_historico.py`.
- Evitar segundo commit automatico em loop: manter sempre o filtro `!contains(github.event.head_commit.message, '[historico-ci]')` no workflow.
