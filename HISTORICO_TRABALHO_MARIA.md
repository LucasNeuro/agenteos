# Historico de Trabalho - Mari (AgentOS + WhatsApp/UAZAPI)

Ultima atualizacao: 2026-05-06 (UTC-3) — hardening WhatsApp + CRM + RAG

## Em linguagem simples (evolucao para leigos)

Resumo para quem nao programa: o que mudou em relacao a **Mari**, ao **WhatsApp** e ao **projeto**. Acrescentar uma subsecção `### ...` por **dia** em que houver algo relevante (exemplos abaixo: 4 e 5 de maio de 2026).

### Segunda-feira, 4 de maio de 2026

- Foi criado o **repositorio** do projeto no GitHub com a primeira versao do codigo.
- Comecou a **ligacao com a Mem0**: servico de memoria para a Mari **lembrar** informacoes do cliente ao longo do tempo (entre conversas).
- A **estrutura da documentacao** do negocio (**mercado imobiliario / Obra 10+**) e guias de ambiente foram organizadas; preparou-se a **integracao com o WhatsApp** via provedor **UAZAPI** (mensagens a entrar e sair pelo numero da empresa).

### Terca-feira, 5 de maio de 2026

- **WhatsApp:** o sistema passou a tratar melhor os **avisos** que chegam da UAZAPI (formatos diferentes do webhook) para a Mari **nao deixar de responder**.
- **Botoes e listas:** quando a pergunta e de escolha (por exemplo: buscar imovel, anunciar, corretor), a Mari pode enviar **botoes** ou **menu em lista** no WhatsApp, e nao so texto corrido; foram reforcadas as **instrucoes internas** (playbooks) para isso acontecer com mais constancia.
- **Citacao da mensagem:** explicou-se que, se a resposta aparece como "resposta citada" no telemovel, isso vem de uma **opcao de configuracao** no servidor (Render); desligando essa opcao, a mensagem volta ao formato de **bolha normal**.
- **Memoria e registo:** melhorias na forma como o **telefone** do WhatsApp e a **memoria Mem0** entram na conversa, e afinacoes nos **logs** para perceber se a Mari enviou texto, botoes ou lista.
- **Relatorio no GitHub:** experimentou-se atualizar este historico e pagina publica **por automatismo**; **nao ficou em uso.** O acordo atual e **comunicar o andamento no grupo manualmente**. O detalhe tecnico do dia 5 continua abaixo para a equipa.
- **Novo modulo no atendimento:** a Mari passou a ter instrucoes para **projeto de arquitetura, interiores e reforma com projeto** (POP HUB Obra 10+), alem do mercado imobiliario. Na triagem inicial, o cliente pode escolher **buscar imovel, anunciar, ser corretor/imobiliaria ou projeto de arquitetura/interiores**; no ultimo caso ela qualifica com **tamanho**, **prazo** e **cidade/bairro** e regista o lead como **`cliente_projetos`** no CRM para os arquitetos homologados darem seguimento.
- **Organizacao do repositorio:** foram removidas pastas que entraram por engano (`admin-ui` com `node_modules`, `scripts` e `.github`) para manter o projeto focado no runtime Python da Mari.

### Quarta-feira, 6 de maio de 2026

- **WhatsApp mais confiavel:** o webhook da UAZAPI ficou mais resistente a mensagens duplicadas e a payloads sem `messageid`, reduzindo risco de resposta repetida.
- **CRM mais consistente:** reforcado o vinculo entre conversa e lead (sessao/contacto), com melhor dedupe e melhor leitura operacional.
- **RAG mais estavel:** upload/reindex com controlo para evitar jobs concorrentes e novo endpoint de validacao para checar estado da base de conhecimento.
- **Operacao e monitorizacao:** adicionados endpoints administrativos protegidos para validar saude do CRM e do RAG sem precisar entrar no codigo.

## Objetivo deste arquivo
- Este ficheiro e o **relatorio oficial** do trabalho na **agente Mari** (codigo, playbooks, integracao WhatsApp, CRM, memoria, deploy). Trata-se tambem do registo que a equipa pode partilhar com **nao tecnicos**, quando fizer sentido.
- **Regra:** apos cada entrega ou correcao relevante na Mari, **actualizar aqui** no mesmo dia (ou no proximo dia util): subir a linha **Ultima atualizacao**, acrescentar bullets em **Em linguagem simples** se houver audiencia leiga, e o pormenor tecnico na seccao do **dia**.
- **Em producao (Render):** o mesmo ficheiro e servido em HTML nas rotas **`/relatorio`** ou **`/relatorios`** (mesmo conteudo; a segunda e alias por engano comum) da app (ex.: `https://<servico>.onrender.com/relatorio`). A pagina le o Markdown no servidor a cada visita; **apos editar este ficheiro e fazer deploy**, o site mostra a versao nova.
- Registrar o que foi feito por dia e horario.
- Manter um diario tecnico curto de evolucao do projeto.
- Facilitar acompanhamento por conversa, codigo e commits.

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

