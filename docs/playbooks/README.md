# Playbooks da Mari — Mercado Imobiliário (POP)

A app lê **três** ficheiros, por ordem fixa, via `src/playbook_loader.py` (`_PLAYBOOK_ACTIVE`):

| Ficheiro | Conteúdo |
|----------|----------|
| `00_mari_persona_global.md` | Tom, identidade Mari, ritmo (linhas), regra do nome, o que evitar |
| `00_mari_mercado_imobiliario_core.md` | POP: objetivo, escopo, classificação, Mem0, telefone/sessão, tool CRM |
| `01_mari_mercado_imobiliario_fluxos.md` | POP: fluxos 1–3 (textos e passos), §10 padrões, §11 cards, §12 potencial, exceções |

**Editar estes `.md`** para mudar comportamento — sem alterar Python, salvo reactivar outros módulos no loader.

Playbooks antigos (projetos, prestadores, router anterior) estão em **`arquivo/`** e **não** são carregados.

Documentação de produto: `../maria.md`.
