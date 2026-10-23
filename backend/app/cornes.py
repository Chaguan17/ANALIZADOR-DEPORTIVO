"""Modelo de CORNES por partido — Poisson con tasa encogida (Fase 16).

Qué predice: el TOTAL de cornes del partido (saques de esquina a favor de
cada equipo, la unidad del mercado over/under de cornes) con dos líneas
FIJAS del proyecto: 9.5 y 11.5. Fuente: `wonCorners` del boxscore ESPN
(guardado en stats_partido.datos["cornes"]).

RE-versión de decisión (Sesión 16 → 17): los cornes estaban declarados
fuera de alcance porque ninguna fuente gratuita los entregaba; ESPN los
trae por equipo en el MISMO summary de la ingesta común, así que vuelven
a estar dentro SIN ingesta nueva y SIN cron nuevo.

Cómo predice (misma maquinaria que tarjetas y tiros, una sola fuente):
- Tasa de cornes por equipo con shrinkage (rates.tasa_encogida, k=6).
- λ del partido = tasa_cornes(local) + tasa_cornes(visitante).
- Sin factor local/visitante (ver rates.py: la muestra joven lo prohíbe).
- P(over | línea) por Poisson truncada y renormalizada.

Sin ranking de jugadores: el córner lo batea quien pega, pero lo que el
mercado modela y lo verificable por partido es el TOTAL del equipo; el
desglose por batedor no justifica una predicción aparte.

Calidad walk-forward: acierto O/U 9.5/11.5 + MAE de λ (honesto: omite las
jornadas donde un equipo debutante aún no tiene historia).

Modelo ON-REQUEST: escribe SOLO respuestas, no tablas.

CLI de inspección (patrón tarjetas.py):
    python -m backend.app.cornes --liga PD
"""

from __future__ import annotations

import argparse

from .consola import consola_utf8
from .rates import (
    evaluar_walk_forward,
    prob_over,
    tasas_por_equipo,
)

LINES = (9.5, 11.5)         # líneas over/under del TOTAL del partido


# ─────────────────────────── extracción pura ────────────────────────────────


def bloques_de(fila: dict) -> tuple[dict | None, dict | None]:
    """(bloque_cornes_local, bloque_cornes_visit) — None si a ese lado le faltan."""
    dl, dv = fila.get("datos_l") or {}, fila.get("datos_v") or {}
    return dl.get("cornes") or None, dv.get("cornes") or None


def total_de(bloque: dict | None) -> int | None:
    """Cornes ganados por ese lado (None si no hay bloque)."""
    if bloque is None:
        return None
    return bloque.get("total") or 0


def extraer_cornes(fila: dict) -> list[tuple[int, float]]:
    """Extractor para tasas: [(equipo, cornes_del_equipo_en_el_partido), ...]."""
    salida: list[tuple[int, float]] = []
    bl, bv = bloques_de(fila)
    if bl is not None:
        salida.append((fila["local"], float(total_de(bl))))
    if bv is not None:
        salida.append((fila["visitante"], float(total_de(bv))))
    return salida


def lam_de(historia: list[dict], fila: dict) -> float | None:
    """λ total del partido con la historia previa (None si falta un equipo)."""
    tasas = tasas_por_equipo(historia, extraer_cornes)
    t_l = tasas.get(fila["local"])
    t_v = tasas.get(fila["visitante"])
    if t_l is None or t_v is None:
        return None  # equipo debutante: no se evalúa (honesto)
    return t_l + t_v


# ─────────────────────────── equipos del modelo ─────────────────────────────


def equipos_cornes(filas: list[dict]) -> dict[int, dict]:
    """{equipo_id: {"partidos", "cornes", "tasa"}} sobre filas completas."""
    tasas = tasas_por_equipo(filas, extraer_cornes)
    crews: dict[int, dict] = {}
    for f in filas:
        bl, bv = bloques_de(f)
        if bl is None or bv is None:
            continue  # solo filas completas
        for equipo_id, bloque in ((f["local"], bl), (f["visitante"], bv)):
            c = crews.setdefault(equipo_id, {"partidos": 0, "cornes": 0})
            c["partidos"] += 1
            c["cornes"] += total_de(bloque) or 0
    return {eid: {**c, "tasa": round(tasas.get(eid, 0.0), 2)} for eid, c in crews.items()}