### 17:30-18:30 (aprox.) - Playbook Arquitetura (cliente final) e triagem em 4 vias
- Novo ficheiro **`docs/playbooks/02_mari_arquitetura_cliente_final.md`**: fluxo POP (saudação, nome, obrigatorio agradecimento apos nome, qualificacao com botoes UAZ para faixa de m² e prazo, localizacao livre, encaminhamento aos arquitetos, FAQ curto, card, criterios ALTO/MEDIO/BAIXO, follow-up unico, proibicoes).
- **`src/playbook_loader.py`**: prompt da Mari passa a juntar **quatro** playbooks (persona, nucleo, fluxos imobiliario, **arquitetura**); guarda tecnica da triagem com **quarta opcao** `fluxo_arquitetura`.
- **`docs/playbooks/00_mari_mercado_imobiliario_core.md`**: ambito e classificacao incluem arquitetura; tabela de campos para **`lead_kind` = `cliente_projetos`**.
- **`docs/playbooks/01_mari_mercado_imobiliario_fluxos.md`**: regra **0** = arquitetura antes dos fluxos 1-3; exemplos **`UAZ_LIST`** / **`UAZ_BUTTONS`** com quatro opcoes (lista quando >3 botoes).
- **`docs/playbooks/00_mari_persona_global.md`**, **`docs/playbooks/README.md`**, **`docs/GUIA_DESENVOLVIMENTO.md`**: referencia ao quarto playbook.
- **`src/maria_crm/lead_tool.py`**: docstring com campos tipicos de **`cliente_projetos`** (alinha com `persist_lead_and_webhook` e tabela `maria_lead_cliente_projetos`).
- Nota: o ficheiro `01_mari_mercado_imobiliario_fluxos.md` tinha estado apagado no working tree local; foi **restaurado a partir do git** para o loader nao falhar.

### 22:45-23:00 (aprox.) - Limpeza estrutural do repositorio
- Remocao da pasta **`admin-ui/`** (incluindo `node_modules/` e `dist/`) que nao fazia parte do backend da Mari.
- Remocao da pasta **`scripts/`**.
- Remocao da pasta **`.github/`**.
- Objetivo: reduzir ruido no projeto e evitar manutencao de artefactos fora do escopo do runtime Python.

---

## 2026-05-06 (Quarta-feira)

### 08:15-08:40 (aprox.) - WhatsApp/UAZAPI hardening (dedupe + resiliencia)
- **`src/maria_crm/uazapi_dedupe.py`**:
  - dedupe expandido para chave de evento (nao so `messageid`);
  - suporte a prefixos `mid:` e `fp:` para idempotencia mais robusta.
- **`src/maria_crm/uazapi_webhook.py`**:
  - chave de dedupe por `messageid` ou fingerprint (`sha1`) quando o id nao vem no payload;
  - tratamento de excecao global no webhook para resposta controlada (`internal_webhook_error`) e melhor observabilidade em log.
- Resultado esperado: menor risco de processar duplicado e melhor comportamento em payloads heterogeneos da UAZAPI.

### 08:40-09:05 (aprox.) - CRM consistente entre sessao e lead
- **`src/maria_crm/lead_service.py`**:
  - resolucao de `session_id` interno a partir de `source_external_session_id`;
  - `persist_lead_and_webhook(...)` passa a aceitar `source_external_session_id` e tenta vincular o lead a sessao;
  - fallback de insercao quando a coluna `source_external_session_id` (migracao 002) ainda nao existe no banco;
  - `ensure_auto_contact_stub_lead(...)` tambem tenta gravar `session_id` quando possivel.
- **`src/maria_crm/lead_tool.py`**: novo argumento opcional `source_external_session_id`.
- **`src/maria_crm/lead_property_link_hook.py`**:
  - apos `registrar_lead_no_crm`, tenta vincular lead <-> sessao externa;
  - mantida ligacao de imoveis em rascunho ao lead.
- Resultado esperado: trilho de dados mais coerente para auditoria, BI e operacao comercial.

### 09:05-09:30 (aprox.) - RAG operacional estavel (upload + reindex + validacao)
- **`src/maria_crm/ingest_maria_knowledge.py`**:
  - adicionado modo single-flight (`run_maria_knowledge_ingest_singleflight`) para impedir ingest concorrente.
- **`src/maria_crm/rag_ingest_webhook.py`** e **`src/maria_crm/rag_admin_ui.py`**:
  - passam a usar o single-flight (se ja houver job a correr, o novo trigger e ignorado com log).
- **`src/maria_crm/knowledge_maria.py`**:
  - novo snapshot de saude (`maria_rag_health_snapshot`) com:
    - estado de configuracao;
    - contagem das tabelas `ai.maria_knowledge_contents` e `ai.maria_knowledge_vectors`;
    - validacao opcional por query textual.
- **`src/maria_crm/rag_admin_ui.py`**:
  - novo endpoint `GET /admin/rag/validate?t=<secret>&q=<texto>&limit=<n>`.
- **`.env.example`**:
  - documentacao atualizada para endpoint de validacao RAG e relatorio operacional do CRM.

### 09:30-09:40 (aprox.) - Endpoint de relatorio operacional CRM
- Novo ficheiro **`src/maria_crm/crm_ops_report.py`**.
- Rota protegida por segredo: **`GET /admin/crm/report?t=<secret>&hours=24`**.
- Ativacao por env: **`MARIA_CRM_REPORT_SECRET`**.
- Metricas expostas (JSON): sessoes, mensagens (user/assistant), leads, stubs automaticos e erros de webhook na janela.
- **`src/agent_app.py`** atualizado para incluir o router apenas quando o segredo estiver definido.

### 09:40-09:45 (aprox.) - Validacao de integridade
- Execucao de `python -m compileall src` sem erros.
- Verificacao de lints nos ficheiros alterados sem novos erros reportados.

---

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
