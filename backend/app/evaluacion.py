"""Evaluación walk-forward del modelo — FASE 7.

Cómo se evalúa sin trampa:
- El modelo `predecir()` (modelo.py) es consciente de la fecha: para cada partido
  ya JUGADO usa SOLO partidos con fecha anterior. Evaluar el pasado = repetir
  exactamente lo que pasaría prediciendolo "en vivo" → walk-forward por diseño.
- NO se toca la tabla `prediccion` (es de predicciones vivas): las evaluaciones
  van a `reales_vs_previsto` según su propósito (comentado en models.py),
  idempotentes por la UNIQUE (partido, modelo).

Métricas (todas sobre la distribución 1X2 salvo nota):
- log loss: -log(P del resultado real). Menor = mejor. Azar uniforme = ln(3) ≈ 1.0986
- Brier: Σ (P_c - 1{c = real})². 0 = perfecto, 2/3 ≈ 0.6667 = azar uniforme
- accuracy 1X2: el favorito acertó. Baseline "siempre local" = % de partidos que
  ganó el local en el propio set (no necesita información)
- over/under 2.5: accuracy + Brier binario del total de goles
- calibración: en cubetas de 10%, ¿la frecuencia real de aciertos coincide con
  la probabilidad promedio prometida? (un modelo calibrado se apoya sobre la diagonal)
- MAE goles: promedio de |λ - goles reales| por equipo (calidad de las intensidades)

Notas honestas:
- El free tier no expone CUOTAS → el benchmark del plano se sustituye por
  los baselines "siempre local" y "uniforme" (documentado en CONTEXTO §3).
- Primeros partidos de la temporada (calentamiento): el modelo walk-forward no
  evalúa con menos de MIN_EVIDENCIA partidos previos; se cuentan como saltados.

CLI:
    python -m backend.app.evaluacion              # demo: LaLiga + 5 peores
    python -m backend.app.evaluacion --todas --guardar   # las 5 ligas → BD
"""

from __future__ import annotations

import argparse
import math
from collections import defaultdict

from sqlalchemy import delete as sa_delete
from sqlalchemy import select

from .consola import consola_utf8
from .db import SessionLocal
from .features import HistoriaLiga, _nombres_equipos
from .models import Partido, RealesVsPrevisto
from .modelo import NOMBRE_MODELO, predecir

EPSILON = 1e-15          # clip para que -log no reviente con probabilidades ~0
MIN_EVIDENCIA = 2        # calentamiento: mínimo de partidos previos para evaluar
CLASES = ("local", "empate", "visita")


def _resultado_de(goles_local: int, goles_visitante: int) -> str:
    if goles_local > goles_visitante:
        return "local"
    if goles_local == goles_visitante:
        return "empate"
    return "visita"


def evaluar_liga(liga: str, temporada: int) -> tuple[list[dict], int]:
    """Evalúa TODOS los partidos FINISHED de la liga; devuelve (filas, saltados)."""
    historia = HistoriaLiga(liga, temporada)
    with SessionLocal() as session:
        partidos = (
            session.execute(
                select(Partido)
                .where(
                    Partido.liga == liga,
                    Partido.temporada == temporada,
                    Partido.estado == "FINISHED",
                    Partido.goles_local.is_not(None),
                )
                .order_by(Partido.utc_date)
            )
            .scalars()
            .all()
        )

    filas: list[dict] = []
    saltados = 0
    for p in partidos:
        # ¿tiene el modelo evidencia previa suficiente para este partido?
        previos = sum(1 for r in historia.partidos if r.fecha < p.utc_date)
        if previos < MIN_EVIDENCIA:  # calentamiento: el arranque frío no se evalúa
            saltados += 1
            continue

        pr = predecir(historia, p.id_local, p.id_visitante, p.utc_date)
        probs = {
            "local": float(pr["pro_local"]),
            "empate": float(pr["pro_empate"]),
            "visita": float(pr["pro_visita"]),
        }
        real = _resultado_de(p.goles_local, p.goles_visitante)

        log_loss = -math.log(max(probs[real], EPSILON))
        brier = sum((probs[c] - (1.0 if c == real else 0.0)) ** 2 for c in probs)
        favorito = max(probs, key=probs.get)

        total_goles = p.goles_local + p.goles_visitante
        over_real = total_goles > 2  # "over 2.5" ⇔ total de goles ≥ 3
        brier_o25 = (float(pr["pro_over25"]) - (1.0 if over_real else 0.0)) ** 2

        mae_goles = (
            abs(float(pr["lam_local"]) - p.goles_local)
            + abs(float(pr["lam_visita"]) - p.goles_visitante)
        ) / 2

        filas.append(
            {
                "partido": p,
                "probs": probs,
                "real": real,
                "favorito": favorito,
                "acierto": favorito == real,
                "log_loss": log_loss,
                "brier": brier,
                "lam_local": float(pr["lam_local"]),
                "lam_visita": float(pr["lam_visita"]),
                "over_real": over_real,
                "acierto_o25": (float(pr["pro_over25"]) > 0.5) == over_real,
                "brier_o25": brier_o25,
                "mae_goles": mae_goles,
            }
        )
    return filas, saltados


