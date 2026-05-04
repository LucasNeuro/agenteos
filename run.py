"""
Arranca o AgentOS local (Maria / HUB Obra 10+).

Na raiz do projeto:

  python run.py

Variáveis opcionais: HOST (padrão 127.0.0.1), PORT (padrão 8000), RELOAD (1 ou 0, padrão 1).
"""

from __future__ import annotations

import os

import uvicorn

if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "1") not in ("0", "false", "False")

    uvicorn.run(
        "src.agent_app:app",
        host=host,
        port=port,
        reload=reload,
    )
