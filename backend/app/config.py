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

# CORS (Fase 11): dominios autorizados a llamar a la API desde el NAVEGADOR,
# separados por comas. El valor por defecto es de desarrollo; en producción
# Render lo alimenta con los dominios reales (ver render.yaml). El SSR de la
# web sale del servidor y no pasa por CORS en absoluto.
CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]