# ───────────────────────── calidad walk-forward ────────────────────────────


def filas_completas_cornes(filas: list[dict]) -> list[dict]:
    """Solo filas con AMBOS lados del bloque cornes (igual que tarjetas)."""
    return [
        f for f in filas if bloques_de(f)[0] is not None and bloques_de(f)[1] is not None
    ]


def calidad_de_filas(filas: list[dict]) -> dict:
    """Walk-forward de la liga: acierto O/U 9.5/11.5 + MAE de λ."""
    completas = filas_completas_cornes(filas)
    evaluado = [
        {**f, "real": (total_de(bloques_de(f)[0]) or 0) + (total_de(bloques_de(f)[1]) or 0)}
        for f in completas
    ]
    return evaluar_walk_forward(evaluado, lam_de, LINES)


def prediccion_de_filas(
    filas: list[dict],
    id_local: int,
    id_visitante: int,
    fecha,
) -> dict | None:
    """Predicción para un partido puntual con TODO el historial previo a fecha."""
    historia = [f for f in filas if f["fecha"] < fecha]
    lam = lam_de(historia, {"local": id_local, "visitante": id_visitante})
    if lam is None:
        return None
    tasas = tasas_por_equipo(historia, extraer_cornes)
    t_l = tasas.get(id_local)
    t_v = tasas.get(id_visitante)
    return {
        "cornes_esperados": round(lam, 2),
        "prob_over_9_5": round(prob_over(lam, 9.5), 4),
        "prob_over_11_5": round(prob_over(lam, 11.5), 4),
        "por_equipo": {
            "local": (round(t_l, 2) if t_l is not None else None),
            "visitante": (round(t_v, 2) if t_v is not None else None),
        },
    }


# ──────────────────────────────── CLI (análisis) ────────────────────────────


def main() -> int:
    consola_utf8()
    parser = argparse.ArgumentParser(description="Modelo de cornes (Fase 16)")
    parser.add_argument("--liga", required=True, choices=("PD", "PL", "SA", "BL1", "CL"))
    args = parser.parse_args()

    # diferidos: el módulo queda importable en tests sin tocar la BD
    from sqlalchemy import select

    from .db import SessionLocal
    from .models import Partido
    from .stats_filas import filas_de_liga

    with SessionLocal() as session:
        filas = filas_de_liga(session, args.liga)
        if not filas:
            print(f"[{args.liga}] sin datos de ESPN todavía (backfill en curso)")
            return 0
        calidad = calidad_de_filas(filas)
        print(f"== Cornes [{args.liga}] — {len(filas)} partidos con datos ESPN ==")
        for linea, r in calidad["lineas"].items():
            acc = f"{r['accuracy']:.0%}" if r["accuracy"] is not None else "—"
            mae = f"{r['mae']:.2f}" if r["mae"] is not None else "—"
            print(f"   O/U {linea}: {r['aciertos']}/{r['evaluados']} ({acc}) · MAE λ {mae}")
        print(f"   omisiones (equipos debutantes): {calidad['omisiones']}")

        prox = session.scalars(
            select(Partido).where(
                Partido.liga == args.liga,
                Partido.estado.in_(("SCHEDULED", "TIMED")),
            ).order_by(Partido.utc_date).limit(8)
        ).all()
        if prox:
            print("\nPróximos partidos:")
            for p in prox:
                pred = prediccion_de_filas(filas, p.id_local, p.id_visitante, p.utc_date)
                if pred is None:
                    print(f"   {p.utc_date:%m-%d %H:%M} — sin tasa (debutante)")
                    continue
                print(
                    f"   {p.utc_date:%m-%d %H:%M}: esperados {pred['cornes_esperados']}"
                    f" · over 9.5 {pred['prob_over_9_5']:.0%}"
                    f" · over 11.5 {pred['prob_over_11_5']:.0%}"
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
