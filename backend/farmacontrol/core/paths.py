"""Caminhos absolutos, independentes do diretório de execução."""

from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = BACKEND_DIR.parent / "frontend" / "src"
