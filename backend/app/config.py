"""Configuración del backend.

Lee el MISMO `.env` de la raíz que el pipeline: una sola fuente de verdad
para secretos y conexión a base de datos (regla del proyecto).
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Raíz del repo = 3 niveles desde este archivo (repo/backend/app/config.py)
REPO_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(REPO_ROOT / ".env")

# Postgres LOCAL (servicio "db" del docker-compose) / en nube: Neon (Fase 11)
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://analizador:devpassword@localhost:5432/analizador",
)
