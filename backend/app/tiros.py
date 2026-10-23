"""Modelo de TIROS por partido — Poisson con tasa encogida (Fase 16).

Qué predice, con DOS líneas FIJAS del proyecto sobre DOS eventos distintos:
- TIROS totales (23.5): el total del partido = tiros del local + del visitante.
- TIROS A PUERTA (8.5): idem con `shotsOnTarget`. Cada evento tiene su PROPIO
  λ (dos PMF separadas): comparten maquinaria, no la predicción.

La unidad es la del mercado over/under de tiros; el modelo es el mismo del
núcleo rates (una sola fuente de verdad), solo cambia el extractor:

- Tasa por equipo con shrinkage hacia la media de liga (k=6).
- λ del partido = tasa_tiros(local) + tasa_tiros(visitante).
- Sin factor local/visitante (misma decisión de tarjetas, documentada en
  rates.py: con la muestra joven la división por rol la mataría).
- P(over | línea) por Poisson truncada y renormalizada.

Tiradores del ranking: los líderes de tiros de ESPN (campo `totalShots` por
jugador en el summary, guardado en datos.espn.tiros_jugador) divididos por
APARICIONES (rosters: quién estuvo en cancha). Criterio honesto idéntico al
de propensos de tarjetas: ESPN no entrega minutos por jugador, así que la
unidad es la aparición. Los leaders cubren a los goleadores de tiros del
partido (no a todo el plantel), así que el ranking describe tendencias.

Calidad walk-forward: rates.evaluar_walk_forward por cada stream (una llamada
con 23.5 y otra con 8.5; sus omisiones no se suman porque son el mismo tipo
de arranque sin historia). El MAE de λ es el principal, como en tarjetas.

Fuente: JSONB de `stats_partido` llenado por la ingesta ESPN (backend.app.espn).
Modelo ON-REQUEST: escribe SOLO respuestas, no tablas.

CLI de inspección (patrón tarjetas.py):
    python -m backend.app.tiros --liga PD
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

LINEA_TIROS = 23.5          # over/under del TIRO total del partido
LINEA_A_PUERTA = 8.5        # over/under del TIRO a puerta del partido
MIN_APARICIONES = 2         # mínimo para entrar al ranking de tiradores
TOP_TIRADORES = 5           # por equipo en la página del partido
NOTA_TIROS = (
    "a puerta: ESPN llama shotsOnTarget a lo que otros medios etiquetan "
    "disparos a puerta; es el mismo evento del mercado del partido"
)


# ─────────────────────────── extracción pura ────────────────────────────────


def bloques_de(fila: dict) -> tuple[dict | None, dict | None]:
    """(bloque_tiros_local, bloque_tiros_visit) — None si a ese lado le faltan."""
    dl, dv = fila.get("datos_l") or {}, fila.get("datos_v") or {}
    return dl.get("tiros") or None, dv.get("tiros") or None


def total_de(bloque: dict | None) -> int | None:
    """Tiros totales del bloque (None si no hay bloque)."""
    if bloque is None:
        return None
    return bloque.get("total") or 0


def a_puerta_de(bloque: dict | None) -> int | None:
    """Tiros a puerta del bloque (None si no hay bloque)."""
    if bloque is None:
        return None
    return bloque.get("a_puerta") or 0


def extraer_tiros(fila: dict) -> list[tuple[int, float]]:
    """Extractor para tasas: tiros TOTALES por equipo en el partido."""
    salida: list[tuple[int, float]] = []
    bl, bv = bloques_de(fila)
    if bl is not None:
        salida.append((fila["local"], float(total_de(bl))))
    if bv is not None:
        salida.append((fila["visitante"], float(total_de(bv))))
    return salida


def extraer_a_puerta(fila: dict) -> list[tuple[int, float]]:
    """Extractor para tasas: tiros A PUERTA por equipo en el partido."""
    salida: list[tuple[int, float]] = []
    bl, bv = bloques_de(fila)
    if bl is not None:
        salida.append((fila["local"], float(a_puerta_de(bl))))
    if bv is not None:
        salida.append((fila["visitante"], float(a_puerta_de(bv))))
    return salida


def lam_total_de(historia: list[dict], fila: dict) -> float | None:
    """λ del stream TIROS = suma de tasas (None si algún equipo no tiene historia)."""
    return _lam_de(historia, fila, extraer_tiros)


def lam_a_puerta_de(historia: list[dict], fila: dict) -> float | None:
    """λ del stream A PUERTA = suma de tasas (None si falta un equipo)."""
    return _lam_de(historia, fila, extraer_a_puerta)


def _lam_de(historia: list[dict], fila: dict, extraer) -> float | None:
    """λ = suma de las tasas de ambos equipos con la historia (`extraer` da el
    evento); None si algún equipo no tiene partidos en la historia."""
    tasas = tasas_por_equipo(historia, extraer)
    t_l = tasas.get(fila["local"])
    t_v = tasas.get(fila["visitante"])
    if t_l is None or t_v is None:
        return None  # equipo debutante: omisión honesta
    return t_l + t_v


# ────────────────────────────── tiradores ───────────────────────────────────


def contados_de_tiros(filas: list[dict], equipo_id: int) -> dict[str, dict]:
    """{nombre: {nombre, tiros, apariciones}} con TODO el historial del equipo.

    Aparición = estar en la alineación (rosters) o salir en los líderes de
    tiros (ambas señales dicen "estuvo en cancha"); tiros vienen de los leaders.
    """
    contados: dict[str, dict] = {}
    for fila in filas:
        lado = fila["datos_l"] if fila["local"] == equipo_id else fila["datos_v"]
        bloque = lado.get("tiros")
        if bloque is None:
            continue
        espn = lado.get("espn") or {}
        en_cancha = {j["nombre"] for j in espn.get("alineacion") or []}
        leaders = {t["nombre"]: t["tiros"] for t in espn.get("tiros_jugador") or []}
        en_cancha.update(leaders)
        for nombre in en_cancha:
            c = contados.setdefault(
                nombre, {"nombre": nombre, "tiros": 0, "apariciones": 0}
            )
            c["apariciones"] += 1
            c["tiros"] += leaders.get(nombre, 0)
    return contados


def tiradores_equipo(
    filas: list[dict], equipo_id: int, top: int = TOP_TIRADORES
) -> list[dict]:
    """Ranking de tiradores de UN equipo por tiros POR APARICIÓN."""
    contados = contados_de_tiros(filas, equipo_id)
    return mejor_jugadores(contados, MIN_APARICIONES, top, "tiros")


def tiradores_liga(filas: list[dict], top: int = 15) -> list[dict]:
    """Top tiradores de la liga, sumando equipos (igual que propensos_liga)."""
    globales: dict[str, dict] = {}
    equipo_de: dict[str, int] = {}
    for f in filas:
        for equipo_id in (f["local"], f["visitante"]):
            for nombre, c in contados_de_tiros([f], equipo_id).items():
                g = globales.setdefault(
                    nombre, {"nombre": nombre, "tiros": 0, "apariciones": 0}
                )
                g["tiros"] += c["tiros"]
                g["apariciones"] += c["apariciones"]
                equipo_de.setdefault(nombre, equipo_id)
    salida = mejor_jugadores(globales, MIN_APARICIONES, top, "tiros")
    return [{**t, "equipo_id_api": equipo_de[t["nombre"]]} for t in salida]


# ─────────────────────────── equipos del modelo ─────────────────────────────


def equipos_tiros(filas: list[dict]) -> dict[int, dict]:
    """{equipo_id: {"partidos", "tiros", "a_puerta", "tasa_tiros", "tasa_a_puerta"}}.

    Totales crudos sobre filas COMPLETAS (comparables); tasas encogidas que
    alimentan las predicciones.
    """
    tasas_t = tasas_por_equipo(filas, extraer_tiros)
    tasas_ap = tasas_por_equipo(filas, extraer_a_puerta)
    crews: dict[int, dict] = {}
    for f in filas:
        bl, bv = bloques_de(f)
        if bl is None or bv is None:
            continue  # solo filas completas
        for equipo_id, bloque in ((f["local"], bl), (f["visitante"], bv)):
            c = crews.setdefault(equipo_id, {"partidos": 0, "tiros": 0, "a_puerta": 0})
            c["partidos"] += 1
            c["tiros"] += total_de(bloque) or 0
            c["a_puerta"] += a_puerta_de(bloque) or 0
    return {
        eid: {
            **c,
            "tasa_tiros": round(tasas_t.get(eid, 0.0), 2),
            "tasa_a_puerta": round(tasas_ap.get(eid, 0.0), 2),
        }
        for eid, c in crews.items()
    }


# ───────────────────────── calidad walk-forward ────────────────────────────


def filas_completas_tiros(filas: list[dict]) -> list[dict]:
    """Solo filas con el BLOQUE tiros de ambos lados (igual que tarjetas)."""
    return [
        f for f in filas if bloques_de(f)[0] is not None and bloques_de(f)[1] is not None
    ]


def calidad_de_filas(filas: list[dict]) -> dict:
    """Walk-forward DOS streams: total (23.5) y a puerta (8.5).

    La "real" de cada stream es la suma de ambos lados del bloque tiros.
    """
    completas = filas_completas_tiros(filas)
    evalu_t = [
        {**f, "real": (total_de(bloques_de(f)[0]) or 0) + (total_de(bloques_de(f)[1]) or 0)}
        for f in completas
    ]
    evalu_ap = [
        {**f, "real": (a_puerta_de(bloques_de(f)[0]) or 0) + (a_puerta_de(bloques_de(f)[1]) or 0)}
        for f in completas
    ]
    return {
        "total": evaluar_walk_forward(evalu_t, lam_total_de, (LINEA_TIROS,)),
        "a_puerta": evaluar_walk_forward(evalu_ap, lam_a_puerta_de, (LINEA_A_PUERTA,)),
    }


def calidad_a_lineas(calidad: dict) -> dict:
    """Junta los dos streams en el mismo mapa {"lineas": {..., "23.5": ..., "8.5": ...}}.

    Las omisiones de cada stream son el MISMO proceso (equipos sin historia al
    abrir la liga): se reporta el máximo, no la suma, para no contar dos veces.
    """
    lineas = {**calidad["total"]["lineas"], **calidad["a_puerta"]["lineas"]}
    return {
        "lineas": lineas,
        "omisiones": max(calidad["total"]["omisiones"], calidad["a_puerta"]["omisiones"]),
    }


# ────────────────────────── predicción puntual ──────────────────────────────


def prediccion_de_filas(
    filas: list[dict],
    id_local: int,
    id_visitante: int,
    fecha,
) -> dict | None:
    """Predicción para un partido puntual con TODO el historial previo a fecha."""
    historia = [f for f in filas if f["fecha"] < fecha]
    filtro = {"local": id_local, "visitante": id_visitante}
    lam_t = lam_total_de(historia, filtro)
    lam_ap = lam_a_puerta_de(historia, filtro)
    if lam_t is None or lam_ap is None:
        return None
    tasas_t = tasas_por_equipo(historia, extraer_tiros)
    tasas_ap = tasas_por_equipo(historia, extraer_a_puerta)
    por_equipo = {}
    for lado, eid in (("local", id_local), ("visitante", id_visitante)):
        t = tasas_t.get(eid)
        a = tasas_ap.get(eid)
        por_equipo[lado] = {
            "tiros": round(t, 2) if t is not None else None,
            "a_puerta": round(a, 2) if a is not None else None,
        }
    return {
        "tiros_esperados": round(lam_t, 2),
        "a_puerta_esperados": round(lam_ap, 2),
        "prob_over_23_5": round(prob_over(lam_t, LINEA_TIROS), 4),
        "prob_a_puerta_over_8_5": round(prob_over(lam_ap, LINEA_A_PUERTA), 4),
        "por_equipo": por_equipo,
    }


# ──────────────────────────────── CLI (análisis) ────────────────────────────


def main() -> int:
    consola_utf8()
    parser = argparse.ArgumentParser(description="Modelo de tiros (Fase 16)")
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
        calidad = calidad_a_lineas(calidad_de_filas(filas))
        print(f"== Tiros [{args.liga}] — {len(filas)} partidos con datos ESPN ==")
        for linea, r in calidad["lineas"].items():
            etiqueta = "a puerta" if linea == "8.5" else "total"
            acc = f"{r['accuracy']:.0%}" if r["accuracy"] is not None else "—"
            mae = f"{r['mae']:.2f}" if r["mae"] is not None else "—"
            print(f"   O/U {linea} ({etiqueta}): {r['aciertos']}/{r['evaluados']} ({acc}) · MAE λ {mae}")
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
                    print(f"   {p.utc_date:%m-%d %H:%M} — sin tasa (equipo debutante)")
                    continue
                print(
                    f"   {p.utc_date:%m-%d %H:%M}: tiros {pred['tiros_esperados']}"
                    f" (a puerta {pred['a_puerta_esperados']})"
                    f" · over 23.5 {pred['prob_over_23_5']:.0%}"
                    f" · over 8.5 {pred['prob_a_puerta_over_8_5']:.0%}"
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
