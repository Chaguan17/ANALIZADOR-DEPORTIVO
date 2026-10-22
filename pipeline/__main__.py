"""CLI del pipeline (Fase 2):  python -m pipeline [--refresh]

- Sin flags: usa caché-first (solo descarga lo que falta).
- --refresh: fuerza re-descargar TODO (consume ~20 peticiones ≈ 2 min).
Exit code: 0 = todo ok · 1 = alguna fuente falló (útil para CI en la Fase 10).
"""

from __future__ import annotations

import argparse
import logging
import sys

from .config import RAW_DIR, SEASON
from .ingest import ingest

logger = logging.getLogger("pipeline")


def _consola_utf8() -> None:
    """Consola Windows (cp1252) + símbolos ✓/✗/nuestras tildes = UTF-8 forzado, sin crash."""
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    _consola_utf8()
    parser = argparse.ArgumentParser(
        description="Ingesta de datos de football-data.org (Fase 2 — ANALIZADOR DEPORTIVO)"
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-descarga los JSON crudos aunque ya existan en pipeline/raw/",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Menos ruido en consola (solo warnings y errores)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )

    logger.info("Iniciando ingesta (temporada %s) — caché-first %s",
                SEASON, "DESHABILADA (refresh)" if args.refresh else "activada")
    resumen, errores = ingest(raw_dir=RAW_DIR, refresh=args.refresh)

    print("\n===== RESUMEN DE INGESTA =====")
    for code, fuentes in resumen.items():
        print(f"\n{code}")
        for fuente, estado in fuentes.items():
            print(f"  {fuente:<13} {estado}")
    print("\n==============================")

    if errores:
        logger.warning("Ingesta completada con %d fuente(s) con error", errores)
        return 1
    logger.info("Ingesta 100%% limpia")
    return 0


if __name__ == "__main__":
    sys.exit(main())
