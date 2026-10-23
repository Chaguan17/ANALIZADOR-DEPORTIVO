"""Modelo de TARJETAS por partido — Poisson simple con tasa encogida (Fase 15).

Qué predice: el TOTAL de tarjetas del partido (amarillas + rojas, la misma
unidad que el mercado over/under de tarjetas) con dos líneas FIJAS del
proyecto: 2.5 y 3.5. Las rojas NO se modelan aparte (~0.15 tarjetas rojas
por partido: la muestra de una temporada no da para una PMF con criterio) —
se reportan como dato real, nunca como predicción (decisión documentada).

Cómo predice (la muestra es una temporada joven, ser honesto con ella):
- Tasa de tarjetas por equipo con shrinkage hacia la media de liga
  (rates.tasa_encogida, k=6): el equipo con pocos partidos tira hacia la
  media en vez de bailar con 3 juegos.
- λ del partido = tasa_tarjetas(local) + tasa_tarjetas(visitante).
- Sin factor local/visitante: con la muestra actual dividiría la muestra
  (documentado en rates.py).
- P(over | línea) por Poisson(λ) truncada y renormalizada.

Calidad walk-forward: para cada partido jugado se predice SOLO con partidos
estrictamente anteriores y se compara con la realidad
(rates.evaluar_walk_forward: acierto O/U por línea + MAE de λ).

Jugador "propenso": tarjetas POR APARICIÓN (ESPN no da minutos nivel
jugador; rosters sí dice quién estuvo en cancha: titular o entró).

Fuente de los datos: JSONB de `stats_partido` llenado por la ingesta ESPN
(backend.app.espn). Los modelos corren ON-REQUEST: no escriben tablas.

CLI de inspección (patrón torneo.py):
    python -m backend.app.tarjetas --liga PD
"""

from __future__ import annotations

import argparse

from .consola import consola_utf8
from .rates import (
    evaluar_walk_forward,
    mejor_jugadores,
    prob_over,
    tasas_por_equipo,
)

LINES = (2.5, 3.5)          # líneas over/under del TOTAL del partido
MIN_APARICIONES = 2         # mínimo para entrar al ranking de propensos
TOP_PROPENSOS = 5           # por equipo en la página de partido
NOTA_ROJAS = "las rojas no se predicen (evento raro); solo se reportan como reales"


# ─────────────────────────── extracción pura ────────────────────────────────


def bloques_de(fila: dict) -> tuple[dict | None, dict | None]:
    """(bloque_tarjetas_local, bloque_visita) o None si a ese lado le faltan datos."""
    dl, dv = fila.get("datos_l") or {}, fila.get("datos_v") or {}
    bl = dl.get("tarjetas") or None
    bv = dv.get("tarjetas") or None
    return bl, bv


def total_de(bloque: dict | None) -> int | None:
    """amarillas + rojas del bloque (None si no hay bloque)."""
    if bloque is None:
        return None
    return (bloque.get("amarillas") or 0) + (bloque.get("rojas") or 0)


def extraer_tarjetas(fila: dict) -> list[tuple[int, float]]:
    """rate.extractor: [(equipo_id, tarjetas_del_equipo_en_ese_partido), ...]."""
    salida: list[tuple[int, float]] = []
    bl, bv = bloques_de(fila)
    if bl is not None:
        salida.append((fila["local"], float(total_de(bl) or 0)))
    if bv is not None:
        salida.append((fila["visitante"], float(total_de(bv) or 0)))
    return salida


def contados_por_jugador(filas: list[dict], equipo_id: int) -> dict[str, dict]:
    """{nombre: {nombre, amarillas, rojas, apariciones}} con TODO el historial.

    La aparición ladan rosters (titular o entró); quien sale en un evento de
    tarjeta cuenta como aparición también (unión de ambas listas).
    """
    contados: dict[str, dict] = {}
    for fila in filas:
        es_local = fila["local"] == equipo_id
        bloque = (fila.get("datos_l") or {} if es_local else fila.get("datos_v") or {}).get("tarjetas")
        if bloque is None:
            continue
        espn = ((fila.get("datos_l") or {} if es_local else fila.get("datos_v") or {}).get("espn")) or {}
        vistos = {j["nombre"] for j in (espn.get("alineacion") or [])}
        eventos = bloque.get("por_jugador") or []
        for evento in eventos:
            vistos.add(evento["nombre"])
        for nombre in vistos:
            c = contados.setdefault(
                nombre, {"nombre": nombre, "amarillas": 0, "rojas": 0, "apariciones": 0}
            )
            c["apariciones"] += 1
        for evento in eventos:
            c = contados[evento["nombre"]]
            if evento["tipo"] == "amarilla":
                c["amarillas"] += 1
            elif evento["tipo"] == "roja":
                c["rojas"] += 1
    return contados


def propensos_equipo(filas: list[dict], equipo_id: int, top: int = TOP_PROPENSOS) -> list[dict]:
    """Ranking de propensos de UN equipo por tarjetas totales por aparición."""
    contados = contados_por_jugador(filas, equipo_id)
    return mejor_jugadores(contados, MIN_APARICIONES, top, "amarillas")


# ──────────────────────────── predicción y calidad ──────────────────────────


