# Maria / HUB — referência de configuração (runtime)

Todas as opções abaixo vêm de variáveis de ambiente (ficheiro `.env` ou painel do host).  
Os **padrões** estão definidos em `src/maria_crm/config.py` (e em `agent_app.py` onde indicado).

---

## Memória (Mem0)

| Variável | Padrão | Notas |
|----------|--------|--------|
| `MEM0_API_KEY` | — | Se definida e `MARIA_USE_MEM0` não for `0`, a Mari usa Mem0 na nuvem. |
| `MARIA_USE_MEM0` | ligado com chave | `0` / `false` / `off` desliga mesmo com chave. |
| `MARIA_MEM0_RECALL_DAYS` | `15` | Dias de histórico Mem0 carregados no contexto (1–90). |
| `MARIA_MEM0_APPEND_INFER` | desligado | `1` ativa inferência ao arquivar turnos no Mem0. |

---

## WhatsApp — debounce de texto («mensagens picadas»)

| Variável | Padrão (código) | Notas |
|----------|------------------|--------|
| `MARIA_TEXT_DEBOUNCE_SEC` | `3.15` | Segundos **sem nova bolha** antes de chamar a IA (por chat). `0` = cada mensagem responde na hora. Máx. 15. |
| `MARIA_TEXT_DEBOUNCE_TAIL_SEC` | `0.55` | **Cauda:** após esse silêncio, o servidor espera mais estes segundos **antes** de fechar o buffer — ajuda quando a segunda bolha (ex.: bairro) chega com pequeno atraso de rede. `0` = desligado. Máx. 2,5. |
| `MARIA_TEXT_DEBOUNCE_SHORT_SEC` | `0.55` | Só para **um** fragmento muito curto que **não** «pareça» dado de imóvel (saudação, etc.): limite inferior ao debounce longo. |
| `MARIA_TEXT_DEBOUNCE_SHORT_CHARS` | `40` | Tamanho máximo do único fragmento para poder usar o caminho «curto». |

A heurística «parece dado» (cidade, m², preço, **palavra única ≥ 4 letras** tipo bairro, …) está em `maria_text_fragment_prefers_full_debounce` em `uazapi_ids.py`.

---

## WhatsApp — lote de fotos (só imagem)

| Variável | Padrão | Notas |
|----------|--------|--------|
| `MARIA_MEDIA_BATCH_FLUSH_SEC` | `3.5` | Após a última foto só-imagem, espera N s e manda **um** turno agregado. `0` = só quando há texto. |

Outros: `MARIA_UAZAPI_*`, `UAZAPI_TOKEN`, `UAZAPI_BASE_URL` — ver `.env.example`.

---

## Imóvel — ingestão, visão, auto-enriquecimento

| Variável | Padrão | Notas |
|----------|--------|--------|
| `MARIA_PROPERTY_INGEST_ENABLED` | `1` | Desliga ingestão de mídia CRM com `0` / `false`. |
| `MARIA_VISION_ENABLED` | `1` | Análise de imagem (precisa `MISTRAL_API_KEY`). |
| `MARIA_VISION_MODEL` | `pixtral-12b-2409` | Modelo visão Mistral. |
| `MARIA_IMOVEL_STORAGE_BUCKET` | `maria-imoveis` | Bucket Supabase Storage. |
| `MARIA_IMOVEL_AUTO_ENRICH_ENABLED` | ligado se **só** CRM | Segundo plano: `gravar_avaliacao_imovel_rascunho`; com `SERP_API_KEY` pode usar Serp; sem Serp = só visão/contexto. `0` desliga. |
| `MARIA_IMOVEL_AUTO_ENRICH_COOLDOWN_SEC` | `300` | Mínimo entre corridas por mesmo `imovel_id` (60–86400 no código). |
| `SERP_API_KEY` | — | Pesquisa Google via Agno (pacote `google-search-results`). **Opcional** para auto-enrich: sem ela ainda se grava pré-avaliação (visão + texto). |

**Se a tabela `maria_imovel_studio_assessments` ficar vazia:** (1) confirma `SUPABASE_SERVICE_ROLE_KEY` no servidor (**não** uses a chave `anon` neste fluxo); (2) o auto-enrich só corre após **foto aceite** como imóvel e existir `maria_rascunho_imovel_id` — envia pelo menos uma foto válida e espera a Mari responder; (3) vê os logs `[cyan]Auto-enrich imóvel[/]` e avisos HTTP ao gravar.

---

## RAG, tracing, relatórios

Resumo: `MARIA_KNOWLEDGE_ENABLED`, `MARIA_DATABASE_URL`, `AGENTOS_TRACING`, `MARIA_HISTORICO_*`, etc. — detalhe em `.env.example` e comentários em `config.py`.

---

## Onde mudar sem «espalhar» defaults

1. **Produção:** define variáveis no painel (Render, Docker, etc.).  
2. **Local:** `.env` na raiz do repo (não commitar segredos).  
3. **Código:** só altere defaults em `src/maria_crm/config.py` se quiseres novo comportamento para quem **não** define a env.