def _agregar(filas: list[dict]) -> dict | None:
    """Agregados promedio de una lista de filas evaluadas."""
    n = len(filas)
    if n == 0:
        return None
    return {
        "n": n,
        "accuracy": sum(f["acierto"] for f in filas) / n,
        "baseline_local": sum(f["real"] == "local" for f in filas) / n,
        "log_loss": sum(f["log_loss"] for f in filas) / n,
        "brier": sum(f["brier"] for f in filas) / n,
        "accuracy_o25": sum(f["acierto_o25"] for f in filas) / n,
        "baseline_over": sum(f["over_real"] for f in filas) / n,
        "brier_o25": sum(f["brier_o25"] for f in filas) / n,
        "mae_goles": sum(f["mae_goles"] for f in filas) / n,
    }


def _imprimir_resumen(titulo: str, agg: dict, saltados: int) -> None:
    print(f"\n────────── {titulo} · {NOMBRE_MODELO} ──────────")
    print(
        f"  Partidos evaluados: {agg['n']}"
        f"   (saltados sin evidencia previa: {saltados})"
    )
    print(
        f"  1X2 · accuracy:        {agg['accuracy']:>7.1%}"
        f"   baselines → siempre-local: {agg['baseline_local']:.1%} · uniforme: 33.3%"
    )
    print(
        f"  1X2 · log loss:        {agg['log_loss']:>7.4f}"
        f"   (uniforme: {math.log(3):.4f} — menor es mejor)"
    )
    print(
        f"  1X2 · Brier:           {agg['brier']:>7.4f}"
        f"   (uniforme: 0.6667)"
    )
    print(
        f"  O2.5 · accuracy:       {agg['accuracy_o25']:>7.1%}"
        f"   baseline 'siempre-over': {agg['baseline_over']:.1%}"
    )
    print(f"  O2.5 · Brier binario:  {agg['brier_o25']:>7.4f}")
    print(f"  Goles · MAE |λ-real|:  {agg['mae_goles']:>7.3f}")


def tabla_calibracion(filas: list[dict]) -> None:
    """¿Las probabilidades prometidas coinciden con las frecuencias reales?"""
    bins: dict[str, list] = defaultdict(list)
    for f in filas:
        for c in CLASES:
            p = f["probs"][c]
            cubeta = min(int(p * 10), 9)  # 0.30 → índice 3 · 0.99 → 9
            bins[c].append((cubeta, p, 1.0 if f["real"] == c else 0.0))

    print("\n  Calibración por cubetas de 10% (n | prob prometida | frecuencia real):")
    print(f"  {'cubeta':<10}{'local':<22}{'empate':<22}{'visita':<22}")
    por_cubeta: dict[int, dict[str, list]] = defaultdict(dict)
    for c in CLASES:
        for cubeta, p, hit in bins[c]:
            actual = por_cubeta[cubeta].setdefault(c, [0, 0.0, 0.0])
            actual[0] += 1
            actual[1] += p
            actual[2] += hit
    for i in range(10):
        celdas = []
        vacia = True
        for c in CLASES:
            d = por_cubeta[i].get(c)
            if d and d[0] > 0:
                vacia = False
                celdas.append(f"{d[0]:>3} {d[1]/d[0]:.0%}/{d[2]/d[0]:.0%}")
            else:
                celdas.append("—")
        if not vacia:
            print(f"  {i*10:>3}-{i*10+10:<6}{''.join(f'{x:<22}' for x in celdas)}")


