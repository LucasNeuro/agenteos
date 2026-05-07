# Playbooks da Mari — Mercado Imobiliário (POP)

A app lê **quatro** ficheiros, por ordem fixa, via `src/playbook_loader.py` (`_PLAYBOOK_ACTIVE`):

| Ficheiro | Conteúdo |
|----------|----------|
| `00_mari_persona_global.md` | Tom, identidade Mari, **skills de SDR**, **primeira resposta com pedido de nome**, **raciocínio contextual (anti-repetição de fluxos e UAZ)**, ritmo (linhas), regra do nome, o que evitar |
| `00_mari_mercado_imobiliario_core.md` | POP: objetivo, escopo, classificação, Mem0, telefone/sessão, tool CRM |
| `01_mari_mercado_imobiliario_fluxos.md` | Triagem (incl. arquitetura), fluxos 1–3, padrões, cards, potencial |
| `02_mari_arquitetura_cliente_final.md` | POP Arquitetura: qualificação, FAQ, card, `cliente_projetos`, potencial |

**Editar estes `.md`** para mudar comportamento — sem alterar Python, salvo reactivar outros módulos no loader.

Playbooks antigos (projetos, prestadores, router anterior) estão em **`arquivo/`** e **não** são carregados.

Documentação de produto: `../maria.md`.
