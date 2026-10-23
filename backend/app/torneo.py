"""Torneo de los modelos — FASE 13: ranking vivo de aciertos.

Qué hace este módulo:
- NO re-evalúa nada. El cron de la Fase 12 refresca `reales_vs_previsto` en
  cada corrida con la evaluación walk-forward (la MISMA `predecir()` que está
  viva) — este módulo lee ese ledger y lo presenta como un torneo: tasa de
  acierto 1X2, log loss y Brier medios, over/under 2.5 (solo las voces que
  emiten esa probabilidad), el recorte por liga y la FORMA viva (los últimos
  partidos confirmados de cada modelo, como la forma de un equipo en la
  tabla de posiciones).

Por qué es distinto de `/model-accuracy`: mismo ledger, otra lectura.
`/precision` mira la calidad probabilística liga por liga (backtesting);
`/torneo` arma la tabla de temporada como la miraría un hincha: quién va
ganando y cómo viene de forma.

CLI:
    python -m backend.app.torneo                 # podio completo
    python -m backend.app.torneo --forma 12      # más partidos por voz
"""

from __future__ import annotations

import argparse

from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from .consola import consola_utf8
from .db import SessionLocal
from .models import Equipo, Partido, RealesVsPrevisto

FORMA_POR_DEFECTO = 8
LIGAS_ORDEN = ("PD", "PL", "SA", "BL1", "CL")
MODELOS_ORDEN = ("poisson_doble", "poisson_dc", "lightgbm_v1")


def tasa_de(aciertos: int, evaluados: int) -> float | None:
    """Tasa honesta: None cuando no hay nada que medir (jamás fingir 0)."""
    return aciertos / evaluados if evaluados else None


def _orden_liga(liga: str) -> int:
    try:
        return LIGAS_ORDEN.index(liga)
    except ValueError:
        return len(LIGAS_ORDEN)


def construir_torneo(
    aggs: list[dict],
    formas: dict[str, list[dict]],
) -> list[dict]:
    """Arma el ranking a partir de agregados por (modelo, liga) + formas.

    `aggs`: dicts con modelo, liga, evaluados, aciertos, log_loss (media por
    liga o None), brier (ídem), o25_evaluados, o25_aciertos.
    `formas`: modelo → lista de filas de forma (recientes primero).
    Los agregados totales de log loss/Brier son promedios ponderados por n
    (equivalente exacto al promedio directo sobre todas las filas).
    """
    torneos: dict[str, dict] = {}
    for a in aggs:
        t = torneos.setdefault(
            a["modelo"],
            {
                "evaluados": 0,
                "aciertos": 0,
                "ll_peso": 0.0,
                "brier_peso": 0.0,
                "o25_eval": 0,
                "o25_ok": 0,
                "por_liga": [],
            },
        )
        n = a["evaluados"]
        t["evaluados"] += n
        t["aciertos"] += a["aciertos"]
        if a["log_loss"] is not None and n:
            t["ll_peso"] += float(a["log_loss"]) * n
        if a["brier"] is not None and n:
            t["brier_peso"] += float(a["brier"]) * n
        t["o25_eval"] += a["o25_evaluados"]
        t["o25_ok"] += a["o25_aciertos"]
        t["por_liga"].append(
            {
                "liga": a["liga"],
                "evaluados": n,
                "aciertos": a["aciertos"],
                "accuracy": tasa_de(a["aciertos"], n),
            }
        )

    salida: list[dict] = []
    for modelo, t in torneos.items():
        n = t["evaluados"]
        fila = {
            "modelo": modelo,
            "evaluados": n,
            "aciertos": t["aciertos"],
            "accuracy": tasa_de(t["aciertos"], n),
            "log_loss": t["ll_peso"] / n if n and t["ll_peso"] else None,
            "brier": t["brier_peso"] / n if n and t["brier_peso"] else None,
            "o25": (
                {
                    "evaluados": t["o25_eval"],
                    "aciertos": t["o25_ok"],
                    "accuracy": tasa_de(t["o25_ok"], t["o25_eval"]),
                }
                if t["o25_eval"]
                else None
            ),
            "por_liga": sorted(t["por_liga"], key=lambda x: _orden_liga(x["liga"])),
            "forma": formas.get(modelo, []),
        }
        salida.append(fila)

    salida.sort(
        key=lambda f: (
            -(f["accuracy"] if f["accuracy"] is not None else -1.0),
            -f["evaluados"],
            MODELOS_ORDEN.index(f["modelo"]) if f["modelo"] in MODELOS_ORDEN else 99,
        )
    )
    return salida


