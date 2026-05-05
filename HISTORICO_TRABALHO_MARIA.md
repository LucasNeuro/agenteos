# Historico de Trabalho - Mari (AgentOS + WhatsApp/UAZAPI)

Ultima atualizacao: 2026-05-05 17:37 (UTC-3)

## Objetivo deste arquivo
- Registrar o que foi feito por dia e horario.
- Manter um diario tecnico curto de evolucao do projeto.
- Facilitar acompanhamento por conversa, codigo e commits.

## Como atualizar (padrao)
- Abrir um bloco novo por data: `## YYYY-MM-DD (Dia)`.
- Dentro do dia, adicionar entradas por horario: `### HH:MM`.
- Em cada entrada, registrar:
  - contexto/problema;
  - mudancas feitas;
  - validacao realizada;
  - proximo passo.
- A secao **Registro automatico (CI)** e preenchida pelo **GitHub Actions** a cada push na branch **main** (linguagem simples + lista de ficheiros). Em Pull Requests o mesmo texto aparece so no log do CI (preview), sem alterar o ficheiro no PR.
- **Leitura publica no browser (amigavel para nao tecnicos):** o workflow `Pages - Historico publico` gera um site a partir deste ficheiro. Apos a primeira configuracao em **Settings - Pages** (source: **GitHub Actions**), o URL aparece nessa pagina (tipicamente `https://<don>.github.io/<repo>/`).

---

## 2026-05-05 (Terca-feira)

### 15:20-15:35 - Diagnostico do WhatsApp "respondendo como citacao"
- Causa confirmada: envio com `replyid` ativo.
- Verificado que o comportamento depende da env `MARIA_UAZAPI_REPLY_TO_USER_MESSAGE`.
- Orientacao para Render: usar `0` (ou remover variavel) para resposta em bolha normal.

### 15:35-15:55 - Interativos UAZ (botao/lista) com fallback
- Parser reforcado em `src/maria_crm/uazapi_parse.py`.
- Mantido suporte explicito:
  - `<<<UAZ_BUTTONS>>>...<<<END_UAZ_BUTTONS>>>`
  - `<<<UAZ_LIST>>>...<<<END_UAZ_LIST>>>`
- Adicionado fallback para listas markdown/bullets/numero:
  - 2-3 opcoes no final da resposta -> `button`;
  - 4+ opcoes -> `list`.

### 15:55-16:10 - Observabilidade para debug de envio
- Log tecnico incluido no webhook para indicar o resultado do parse:
  - `kind=text|button|list`
  - quantidade de botoes/lista
- Arquivo: `src/maria_crm/uazapi_webhook.py`.

### 16:10-16:30 - Correcao para caso real do print (sem bloco explicito)
- Problema observado: Mari perguntava triagem sem listar opcoes em linhas, entao nao virava botao.
- Solucao: fallback por intencao/pergunta em `uazapi_parse.py`:
  - triagem (buscar/anunciar/corretor/parceria) -> botoes fixos;
  - vender/alugar -> botoes;
  - cadastrar imovel/parceria -> botoes.

### 16:30-16:45 - Prompt/playbooks mais firmes
- Ajustes em:
  - `docs/playbooks/00_mari_mercado_imobiliario_core.md`
  - `docs/playbooks/01_mari_mercado_imobiliario_fluxos.md`
  - `src/playbook_loader.py`
- Regra atual: nos pontos de decisao, o formato com `UAZ_BUTTONS` passou a ser obrigatorio.
- Incluido guard tecnico em runtime para reforcar padrao de resposta.

### 16:45-17:09 - Validacao funcional e alinhamento de memoria
- Testes locais de parser executados com casos de triagem, proprietario e parceria.
- Confirmado funcionamento de botoes no fluxo inicial (print com botoes recebido).
- Esclarecido funcionamento de contexto rico:
  - telefone vindo de `wa_<numero>` via webhook/session state;
  - e-mail/nome podendo vir de historico + Mem0 (`MARIA_USE_MEM0=1`).
- Decisao do projeto: manter contexto o mais rico possivel.

---

## Registro automatico (CI)

Esta secao e gerada automaticamente pelo GitHub Actions. Cada entrada resume **o que mudou no codigo** em linguagem simples. Para testes no Render (botoes, logs WhatsApp), continue a acrescentar notas manualmente na secao do dia acima.


### 2026-05-05 17:37 (UTC-3) - Atividade no repositorio

- **Para nao tecnicos:** Novo codigo foi enviado (push) para o repositorio. Isto significa que ha alteracoes guardadas no historico do projeto.
- **Branch:** `main`
- **Commit:** `a536fa7` (a536fa723d15...) - Merge branch 'main' of https://github.com/LucasNeuro/agenteos
- **Quem:** LucasNeuro
- **Detalhe tecnico (CI):** https://github.com/LucasNeuro/agenteos/actions/runs/25400940520
- **Ficheiros alterados neste envio:**
  - `HISTORICO_TRABALHO_MARIA.md`


### 2026-05-05 17:23 (UTC-3) - Atividade no repositorio

- **Para nao tecnicos:** Novo codigo foi enviado (push) para o repositorio. Isto significa que ha alteracoes guardadas no historico do projeto.
- **Branch:** `main`
- **Commit:** `1f61082` (1f6108238fe0...) - Add automated update for HISTORICO_TRABALHO_MARIA.md and CI workflow
- **Quem:** LucasNeuro
- **Detalhe tecnico (CI):** https://github.com/LucasNeuro/agenteos/actions/runs/25400278960
- **Ficheiros alterados neste envio:**
  - `.github/workflows/historico-ci.yml`
  - `HISTORICO_TRABALHO_MARIA.md`
  - `scripts/update_historico.py`

## Commits recentes considerados
- `1006ca4` - Enhance WhatsApp integration with mandatory button inclusion in decision flows
- `c473a9e` - Implement enhanced parsing for generic options in UAZAPI
- `e11fa9c` - Enhance UAZAPI integration with support for interactive lists and improved parsing
- `85c5ce7` - Enhance documentation and configuration for WhatsApp integration and Mem0 functionality
- `21ba92a` - Enhance uazapi_webhook.py with improved payload handling and event extraction
- `5b5e5e1` - Update agent_app.py to enhance Mem0 integration logging
- `681426f` - Refactor MariaMem0Tools for v3 API compatibility and improve logging
- `e321352` - Enhance UAZAPI and Mem0 integration with improved payload handling and user ID management
- `401f696` - Add Python version environment variable and clean up agent_app.py
- `555804b` - Remove outdated playbooks for client interactions and service providers
- `6de1015` - Update environment configuration and documentation for UAZAPI integration
- `5ecf242` - Enhance project structure and documentation for Mercado Imobiliario
- `37466f1` - Add Mem0 integration for persistent memory management
- `2b841de` - first commit

---

## Proximo update sugerido
- A cada novo teste no Render, incluir uma entrada com:
  - horario do teste;
  - resultado (`text/button/list`);
  - print/log associado;
  - acao tomada.
