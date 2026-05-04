"""Console Rich dedicado ao mini CRM Maria (legível no terminal)."""

from __future__ import annotations

import logging

from rich.console import Console
from rich.logging import RichHandler

_console = Console(stderr=True)
_logger: logging.Logger | None = None


def setup_maria_rich_logging(level: int = logging.INFO) -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger
    lg = logging.getLogger("maria_crm")
    lg.setLevel(level)
    lg.handlers.clear()
    h = RichHandler(
        console=_console,
        rich_tracebacks=True,
        show_time=True,
        show_path=False,
        markup=True,
        omit_repeated_times=False,
    )
    h.setLevel(level)
    lg.addHandler(h)
    lg.propagate = False
    _logger = lg
    return lg


def get_maria_logger() -> logging.Logger:
    if _logger is None:
        return setup_maria_rich_logging()
    return _logger
