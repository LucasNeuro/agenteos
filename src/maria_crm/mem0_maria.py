"""
Mem0 (nuvem) — memória persistente por contacto (ex.: WhatsApp).

O Agno ``Mem0Tools`` usa ``user_id=...`` em ``search``/``get_all``, mas o cliente
``mem0ai`` v3 exige ``filters`` com ``user_id``. Esta camada corrige isso e liga
pré/pós-hooks para contexto e arquivo automático de turnos.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Union

from agno.session.agent import AgentSession
from agno.run.agent import RunOutput
from agno.tools.mem0 import Mem0Tools

from mem0.client.main import MemoryClient

from .config import mem0_api_key, mem0_append_infer, mem0_configured, mem0_recall_days
from .channel_context import _session_state_from_hook_kwargs
from .rich_logging import get_maria_logger


def _filters_for_user(user_id: str) -> dict[str, str]:
    return {"user_id": str(user_id)}


def _recall_start_iso(days: int) -> str:
    start = datetime.now(timezone.utc) - timedelta(days=days)
    return start.strftime("%Y-%m-%dT00:00:00.000Z")


def _memory_text(item: dict[str, Any]) -> str:
    return str(item.get("memory") or item.get("text") or item.get("content") or "").strip()


def _flatten_get_all_results(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return list(payload)
    if isinstance(payload, dict):
        inner = payload.get("results")
        if isinstance(inner, list):
            return list(inner)
    return []


class MariaMem0Tools(Mem0Tools):
    """
    Mem0Tools com ``get_all``/``search``/``delete_all`` em filtros v3;
    o ``add`` da API v3 usa ``user_id`` ao nível raiz (como o Agno base) — não misturar com ``filters`` no add.
    """

    def add_memory(
        self,
        session_state,
        content: Union[str, Dict[str, str]],
    ) -> str:
        resolved_user_id = self._get_user_id("add_memory", session_state=session_state)
        if isinstance(resolved_user_id, str) and resolved_user_id.startswith("Error in add_memory:"):
            return resolved_user_id
        try:
            if isinstance(content, dict):
                content = json.dumps(content)
            elif not isinstance(content, str):
                content = str(content)
            messages_list = [{"role": "user", "content": content}]
            result = self.client.add(
                messages_list,
                user_id=str(resolved_user_id),
                infer=self.infer,
            )
            return json.dumps(result)
        except Exception as e:
            from agno.utils.log import log_error

            log_error(f"Error adding memory: {e}")
            return f"Error adding memory: {e}"

    def search_memory(
        self,
        session_state: Dict[str, Any],
        query: str,
    ) -> str:
        resolved_user_id = self._get_user_id("search_memory", session_state=session_state)
        if isinstance(resolved_user_id, str) and resolved_user_id.startswith("Error in search_memory:"):
            return resolved_user_id
        try:
            results = self.client.search(
                query,
                filters=_filters_for_user(resolved_user_id),
                top_k=16,
            )
            if isinstance(results, dict) and "results" in results:
                search_results_list = results.get("results", [])
            elif isinstance(results, list):
                search_results_list = results
            else:
                search_results_list = []
            return json.dumps(search_results_list)
        except Exception as e:
            from agno.utils.log import log_error

            log_error(f"Error searching memory: {e}")
            return f"Error searching memory: {e}"

    def get_all_memories(self, session_state: Dict[str, Any]) -> str:
        resolved_user_id = self._get_user_id("get_all_memories", session_state=session_state)
        if isinstance(resolved_user_id, str) and resolved_user_id.startswith("Error in get_all_memories:"):
            return resolved_user_id
        try:
            days = mem0_recall_days()
            results = self.client.get_all(
                filters=_filters_for_user(resolved_user_id),
                start_date=_recall_start_iso(days),
                page_size=500,
            )
            memories_list = _flatten_get_all_results(results)
            return json.dumps(memories_list)
        except Exception as e:
            from agno.utils.log import log_error

            log_error(f"Error getting all memories: {e}")
            return f"Error getting all memories: {e}"

    def delete_all_memories(self, session_state: Dict[str, Any]) -> str:
        resolved_user_id = self._get_user_id("delete_all_memories", session_state=session_state)
        if isinstance(resolved_user_id, str) and resolved_user_id.startswith("Error in delete_all_memories:"):
            return resolved_user_id
        try:
            self.client.delete_all(filters=_filters_for_user(resolved_user_id))
            return f"Successfully deleted all memories for user_id: {resolved_user_id}."
        except Exception as e:
            from agno.utils.log import log_error

            log_error(f"Error deleting all memories: {e}")
            return f"Error deleting all memories: {e}"


def maria_mem0_load_recent_into_session(session_state: dict[str, Any], user_id: str | None) -> None:
    """
    Preenche ``session_state['maria_mem0_recent']`` com memórias Mem0 dos últimos N dias
    (N = MARIA_MEM0_RECALL_DAYS, default 15) para o utilizador corrente.
    """
    log = get_maria_logger()
    if not mem0_configured():
        return
    uid = user_id or session_state.get("current_user_id")
    if not uid:
        return
    try:
        key = mem0_api_key()
        if not key:
            return
        client = MemoryClient(api_key=key)
        days = mem0_recall_days()
        payload = client.get_all(
            filters=_filters_for_user(str(uid)),
            start_date=_recall_start_iso(days),
            page_size=500,
        )
        rows = _flatten_get_all_results(payload)
        lines: list[str] = []
        for row in rows:
            t = _memory_text(row)
            if t:
                lines.append(f"- {t}")
        session_state["maria_mem0_recent"] = "\n".join(lines[:80]) if lines else "(nenhuma memória Mem0 nesta janela)"
        log.debug(
            "[dim]Maria Mem0[/] contexto carregado · %d factos · user=[cyan]%s[/]",
            min(len(lines), 80),
            str(uid)[:24],
        )
    except Exception as e:  # noqa: BLE001
        log.warning("[yellow]Maria Mem0[/] falha ao carregar contexto — %s", e)
        session_state["maria_mem0_recent"] = "(Mem0 indisponível neste turno)"


def maria_mem0_pre_hook(**kwargs: Any) -> None:
    session_state = _session_state_from_hook_kwargs(kwargs)
    if session_state is None:
        return
    user_id = kwargs.get("user_id")
    session = kwargs.get("session")
    uid = resolve_maria_mem0_user_id(
        hook_user_id=user_id,
        session=session,
        session_state=session_state,
    )
    maria_mem0_load_recent_into_session(session_state, uid)


def resolve_maria_mem0_user_id(
    *,
    hook_user_id: str | None = None,
    run_output: RunOutput | None = None,
    session: AgentSession | None = None,
    session_state: dict[str, Any] | None = None,
) -> str | None:
    """
    Identificador estável para o Mem0 (filtro ``user_id``).

    O AgentOS / playground por vezes não preenche ``user_id``; nesse caso usa-se
    ``session.session_id`` para não perder gravações no painel Mem0.
    """
    ro_state = getattr(run_output, "session_state", None) if run_output else None
    for candidate in (
        hook_user_id,
        getattr(run_output, "user_id", None) if run_output else None,
        session.user_id if session else None,
        (session_state or {}).get("current_user_id"),
        ro_state.get("current_user_id") if isinstance(ro_state, dict) else None,
    ):
        if candidate is not None and str(candidate).strip():
            return str(candidate).strip()
    if session is not None:
        sid = getattr(session, "session_id", None)
        if sid is not None and str(sid).strip():
            return str(sid).strip()
    return None


def _count_mem0_add_results(payload: Any) -> int | None:
    if not isinstance(payload, dict):
        return None
    for key in ("results", "memories", "items", "data"):
        v = payload.get(key)
        if isinstance(v, list):
            return len(v)
    if payload.get("id") or payload.get("memory_id"):
        return 1
    return None


def maria_mem0_post_append_turn(
    run_output: RunOutput,
    session: AgentSession,
    user_id: str | None = None,
    session_state: dict[str, Any] | None = None,
    **kwargs: Any,
) -> None:
    """
    Arquivar turno (utilizador + assistente) no Mem0 para continuidade entre sessões/canal.
    """
    log = get_maria_logger()
    if not mem0_configured():
        return
    st = session_state if isinstance(session_state, dict) else _session_state_from_hook_kwargs(kwargs)
    uid = resolve_maria_mem0_user_id(
        hook_user_id=user_id,
        run_output=run_output,
        session=session,
        session_state=st,
    )
    if not uid:
        log.warning(
            "[yellow]Maria Mem0[/] turno não enviado — falta [cyan]user_id[/] no hook "
            "(confirma que o cliente AgentOS envia [dim]user_id[/] no run)."
        )
        return
    user_text = ""
    if run_output.input is not None:
        user_text = run_output.input.input_content_string() or ""
    assistant_text = ""
    if isinstance(run_output.content, str):
        assistant_text = run_output.content
    elif run_output.content is not None:
        assistant_text = str(run_output.content)
    blob = f"User: {user_text.strip()}\nAssistant: {assistant_text.strip()}".strip()
    if not blob or len(blob) < 4:
        return
    if len(blob) > 12_000:
        blob = blob[:12_000] + "\n…"
    key = mem0_api_key()
    if not key:
        return
    try:
        client = MemoryClient(api_key=key)
        # POST /v3/memories/add/ — entidade em ``user_id`` no corpo; ``filters`` aqui costuma impedir contagem/persistência no dashboard.
        result = client.add(
            [{"role": "user", "content": blob}],
            user_id=str(uid),
            infer=mem0_append_infer(),
        )
        n = _count_mem0_add_results(result)
        log.info(
            "[bold green]Maria Mem0 ✓[/] turno enviado · user=[cyan]%s[/] · "
            "itens_na_resposta_add=%s",
            str(uid)[:48],
            n if n is not None else "?",
        )
        if n == 0:
            log.info(
                "Maria Mem0: resposta add sem lista de itens (infer=%s). "
                "Confirma no dashboard Mem0; com `MARIA_MEM0_APPEND_INFER=1` a extração explícita costuma aparecer como mais factos.",
                mem0_append_infer(),
            )
            log.debug("Maria Mem0 add corpo: %s", json.dumps(result, default=str)[:900])
    except Exception as e:  # noqa: BLE001
        log.warning("[yellow]Maria Mem0[/] falha ao gravar turno — %s", e)
