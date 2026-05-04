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

from .config import mem0_api_key, mem0_configured, mem0_recall_days
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
    Idêntico ao Mem0Tools, mas compatível com MemoryClient v3 (filters em vez de user_id solto).
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
                filters=_filters_for_user(resolved_user_id),
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


def maria_mem0_pre_hook(
    *,
    session_state: dict[str, Any],
    user_id: str | None = None,
    **kwargs: Any,
) -> None:
    maria_mem0_load_recent_into_session(session_state, user_id)


def maria_mem0_post_append_turn(
    run_output: RunOutput,
    session: AgentSession,
    **kwargs: Any,
) -> None:
    """
    Arquivar turno (utilizador + assistente) no Mem0 para continuidade entre sessões/canal.
    """
    log = get_maria_logger()
    if not mem0_configured():
        return
    uid = run_output.user_id or (session.user_id if session else None)
    if not uid:
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
        client.add(
            [{"role": "user", "content": blob}],
            filters=_filters_for_user(str(uid)),
            infer=True,
        )
        log.debug("[dim]Maria Mem0[/] turno gravado · user=[cyan]%s[/]", str(uid)[:24])
    except Exception as e:  # noqa: BLE001
        log.warning("[yellow]Maria Mem0[/] falha ao gravar turno — %s", e)