def _persistir(filas: list[dict]) -> int:
    """Guarda las evaluaciones en reales_vs_previsto (delete+insert idempotente)."""
    if not filas:
        return 0
    with SessionLocal.begin() as session:
        session.execute(
            sa_delete(RealesVsPrevisto).where(
                RealesVsPrevisto.modelo == NOMBRE_MODELO,
                RealesVsPrevisto.partido_id_api.in_(
                    [f["partido"].id_api for f in filas]
                ),
            )
        )
        for f in filas:
            p = f["partido"]
            session.add(
                RealesVsPrevisto(
                    partido_id_api=p.id_api,
                    modelo=NOMBRE_MODELO,
                    acierto_1x2=f["acierto"],
                    brier_score=f["brier"],
                    log_loss=f["log_loss"],
                    datos={
                        "liga": p.liga,
                        "temporada": p.temporada,
                        "fecha_utc": p.utc_date.isoformat(),
                        "id_local": p.id_local,
                        "id_visitante": p.id_visitante,
                        "resultado_real": f["real"],
                        "favorito_predicho": f["favorito"],
                        "probs": f["probs"],
                        "lam_local": f["lam_local"],
                        "lam_visita": f["lam_visita"],
                        "goles_reales": [p.goles_local, p.goles_visitante],
                        "over25_real": f["over_real"],
                        "acierto_over25": f["acierto_o25"],
                    },
                )
            )
    return len(filas)


def _imprimir_peores(filas: list[dict], nombres: dict[int, str], n: int) -> None:
    peores = sorted(filas, key=lambda f: f["log_loss"], reverse=True)[:n]
    print(f"\n  Los {len(peores)} fallos más caros (log loss) de esta liga:")
    for f in peores:
        p = f["partido"]
        print(
            f"    {p.utc_date:%m-%d} {nombres[p.id_local]:<24} {p.goles_local}-"
            f"{p.goles_visitante} {nombres[p.id_visitante]:<24}"
            f"A {f['log_loss']:.2f} (modelo: {f['favorito']} {f['probs'][f['favorito']]:.0%})"
        )


def main() -> None:
    consola_utf8()
    parser = argparse.ArgumentParser(description="Evaluación walk-forward (Fase 7)")
    parser.add_argument("--liga", default="PD", help="Código de liga (PD/PL/SA/BL1/CL)")
    parser.add_argument("--todas", action="store_true", help="Las 5 ligas del MVP")
    parser.add_argument("--peores", type=int, default=5, help="Nº fallos caros a listar")
    parser.add_argument("--guardar", action="store_true", help="Persistir en reales_vs_previsto")
    args = parser.parse_args()

    from pipeline.config import LIGAS_MVP, SEASON

    ligas = list(LIGAS_MVP) if args.todas else [args.liga]

    global_agg_filas: list[dict] = []
    global_saltados = 0

    for liga in ligas:
        filas, saltados = evaluar_liga(liga, SEASON)
        agg = _agregar(filas)
        nombres = _nombres_equipos(
            sorted({f["partido"].id_local for f in filas} | {f["partido"].id_visitante for f in filas})
        )
        if agg:
            _imprimir_resumen(liga, agg, saltados)
            tabla_calibracion(filas)
            if args.peores > 0:
                _imprimir_peores(filas, nombres, args.peores)
        else:
            print(f"\n[{liga}] sin partidos FINISHED evaluables")
        global_agg_filas.extend(filas)
        global_saltados += saltados

        if args.guardar and filas:
            guardadas = _persistir(filas)
            print(f"  💾 {guardadas} evaluaciones persistidas en 'reales_vs_previsto'.")

    if len(ligas) > 1:
        agg = _agregar(global_agg_filas)
        if agg:
            _imprimir_resumen("TOTAL 5 LIGAS", agg, global_saltados)


if __name__ == "__main__":
    main()
