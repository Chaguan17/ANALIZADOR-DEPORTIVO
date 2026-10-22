"""Orquestador de la ingesta (Fase 2 del plano maestro).

Para cada liga del MVP descarga 4 fuentes en JSON crudo:
  · matches     → todos los partidos de la temporada (fija el campo `season`)
  · standings   → clasificación actual
  · teams       → equipos de la competición
  · scorers     → goleadores de la competición

Todo queda bajo `pipeline/raw/{CODIGO_LIGA}/`, formato:
  pipeline/raw/PD/partidos_2026.json

Con caché-first: si el archivo ya existe, no se gasta cuota de la API.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import httpx

from .client import FootballDataClient
from .config import SEASON

logger = logging.getLogger("pipeline")


@dataclass(frozen=True)
class Fuente:
    """Una fuente de datos de una competición."""

    endpoint: str  # sub-ruta de la API (sin liga ni query)
    archivo: str   # nombre de archivo (sin extensión ni temporada)


FUENTES: tuple[Fuente, ...] = (
    Fuente(endpoint="matches", archivo="partidos"),
    Fuente(endpoint="standings", archivo="clasificacion"),
    Fuente(endpoint="teams", archivo="equipos"),
    Fuente(endpoint="scorers", archivo="goleadores"),
)


def _resumen_counts(endpoint: str, data: dict) -> str:
    """Resumen legible de la fuente descargada, para el log final."""
    if endpoint == "matches":
        return f"{data.get('count', len(data.get('matches', [])))} partidos"
    if endpoint == "standings":
        return f"{len(data.get('standings', []))} tablas de posiciones"
    if endpoint == "teams":
        return f"{len(data.get('teams', []))} equipos"
    if endpoint == "scorers":
        return f"{len(data.get('scorers', []))} goleadores"
    return "ok"


def ingest_league(
    code: str,
    client: FootballDataClient,
    raw_dir: Path,
    refresh: bool = False,
) -> dict[str, str]:
    """Descarga las 4 fuentes de UNA liga. Devuelve resumen por fuente."""
    lig_dir = raw_dir / code
    resultado: dict[str, str] = {}
    for fuente in FUENTES:
        path = f"/competitions/{code}/{fuente.endpoint}"
        # Solo `matches` admite/permite fijar temporada explícita (reproducible);
        # standings/teams/scorers devuelven la temporada actual.
        params: dict | None = {"season": SEASON} if fuente.endpoint == "matches" else None
        save_path = lig_dir / f"{fuente.archivo}_{SEASON}.json"
        nombre = f"{fuente.archivo}"
        try:
            data = client.get_cached(path, save_path, params=params, refresh=refresh)
            resultado[nombre] = _resumen_counts(fuente.endpoint, data)
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            # Si la API rechazó el filtro de temporada, reintenta sin `season`.
            if status == 400 and params:
                logger.warning(
                    "%s/%s rechazó season=%d → reintentando sin filtro de temporada",
                    code, fuente.endpoint, SEASON,
                )
                try:
                    data = client.get_cached(path, save_path, params=None, refresh=refresh)
                    resultado[nombre] = _resumen_counts(fuente.endpoint, data)
                    continue
                except httpx.HTTPStatusError as error2:
                    resultado[nombre] = f"ERROR HTTP {error2.response.status_code}"
                    continue
            resultado[nombre] = f"ERROR HTTP {status}"
    return resultado


def ingest(raw_dir: Path, refresh: bool = False) -> tuple[dict[str, dict[str, str]], int]:
    """Ingesta completa de las ligas del MVP.

    Devuelve (resumen, errores): resumen por liga/fuente y nº de fuentes con error.
    """
    from .config import LIGAS_MVP  # import tardío: evita import cycle en __main__

    resumen: dict[str, dict[str, str]] = {}
    errores = 0
    client = FootballDataClient(raw_dir=raw_dir)
    try:
        for code, nombre_liga in LIGAS_MVP.items():
            logger.info("──── LIGA %s · %s", code, nombre_liga)
            resultado = ingest_league(code, client, raw_dir, refresh)
            for fuente, estado in resultado.items():
                if estado.startswith("ERROR"):
                    errores += 1
                    logger.warning("  ✗ %-13s %s", fuente, estado)
                else:
                    logger.info("  ✓ %-13s %s", fuente, estado)
            resumen[code] = resultado
    finally:
        client.close()
    return resumen, errores
