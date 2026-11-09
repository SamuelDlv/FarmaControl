# Guia de manutenção — Resolve caminhos a partir do código instalado, sem depender da pasta do terminal.
# Consulte docs/DESENVOLVIMENTO.md para executar as verificações desta camada.
"""Caminhos absolutos, independentes do diretório de execução."""

from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = BACKEND_DIR.parent / "frontend" / "src"