def equipos_tarjetas(filas: list[dict]) -> dict[int, dict]:
    """{equipo_id: {"partidos", "tarjetas", "tasa"}} contando las filas COMPLETAS.

    La tasa va ya encogida (la que alimenta el modelo); los totales son crudos.
    """
    tasas = tasas_por_equipo(filas, extraer_tarjetas)
    crews: dict[int, dict] = {}
    for f in filas:
        bl, bv = bloques_de(f)
        if bl is None or bv is None:
            continue  # solo filas completas: comparables
        for equipo_id, bloque in ((f["local"], bl), (f["visitante"], bv)):
            c = crews.setdefault(equipo_id, {"partidos": 0, "tarjetas": 0})
            c["partidos"] += 1
            c["tarjetas"] += (bloque.get("amarillas") or 0) + (bloque.get("rojas") or 0)
    return {eid: {**c, "tasa": round(tasas.get(eid, 0.0), 2)} for eid, c in crews.items()}


def propensos_liga(filas: list[dict], top: int = 15) -> list[dict]:
    """Top propensos de la liga: igual que por equipo, sumando todos los equipos."""
    globales: dict[str, dict] = {}
    equipo_de: dict[str, int] = {}
    for f in filas:
        bl, bv = bloques_de(f)
        for equipo_id, bloque in ((f["local"], bl), (f["visitante"], bv)):
            if bloque is None:
                continue
            for nombre, c in contados_por_jugador([f], equipo_id).items():
                g = globales.setdefault(
                    nombre, {"nombre": nombre, "amarillas": 0, "rojas": 0, "apariciones": 0}
                )
                g["amarillas"] += c["amarillas"]
                g["rojas"] += c["rojas"]
                g["apariciones"] += c["apariciones"]
                equipo_de.setdefault(nombre, equipo_id)
    salida = mejor_jugadores(globales, MIN_APARICIONES, top, "amarillas")
    return [{**f, "equipo_id_api": equipo_de[f["nombre"]]} for f in salida]


def lam_de(historia: list[dict], fila: dict) -> float | None:
    """λ total del partido con la historia previa (None si falta un equipo)."""
    tasas = tasas_por_equipo(historia, extraer_tarjetas)
    t_l = tasas.get(fila["local"])
    t_v = tasas.get(fila["visitante"])
    if t_l is None or t_v is None:
        return None  # equipo debutante: no se evalúa (omisión honesta)
    return t_l + t_v


def filas_completas(filas: list[dict]) -> list[dict]:
    """Solo filas con AMBOS lados con datos de tarjetas (para calidad/real)."""
    return [f for f in filas if bloques_de(f)[0] is not None and bloques_de(f)[1] is not None]


def calidad_de_filas(filas: list[dict]) -> dict:
    """Walk-forward de la liga: acierto O/U 2.5/3.5 + MAE de λ.

    Solo filas con el BLOQUE de tarjetas en ambos lados: una fila marca-de-vacío
    (la ingesta la dejó sin totales) no debería contaminar la métrica — es la
    regla que stats_filas documenta: cada dominio salta lo que le falta.
    """
    completas = filas_completas(filas)
    evaluadas = [
        {**f, "real": (total_de(bloques_de(f)[0]) or 0) + (total_de(bloques_de(f)[1]) or 0)}
        for f in completas
    ]
    return evaluar_walk_forward(evaluadas, lam_de, LINES)


def prediccion_de_filas(
    filas: list[dict],
    id_local: int,
    id_visitante: int,
    fecha,
) -> dict | None:
    """Predicción para un partido puntual con todo el historial previo a fecha."""
    historia = [f for f in filas if f["fecha"] < fecha]
    lam = lam_de(historia, {"local": id_local, "visitante": id_visitante})
    if lam is None:
        return None
    tasas = tasas_por_equipo(historia, extraer_tarjetas)
    t_l = tasas.get(id_local)
    t_v = tasas.get(id_visitante)
    return {
        "tarjetas_esperadas": round(lam, 2),
        "prob_over_2_5": round(prob_over(lam, 2.5), 4),
        "prob_over_3_5": round(prob_over(lam, 3.5), 4),
        "por_equipo": {
            "local": (round(t_l, 2) if t_l is not None else None),
            "visitante": (round(t_v, 2) if t_v is not None else None),
        },
    }


# ──────────────────────────────── CLI (análisis) ────────────────────────────


def main() -> int:
    consola_utf8()
    parser = argparse.ArgumentParser(description="Modelo de tarjetas (Fase 15)")
    parser.add_argument("--liga", required=True, choices=("PD", "PL", "SA", "BL1", "CL"))
    args = parser.parse_args()

    # deferidos: el módulo queda importable en tests sin tocar la BD
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
        print(f"== Tarjetas [{args.liga}] — {len(filas)} partidos con datos ESPN ==")
        for linea, r in calidad["lineas"].items():
            acc = f"{r['accuracy']:.0%}" if r["accuracy"] is not None else "—"
            mae = f"{r['mae']:.2f}" if r["mae"] is not None else "—"
            print(f"   O/U {linea}: {r['aciertos']}/{r['evaluados']} ({acc}) · MAE λ {mae}")
        print(f"   omisiones (equipos debutantes): {calidad['omisiones']}")
        print(f"   nota: {NOTA_ROJAS}")

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
                    print(f"   {p.utc_date:%m-%d %H:%M} — sin tasa (equipo debutante)")
                    continue
                print(
                    f"   {p.utc_date:%m-%d %H:%M}: esperadas {pred['tarjetas_esperadas']}"
                    f" · over 2.5 {pred['prob_over_2_5']:.0%} · over 3.5 {pred['prob_over_3_5']:.0%}"
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