def leer_ledger(
    session,
    n_forma: int,
) -> tuple[list[dict], dict[str, list[dict]]]:
    """Lee `reales_vs_previsto` (+Partido, +Equipos).

    1) Agregados por (modelo, liga): n, aciertos, ll media, Brier media y
       la cuenta de over/under 2.5 tomada del JSONB (solo las filas ahí
       donde el modelo la emite — LightGBM v1 no la emite).
    2) Forma: los últimos n partidos confirmados por modelo.
    """
    o25 = RealesVsPrevisto.datos["acierto_over25"]
    aggs = [
        dict(
            modelo=modelo,
            liga=liga,
            evaluados=evaluados,
            aciertos=aciertos,
            log_loss=float(log_loss) if log_loss is not None else None,
            brier=float(brier) if brier is not None else None,
            o25_evaluados=o25_eval,
            o25_aciertos=o25_ok,
        )
        for (
            modelo,
            liga,
            evaluados,
            aciertos,
            log_loss,
            brier,
            o25_eval,
            o25_ok,
        ) in session.execute(
            select(
                RealesVsPrevisto.modelo,
                Partido.liga,
                func.count(),
                func.count().filter(RealesVsPrevisto.acierto_1x2.is_(True)),
                func.avg(RealesVsPrevisto.log_loss),
                func.avg(RealesVsPrevisto.brier_score),
                func.count().filter(o25.as_boolean().is_not(None)),
                func.count().filter(o25.as_boolean().is_(True)),
            )
            .join(Partido, Partido.id_api == RealesVsPrevisto.partido_id_api)
            .group_by(RealesVsPrevisto.modelo, Partido.liga)
            .order_by(RealesVsPrevisto.modelo, Partido.liga)
        ).all()
    ]

    formas: dict[str, list[dict]] = {}
    eq_local = aliased(Equipo)
    eq_visita = aliased(Equipo)
    for modelo in MODELOS_ORDEN:
        filas = session.execute(
            select(
                RealesVsPrevisto,
                Partido,
                eq_local.nombre,
                eq_visita.nombre,
            )
            .join(Partido, Partido.id_api == RealesVsPrevisto.partido_id_api)
            .join(eq_local, eq_local.id_api == Partido.id_local)
            .join(eq_visita, eq_visita.id_api == Partido.id_visitante)
            .where(RealesVsPrevisto.modelo == modelo)
            .order_by(Partido.utc_date.desc())
            .limit(n_forma)
        ).all()
        filas_forma = []
        for r, p, nombre_local, nombre_visita in filas:
            datos = r.datos or {}
            filas_forma.append(
                {
                    "partido_id_api": p.id_api,
                    "liga": p.liga,
                    "fecha_utc": p.utc_date.isoformat(),
                    "local": nombre_local,
                    "visitante": nombre_visita,
                    "goles_local": p.goles_local,
                    "goles_visitante": p.goles_visitante,
                    "elegido": datos.get("favorito_predicho") or "?",
                    "resultado": datos.get("resultado_real") or "?",
                    "acierto_1x2": bool(r.acierto_1x2),
                    "log_loss_prediccion": (
                        float(r.log_loss) if r.log_loss is not None else None
                    ),
                }
            )
        formas[modelo] = filas_forma

    return aggs, formas


def main() -> None:
    consola_utf8()
    parser = argparse.ArgumentParser(description="Torneo de los modelos (Fase 13)")
    parser.add_argument(
        "--forma",
        type=int,
        default=FORMA_POR_DEFECTO,
        help="Nº de partidos recientes por voz",
    )
    args = parser.parse_args()

    with SessionLocal() as session:
        aggs, formas = leer_ledger(session, args.forma)
    torneo = construir_torneo(aggs, formas)
    if not torneo:
        print("Aún no hay evaluaciones en `reales_vs_previsto`. Corre el cron o")
        print("  python -m backend.app.evaluacion --todas --guardar")
        return

    print("\n════ TORNEO DE LOS MODELOS · ranking vivo (Fase 13) ════")
    for pos, f in enumerate(torneo, 1):
        tasa = f["accuracy"] or 0.0
        print(
            f"\n{pos}º · {f['modelo']} — {f['aciertos']}/{f['evaluados']} aciertos:"
            f" {tasa:.1%} · log loss {(f['log_loss'] or float('nan')):.4f}"
            f" · Brier {(f['brier'] or float('nan')):.4f}"
        )
        if f["o25"]:
            o25 = f["o25"]
            print(
                f"   O2.5: {o25['aciertos']}/{o25['evaluados']}"
                f" ({(o25['accuracy'] or 0.0):.1%})"
            )
        print("   " + " · ".join(
            f"{lg['liga']} {lg['aciertos']}/{lg['evaluados']}" for lg in f["por_liga"]
        ))
        print("   forma (más reciente primero):")
        for g in f["forma"]:
            marca = "✓" if g["acierto_1x2"] else "✗"
            print(
                f"     {g['fecha_utc'][:10]} {g['local']:<26}"
                f" {g['goles_local']}-{g['goles_visitante']}"
                f" {g['visitante']:<26} elegí {g['elegido']:<7}{marca}"
                f"  (ll {g['log_loss_prediccion']:.2f})"
            )
    print()


if __name__ == "__main__":
    main()
