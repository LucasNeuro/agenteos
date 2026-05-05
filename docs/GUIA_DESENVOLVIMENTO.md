# Guia — Agente HUB Obra 10+ (Agno + AgentOS local)

Objetivo: construir por fases, começando por um **agente mínimo** com Agno, servido com **AgentOS em local**, para afinar fluxo e instruções antes de WhatsApp (UAZ API) e deploy.

- Especificação de produto, tom e fluxos: [`maria.md`](./maria.md)
- API WhatsApp (fases posteriores): OpenAPI em `uazapi-openapi-spec (12).yaml`

---

## Fase 0 — Pré-requisitos

- Python **3.10+** (recomendado 3.11 ou 3.12).
- Chave **Mistral** (`MISTRAL_API_KEY`) — o Agno usa o modelo `MistralChat` e lê esta variável por defeito ([doc Mistral](https://docs.agno.com)).
- Este repositório clonado com `docs/` e código em `src/`.

---

## Fase 1 — Ambiente e dependências

Na raiz do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Crie um ficheiro `.env` na raiz (recomendado para testes locais — `python-dotenv` carrega automaticamente em `src/agent_app.py`) ou exporte variáveis no terminal:

```text
MISTRAL_API_KEY=sua_chave_aqui
# AGNO_MODEL=mistral:mistral-large-latest
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=
WEBHOOK_MARIA_LEADS_URL=
```

Copia de [`../.env.example`](../.env.example).

---

## Fase 2 — Agente mínimo (código atual)

O ficheiro [`src/agent_app.py`](../src/agent_app.py) define:

- **Modelo:** string `mistral:...` (por defeito `mistral:mistral-large-latest`).
**Playbooks (POP Mercado Imobiliário):** [`docs/playbooks/`](../docs/playbooks/) — **três** ficheiros ativos (`00_mari_persona_global.md`, `00_mari_mercado_imobiliario_core.md`, `01_mari_mercado_imobiliario_fluxos.md`), carregados por ordem em [`src/playbook_loader.py`](../src/playbook_loader.py). Outros `.md` estão em `docs/playbooks/arquivo/` e não entram no prompt.
- `SqliteDb` em `tmp/agentos.db` (sessões e histórico locais).
- `timezone_identifier` América/São Paulo; histórico alargado para o modelo não repetir nome/e-mail.
- `AgentOS` com `tracing=True` à volta da mesma base.

- **Memória Agno:** só **Mistral**. Usa-se **memória agentica** (`enable_agentic_memory=True`): a Mari tem a ferramenta `update_user_memory` e deve usá‑la quando o utilizador der factos estáveis (nome, preferências, etc.). O painel **Memory** lê `agno_memories` no SQLite (`tmp/agentos.db`). **Sem OpenAI** neste agente.
- **Mem0 (nuvem):** com **`MEM0_API_KEY`** definida, a integração Mem0 **liga-se** (uso típico em produção com WhatsApp). Para desligar: `MARIA_USE_MEM0=0`. O arquivo automático de turnos usa por omissão **`infer=False`** no API Mem0 (mais linhas visíveis no dashboard); `MARIA_MEM0_APPEND_INFER=1` recupera o modo com inferência. Convive com **memória agentica** no Agno (`update_user_memory` + Mem0).

- Tool **`registrar_lead_no_crm`**: grava lead no **Supabase** (aplica [`001_maria_mini_crm.sql`](../supabase/migrations/001_maria_mini_crm.sql) e depois [`002_maria_lead_source_session.sql`](../supabase/migrations/002_maria_lead_source_session.sql) para stubs por sessão) e envia **POST** JSON para `WEBHOOK_MARIA_LEADS_URL` quando definido (stubs automáticos só disparam webhook se `MARIA_AUTO_STUB_WEBHOOK=1`).

**Gravação Supabase:** cada resposta corre `post_log_maria_conversation_turn` (**`maria_sessions`**, **`maria_messages`**). **`maria_leads`:** lead completo via tool **ou** stub automático por sessão (ver `post_ensure_maria_contact_stub_lead`).

**Próximo passo WhatsApp:** orquestrar webhook UAZ → run do agente com `user_id`/`session_id` estáveis (ver Fase 6b no fim deste guia e `src/maria_crm/uazapi_ids.py`).
---

## Fase 3 — Correr o runtime local

Na raiz do projeto:

```powershell
uvicorn src.agent_app:app --reload --host 127.0.0.1 --port 8000
```

A API FastAPI do AgentOS fica em `http://127.0.0.1:8000` (documentação interativa em `/docs` quando ativa).

---

## Fase 4 — Testar com AgentOS (control plane)

1. Com o servidor a correr, abre a **UI do AgentOS** conforme a documentação Agno para apontar o runtime ao teu endpoint local.
2. Valida na conversa:
   - tom cordial, profissional, **sem emojis**;
   - pedido de nome e e-mail (e-mail dispensável se o utilizador resistir);
   - menu das opções 1–6 e tratamento resumido de “Outro”.

Documentação Agno: [What is AgentOS?](https://docs.agno.com/agent-os/introduction) — índice completo: [llms.txt](https://docs.agno.com/llms.txt).

---

## Fase 5 — Afinar fluxo (ainda local)

- Ajusta persona + playbooks POP em `docs/playbooks/` quando o produto mudar (módulos antigos em `arquivo/`).

---

## Fase 6 — Tools

- Tool `POST` com o JSON de lead (§8 de `maria.md`).
- Tool de agenda (apenas com API/calendário real).
- Resposta WhatsApp: implementado em **`POST /webhooks/uazapi`** + UAZ `POST /send/text` ou `/send/menu` (ver Fase 6b).

---

## Fase 6b — UAZAPI ↔ Maria (contrato técnico)

OpenAPI: [`docs/uazapi-openapi-spec (12).yaml`](../docs/uazapi-openapi-spec%20(12).yaml). Código: [`src/maria_crm/uazapi_ids.py`](../src/maria_crm/uazapi_ids.py), [`src/maria_crm/uazapi_webhook.py`](../src/maria_crm/uazapi_webhook.py).

1. **Webhook HTTP** implementado na app FastAPI: **`POST /webhooks/uazapi`**. Na UAZ, em **Escutar eventos**, inclui obrigatoriamente **`messages`** (mensagens novas). Sem isto, o Render não recebe o texto do utilizador. Podes manter **`messages_update`** se precisares; eventos como `chats`, `groups`, etc. são opcionais para a Mari.
2. **URL pública** (ex.: `https://mari-agentos.onrender.com/webhooks/uazapi`). **`excludeMessages`** deve incluir **`wasSentByApi`** para evitar loop com respostas enviadas pela API.
3. **`UAZAPI_BASE_URL`** no Render/.env deve ser **exactamente o “Server URL” da instância** (ex.: `https://smartvenda.uazapi.com`), **não** assumir `free.uazapi.com` se o painel mostrar outro host.
4. **`UAZAPI_TOKEN`** = token da instância (header `token` nas chamadas `/send/text` e `/send/menu`).
5. **`user_id` / `session_id`** no `hub_agent.run`: `wa_<E.164>` estável por contacto (`maria_user_id_from_uaz_message` / `uaz_session_id_for_maria`), alinhado a Mem0 + CRM + `telefone_whatsapp`.
6. **Segurança opcional:** `UAZAPI_WEBHOOK_SECRET` + header **`X-Maria-Webhook-Secret`** no POST do webhook.

Corpo JSON: típico `WebhookEvent` com `event` + `data` (campos **Message**), ou mensagem “flat”. O código aceita **`event: "messages"`** ou **`"message"`**.

Resposta ao WhatsApp: **`POST /send/text`** ou, se a Mari incluir `<<<UAZ_BUTTONS>>>...`, **`POST /send/menu`** com `type: "button"`.

Mem0 e Supabase usam o mesmo `user_id`/`session_id` definidos no `hub_agent.run(...)` dentro do webhook.

---

## Fase 7 — Deploy no Render + WhatsApp (UAZAPI)

**Ordem recomendada:** (1) **Web Service no Render** com `MISTRAL_API_KEY`, `UAZAPI_TOKEN`, CRM/Mem0 conforme precisares; (2) copiar a URL pública `https://…onrender.com/webhooks/uazapi`; (3) na UAZAPI, apontar o webhook para essa URL com `excludeMessages` adequados.

Blueprint opcional: [`render.yaml`](../render.yaml) na raiz do repositório (ajusta `region` / `plan` no painel Render).

### Render (Web Service)
1. **Root:** raiz do repositório; **Runtime** Python — o ficheiro [`runtime.txt`](../runtime.txt) na raiz fixa **3.11.11** (recomendado; evita o Render usar Python 3.14 beta com pacotes ainda instáveis). No painel podes alinhar **PYTHON_VERSION** ao mesmo valor se necessário.
2. **Build:** `pip install -r requirements.txt`
3. **Start:**  
   `uvicorn src.agent_app:app --host 0.0.0.0 --port $PORT`  
   (no Render, `PORT` vem do ambiente.)
4. **Variáveis de ambiente** (mínimo para produção):  
   `MISTRAL_API_KEY`, `UAZAPI_TOKEN`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `MEM0_API_KEY`,  
   `WEBHOOK_MARIA_LEADS_URL` (se usares n8n), e opcionalmente `UAZAPI_BASE_URL`, `UAZAPI_WEBHOOK_SECRET`, `MARIA_MEM0_RECALL_DAYS`, `MARIA_AUTO_STUB_WEBHOOK`, `MARIA_MEM0_APPEND_INFER`.
5. **Persistência:** o `SqliteDb` do Agno usa `tmp/agentos.db` por defeito — em instâncias **efémeras** podes perder sessões ao reiniciar. Para produção séria: migrar o `SqliteDb` para caminho em **Render Disk** ou usar **Postgres** como BD do Agno (ver documentação Agno). Mem0 (nuvem) continua a guardar factos por `user_id` mesmo que o SQLite seja reiniciado.
6. **URL pública HTTPS:** necessária para o **webhook UAZAPI** (`POST /webhooks/uazapi` na mesma app).

### WhatsApp (UAZAPI) após o deploy
1. Webhook UAZ → **`https://<teu-serviço>.onrender.com/webhooks/uazapi`** (eventos de mensagem). Usar `excludeMessages` como na Fase 6b.
2. **`UAZAPI_TOKEN`** da instância igual ao definido no Render (envio `POST /send/text` e `/send/menu`).
3. Botões interativos: a Mari pode incluir o bloco documentado no playbook (`<<<UAZ_BUTTONS>>>` … `<<<END_UAZ_BUTTONS>>>`); o backend chama automaticamente **`POST /send/menu`** com `type: "button"` (máx. 3 opções por mensagem).

---

## Checklist — “Fase atual” (local)

- [ ] `venv` ativo e `pip install -r requirements.txt` sem erros
- [ ] `MISTRAL_API_KEY` definida (`.env` ou ambiente)
- [ ] `uvicorn src.agent_app:app --reload` sobe sem traceback
- [ ] Chat na UI AgentOS com: nome, e-mail recusado, cada opção do menu 1–6
