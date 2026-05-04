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
**Playbooks em Markdown:** pasta [`docs/playbooks/`](../docs/playbooks/) — ficheiros `00_router.md`, `01_*.md` … são carregados por [`src/playbook_loader.py`](../src/playbook_loader.py) no arranque. Edita os `.md` para afinar fluxos sem mexer em código.
- `SqliteDb` em `tmp/agentos.db` (sessões e histórico locais).
- `timezone_identifier` América/São Paulo; histórico alargado para o modelo não repetir nome/e-mail.
- `AgentOS` com `tracing=True` à volta da mesma base.

- Tool **`registrar_lead_no_crm`**: grava lead no **Supabase** (aplica primeiro [`supabase/migrations/001_maria_mini_crm.sql`](../supabase/migrations/001_maria_mini_crm.sql)) e envia **POST** JSON para `WEBHOOK_MARIA_LEADS_URL` se definido.

**Gravação Supabase:** cada resposta do Agent corre o `post_hook` `post_log_maria_conversation_turn`, que preenche **`maria_sessions`** e **`maria_messages`**. Os **`maria_leads`** só aparecem quando o modelo invoca **`registrar_lead_no_crm`** no fim da qualificação.

**Ainda por fazer:** UAZ WhatsApp, agenda real.

**Fora de escopo nesta fase:** UAZ, calendário, transcrição de áudio.

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

- O playbook em `docs/playbooks/` já cobre os fluxos; ajusta os `.md` quando o produto mudar.

---

## Fase 6 — Tools

- Tool `POST` com o JSON de lead (§8 de `maria.md`).
- Tool de agenda (apenas com API/calendário real).
- Tools UAZ (`/send/text`, `/send/menu`, …) depois de existir webhook de entrada estável.

---

## Fase 7 — WhatsApp e deploy

- Instância UAZ: token, webhook HTTPS para o teu backend.
- Deploy (ex.: Render): serviço com uptime adequado a webhooks; **Postgres** se precisares de persistência forte (evitar SQLite só em disco efémero).

---

## Checklist — “Fase atual” (local)

- [ ] `venv` ativo e `pip install -r requirements.txt` sem erros
- [ ] `MISTRAL_API_KEY` definida (`.env` ou ambiente)
- [ ] `uvicorn src.agent_app:app --reload` sobe sem traceback
- [ ] Chat na UI AgentOS com: nome, e-mail recusado, cada opção do menu 1–6
