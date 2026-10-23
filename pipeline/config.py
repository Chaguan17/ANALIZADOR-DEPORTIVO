"""Configuración central del pipeline de ingesta (Fase 2).

Reglas del proyecto aplicadas aquí:
- La API key vive en el `.env` de la raíz del repo (NUNCA subida a GitHub).
- Los JSON crudos se guardan en `pipeline/raw/` (ignorado por .gitignore, auditable).
- Free tier: 10 peticiones/minuto → pacing entre requests con margen de seguridad.
- Liga(s) no incluida(s) en el free tier (Europa League) NO se piden: están deferidas
  a API-Football (ver proyecto/00_CONTEXTO.md).
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Raíz del repo = dos niveles desde este archivo (repo/pipeline/config.py)
REPO_ROOT = Path(__file__).resolve().parents[1]

# Carga el .env de la raíz si existe (en producción se usa GitHub Secrets)
load_dotenv(REPO_ROOT / ".env")

API_BASE_URL = "https://api.football-data.org/v4"
# .strip() en runtime de CI: si el secret se pegó con espacios/newline arrastrados,
# el header Authorization saldría sucio (401 o "Illegal header value").
# NOTA (Fase 15): el token se EXIGE solo al construir el cliente HTTP
# (client.exigir_token), no al importar este módulo: el matcher ESPN
# (pipeline/espn.py) y los auditores offline NO tocan la red y no deben
# necesitar una credencial para importar (los tests unitarios corren "sin
# secretos" en CI, como el resto del repo).
API_TOKEN = os.environ.get("FOOTBALL_API_KEY", "").strip()


def exigir_token() -> str:
    """Devuelve el token o aborta con un error accionable — SOLO al usar la API.

    Fail-fast en el punto de uso: local sin `.env` o cron sin secret
    producen aquí un mensaje claro (antes se exigía al importar config,
    lo que bloqueaba herramientas offline y tests que solo importan
    módulos de transformación).
    """
    if not API_TOKEN:
        raise RuntimeError(
            "FOOTBALL_API_KEY no está definida. Local: copia .env.example → .env y "
            "rellénala (https://www.football-data.org/client/register). "
            "Cron (Fase 12): defínela como secret FOOTBALL_API_KEY en "
            "GitHub → Settings → Secrets and variables → Actions."
        )
    return API_TOKEN

# Temporada por año de INICIO de temporada europea (2026-27). Fijada explícitamente
# para que las descargas sean reproducibles y comparables entre sesiones.
SEASON = 2026

LIGAS_MVP: dict[str, str] = {
    "PD": "Primera División (España)",
    "PL": "Premier League (Inglaterra)",
    "SA": "Serie A (Italia)",
    "BL1": "Bundesliga (Alemania)",
    "CL": "UEFA Champions League",
}

# Carpeta de datos crudos, organizada por liga
RAW_DIR = REPO_ROOT / "pipeline" / "raw"

# Free tier: 10 req/min → dejamos margen (6.2 s entre requests ≈ máx 9.6 req/min)
MIN_INTERVAL = 6.2  # segundos entre requests consecutivos
MAX_RETRIES = 3  # para 429 (límite de ratio) o 5xx, con backoff exponencial
TIMEOUT_S = 30.0  # timeout por petición HTTP
