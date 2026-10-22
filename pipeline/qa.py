"""QA de los datos crudos (Fase 2) — SIN gastar cuota de API.

Valida que los JSON en pipeline/raw/ parseen y tengan datos sanos:
- partidos: IDs únicos, una sola temporada, estados y rango de fechas,
  y que existan partidos por jugar (insumo de las predicciones).
- clasificacion: posiciones únicas y consecutivas en la tabla TOTAL.
- equipos: IDs y nombres presentes.
- goleadores: hasta 10 (límite del free tier) con goles > 0.

Ejecución:  python -m pipeline.qa   ·  Exit code: 0 ok · 1 con problemas.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .config import LIGAS_MVP, RAW_DIR, SEASON

PARTIDOS_POR_JUGAR = ("SCHEDULED", "TIMED")


def _consola_utf8() -> None:
    """Fuera problemas consola Windows (cp1252): salida en UTF-8, sin crash."""
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def _qa_partidos(p: Path) -> tuple[list[str], list[str]]:
    data = json.loads(p.read_text(encoding="utf-8"))
    partidos = data.get("matches")
    errs, oks = [], []
    if not isinstance(partidos, list) or not partidos:
        return [], ["'matches' vacío o ausente"]

    ids: set[int] = set()
    temporadas: set[str] = set()
    fechas: list[str] = []
    estados: dict[str, int] = {}
    for m in partidos:
        ids.add(m.get("id"))
        s = m.get("season", {})
        temporadas.add(f"{s.get('startDate')}~{s.get('endDate')}")
        fechas.append(str(m.get("utcDate", ""))[:10])
        estados[m.get("status", "?")] = estados.get(m.get("status", "?"), 0) + 1

    if len(ids) != len(partidos):
        errs.append("IDs de partido duplicados en la lista")

    rango = f"{min(fechas)} -> {max(fechas)}" if fechas else "n/a"
    oks.append(f"{len(partidos)} partidos | estados {estados} | fechas {rango} | 1 temporada: {len(temporadas) == 1}")

    por_jugar = sum(v for k, v in estados.items() if k in PARTIDOS_POR_JUGAR)
    if por_jugar == 0:
        errs.append("0 partidos por jugar: ¿temporada terminada?-review")
    else:
        oks.append(f"insumo de predicciones: {por_jugar} partidos futuros (SCHEDULED/TIMED)")
    return oks, errs


def _qa_clasificacion(p: Path) -> tuple[list[str], list[str]]:
    data = json.loads(p.read_text(encoding="utf-8"))
    tablas = data.get("standings", [])
    errs, oks = [], []
    if not tablas:
        return [], ["'standings' vacío o ausente"]
    oks.append(f"{len(tablas)} tablas ({', '.join(t.get('type', '?') for t in tablas)})")

    total = next((t for t in tablas if t.get("type") == "TOTAL"), None)
    if not total:
        return oks, ["no existe la tabla de tipo TOTAL"]
    filas = total.get("table", [])
    if not filas:
        return oks, ["tabla TOTAL sin filas"]

    equipos = [f["team"]["name"] for f in filas]
    posiciones = [f.get("position") for f in filas]

    # Regla general (cubre ligas domésticas y fase de liga de la Champions):
    # - posiciones NO-DECRECIENTES (empates a puntos → misma posición repetida,
    #   comportamiento real de la API p/ ej. CL: 20, 20 · 29, 29)
    # - equipos únicos (sin repetición)
    # - ninguna posición mayor que el nº de filas
    no_decreciente = all(
        a <= b for a, b in zip(posiciones, posiciones[1:])
    )
    equipos_unicos = len(set(equipos)) == len(equipos)
    sin_fuera_rango = all(p is not None and 1 <= p <= len(filas) for p in posiciones)
    if not no_decreciente:
        errs.append(f"posiciones no ordenadas: {posiciones}")
    if not equipos_unicos:
        errs.append("equipos repetidos en la tabla TOTAL")
    if not sin_fuera_rango:
        errs.append("posiciones fuera de rango")

    nota_ties = " (con empates por puntos)" if len(set(posiciones)) < len(posiciones) else ""
    oks.append(f"tabla TOTAL con {len(filas)} filas válidas{nota_ties}")
    return oks, errs


def _qa_equipos(p: Path) -> tuple[list[str], list[str]]:
    data = json.loads(p.read_text(encoding="utf-8"))
    equipos = data.get("teams", [])
    if not equipos:
        return [], ["'teams' vacío o ausente"]
    sin_id = [e for e in equipos if not e.get("id")]
    sin_nombre = [e for e in equipos if not e.get("name")]
    errs = []
    if sin_id:
        errs.append(f"{len(sin_id)} equipos sin id")
    if sin_nombre:
        errs.append(f"{len(sin_nombre)} equipos sin nombre")
    return [f"{len(equipos)} equipos"], errs


def _qa_goleadores(p: Path) -> tuple[list[str], list[str]]:
    data = json.loads(p.read_text(encoding="utf-8"))
    goleadores = data.get("scorers", [])
    if not goleadores:
        return [], ["'scorers' vacío o ausente"]
    errs = []
    goles_cero = [g for g in goleadores if (g.get("goals") or 0) <= 0]
    if goles_cero:
        errs.append(f"{len(goles_cero)} goleadores con 0 goles")
    nota = "límite free tier: máx 10 por liga" if len(goleadores) <= 10 else ""
    return [f"{len(goleadores)} goleadores {nota}".strip()], errs


CHECKS = {
    "partidos": (f"partidos_{SEASON}.json", _qa_partidos),
    "clasificacion": (f"clasificacion_{SEASON}.json", _qa_clasificacion),
    "equipos": (f"equipos_{SEASON}.json", _qa_equipos),
    "goleadores": (f"goleadores_{SEASON}.json", _qa_goleadores),
}


def main() -> int:
    _consola_utf8()
    problemas = 0
    faltantes = 0
    print(f"QA de datos crudos (temporada {SEASON}) — {RAW_DIR}\n")
    for code, nombre_liga in LIGAS_MVP.items():
        print(f"[{code}] {nombre_liga}")
        for fuente, (archivo, checker) in CHECKS.items():
            p = RAW_DIR / code / archivo
            if not p.exists():
                print(f"  ✗ {fuente:<14} FALTA el archivo {p}")
                faltantes += 1
                continue
            try:
                oks, errs = checker(p)
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                print(f"  ✗ {fuente:<14} JSON/estructura inválida: {e!r}")
                problemas += 1
                continue
            for line in oks:
                print(f"  ✓ {fuente:<14} {line}")
            for err in errs:
                problemas += 1
                print(f"  ✗ {fuente:<14} {err}")
        print()

    print(f"Resultados: {faltantes} archivo(s) faltante(s) · {problemas} problema(s)")
    return 1 if (faltantes or problemas) else 0


if __name__ == "__main__":
    sys.exit(main())
