"""LightGBM — FASE 5c: árboles gradient-boosting sobre las features de la Fase 4.

Paradigma opuesto al Poisson: sin estructura de fútbol gravada a mano (no hay
μ, ni fuerzas atk/dfn, ni τ) — el árbol aprende cortes sobre las 31 features
walk-forward de `features_de_partido()` (forma ventana-5, comportamiento por
condición casa/fuera, descanso, snapshot de tabla al día y H2H). LightGBM
maneja nativamente los valores faltantes del arranque frío (None → NaN).

Protocolo walk-forward (idéntico a Fases 7/5b para comparar en limpio):
- los FINISHED se ordenan por fecha; para evaluar el partido i se entrena
  SOLO con los partidos anteriores, cada uno con features computadas a la
  fecha de CADA uno (sin filtración de futuro, por construcción);
- calentamiento reforzado: se exigen MIN_EVIDENCIA=2 previos Y que el pool
  entrenante contenga las 3 clases (si nunca apareció un empate, la salida
  3-clases no está definida → el partido se salta y se cuenta);
- hiperparámetros diminutos para datos diminutos: 60 árboles · 7 hojas ·
  depth ≤ 3 · lr 0.08 · min_data_in_leaf 6 · seed fija (reproducible).

La primera corrida sin protección lo confirmó a lo grande: el árbol puro se
vuelve SOBRECONFIADO cuando entrena con pocas filas (prometió 99% en un
favorito y log loss 1.60 en LaLiga — peor que el azar). La cura es el análogo
exacto del K_SHRINK del Poisson: MEZCLA CON LA UNIFORME
    p_final = w · p_arbol + (1 − w) · (1/3, 1/3, 1/3)
con w por liga elegido por grid-search (0.00…1.00, paso 0.05) minimizando el
log loss walk-forward — el mismo estilo honesto de la ρ de Dixon-Coles
(matiz in-sample de 1 parámetro, documentado). Untamed trees = cero.

Qué NO produce: el árbol no emite intensidades de goles → λ, over/under 2.5
y marcador persisten como NULL en las filas (modelo="lightgbm_v1").
Construir un Poisson encima del árbol sería un doble modelo disfrazado:
honestidad > gancho. (La mejora del O2.5 queda para versiones futuras.)

Usa la API raw de LightGBM (sin scikit-learn): el output multiclase siempre
devuelve (n, 3) con columnas ordenadas 0=local, 1=empate, 2=visita.

CLI:
    python -m backend.app.modelo_lgbm --liga PD           # demo comparación
    python -m backend.app.modelo_lgbm --todas --guardar   # evaluaciones → reales_vs_previsto
    python -m backend.app.modelo_lgbm --todas --vivas     # predicciones vivas → prediccion
"""

from __future__ import annotations

import argparse
import math

import lightgbm as lgb
import numpy as np
from sqlalchemy import select

from .consola import consola_utf8
from .db import SessionLocal
from .evaluacion import (
    MIN_EVIDENCIA,
    _agregar,
    _imprimir_peores,
    _persistir,
    _resultado_de,
    evaluar_liga,
)
from .features import HistoriaLiga, _nombres_equipos, _proximos, features_de_partido
from .modelo import NOMBRE_MODELO, predecir_y_guardar
from .models import Partido

NOMBRE_MODELO_LGBM = "lightgbm_v1"

PARAMS = {
    "objective": "multiclass",
    "num_class": 3,
    "boosting": "gbdt",
    "n_estimators": 60,        # pocas rondas: con 60-300 filas el sobreajuste manda
    "learning_rate": 0.08,
    "num_leaves": 7,
    "max_depth": 3,
    "min_data_in_leaf": 6,
    "feature_fraction": 0.8,
    "seed": 42,
    "verbose": -1,
}

W_GRID: list[float] = [round(i * 0.05, 2) for i in range(21)]  # 0.00 … 1.00


def _mezclar(probs: dict[str, float], w: float) -> dict[str, float]:
    """Mezcla con la uniforme: p = w·p_árbol + (1−w)/3 (análogo del K_SHRINK)."""
    return {c: w * probs[c] + (1.0 - w) / 3.0 for c in probs}


def _etiqueta_de(goles_local: int, goles_visitante: int) -> int:
    """0=local · 1=empate · 2=visita (mapeo único del resultado)."""
    if goles_local > goles_visitante:
        return 0
    if goles_local == goles_visitante:
        return 1
    return 2


def _a_numeros(vector: dict) -> list[float]:
    """features_de_partido → lista de floats (None → NaN, LightGBM los entiende)."""
    return [float(v) if v is not None else math.nan for v in vector.values()]


def _fila_lgbm(booster, historia, id_local: int, id_visitante: int, fecha) -> dict:
    """Predicción 1X2 con LightGBM; los campos de goles quedan NULL honestos.

    Devuelve el mismo shape que `predecir()`/`predecir_dc()` para reutilizar
    la persistencia parametrizada de la Fase 5b.
    """
    f = features_de_partido(historia, id_local, id_visitante, fecha)
    probas = booster.predict(np.array([_a_numeros(f)]))[0]  # (3,) orden 0,1,2 SIEMPRE
    return {
        "pro_local": float(probas[0]),
        "pro_empate": float(probas[1]),
        "pro_visita": float(probas[2]),
        "lam_local": None,
        "lam_visita": None,
        "mu_casa": None,
        "mu_visita": None,
        "atk_casa_local": None,
        "dfn_fuera_visita": None,
        "atk_fuera_visita": None,
        "dfn_casa_local": None,
        "marcador_estimado": None,
        "pro_over25": None,
        "pro_under25": None,
        "masa_grid": None,
        "datos": None,
        "rho": None,
    }


def _select_partidos(liga: str, temporada: int):
    """SELECT de los FINISHED de la liga, ordenados por fecha."""
    return (
        select(Partido)
        .where(
            Partido.liga == liga,
            Partido.temporada == temporada,
            Partido.estado == "FINISHED",
            Partido.goles_local.is_not(None),
        )
        .order_by(Partido.utc_date)
    )


def _pool_de_liga(historia, partidos: list[Partido]) -> list[dict]:
    """Features+etiqueta de cada FINISHED, computadas a la fecha de cada uno.

    Cada elemento sirve como fila entrenante walk-forward y como fila a
    evaluar en su momento (el pool crece SOLO con partidos del pasado).
    """
    pool: list[dict] = []
    for p in partidos:
        f = features_de_partido(historia, p.id_local, p.id_visitante, p.utc_date)
        previos = sum(1 for r in historia.partidos if r.fecha < p.utc_date)
        pool.append(
            {
                "partido": p,
                "x": _a_numeros(f),
                "y": _etiqueta_de(p.goles_local, p.goles_visitante),
                "previos": previos,
            }
        )
    return pool


def evaluar_liga_lgbm(
    liga: str, temporada: int
) -> tuple[list[dict], int, float, float]:
    """Backtesting walk-forward de LightGBM.

    Devuelve (filas, saltados, mejor_w, log_loss_con_w): las filas llevan las
    probabilidades YA mezcladas con la uniforme (mejor_w del grid-search) y
    el campo "mezcla_uniforme" para que viaje hasta la BD.
    """
    historia = HistoriaLiga(liga, temporada)
    with SessionLocal() as session:
        partidos = session.execute(_select_partidos(liga, temporada)).scalars().all()

    pool = _pool_de_liga(historia, partidos)

    # Primera pasada: probabilidades CRUDAS + resultado real (aún sin mezclar).
    pruebas: list[dict] = []
    saltados = 0
    X_pool: list[list[float]] = []
    y_pool: list[int] = []

    for fila in pool:
        p = fila["partido"]
        # calentamiento reforzado: evidencia mínima + las 3 clases presentes
        if fila["previos"] < MIN_EVIDENCIA or len(set(y_pool)) < 3:
            saltados += 1
            X_pool.append(fila["x"])
            y_pool.append(fila["y"])
            continue

        train = lgb.Dataset(np.array(X_pool), label=np.array(y_pool))
        booster = lgb.train(PARAMS, train, num_boost_round=PARAMS["n_estimators"])

        pr = _fila_lgbm(booster, historia, p.id_local, p.id_visitante, p.utc_date)
        pruebas.append(
            {
                "partido": p,
                "raw": {
                    "local": pr["pro_local"],
                    "empate": pr["pro_empate"],
                    "visita": pr["pro_visita"],
                },
                "real": _resultado_de(p.goles_local, p.goles_visitante),
                "over_real": (p.goles_local + p.goles_visitante) > 2,
            }
        )
        X_pool.append(fila["x"])
        y_pool.append(fila["y"])

    if not pruebas:
        return [], saltados, 0.0, None

    # Grid-search de w: el análogo del K_SHRINK, mirando solo el pasado.
    mejor_w, mejor_ll = 1.0, None
    for w in W_GRID:
        ll = sum(
            -math.log(max(_mezclar(t["raw"], w)[t["real"]], 1e-15)) for t in pruebas
        ) / len(pruebas)
        if mejor_ll is None or ll < mejor_ll:
            mejor_w, mejor_ll = w, ll

    # Segunda pasada: filas finales con las probabilidades mezcladas.
    filas: list[dict] = []
    for t in pruebas:
        probs = _mezclar(t["raw"], mejor_w)
        real = t["real"]
        favorito = max(probs, key=probs.get)
        filas.append(
            {
                "partido": t["partido"],
                "probs": probs,
                "real": real,
                "favorito": favorito,
                "acierto": favorito == real,
                "log_loss": -math.log(max(probs[real], 1e-15)),
                "brier": sum(
                    (probs[c] - (1.0 if c == real else 0.0)) ** 2 for c in probs
                ),
                "raw_lgbm": t["raw"],  # probabilidades crudas, para diagnóstico
                "mezcla_uniforme": mejor_w,
                "lam_local": None,
                "lam_visita": None,
                "over_real": t["over_real"],
                "acierto_o25": None,  # LightGBM v1 no emite over/under
                "brier_o25": None,
                "mae_goles": None,
            }
        )

    return filas, saltados, mejor_w, mejor_ll


def _imprimir_resumen_liga(titulo: str, resumen: dict[str, tuple[dict, int]]) -> None:
    """Una línea por modelo, contando con las mismas métricas de la Fase 7."""
    print(f"\n────── {titulo} ──────")
    for modelo_etiqueta, (agg, salt) in resumen.items():
        print(
            f"  {modelo_etiqueta:<14}"
            f" accuracy {agg['accuracy']:.1%} · log loss {agg['log_loss']:.4f}"
            f" · Brier {agg['brier']:.4f} · n {agg['n']} (saltados {salt})"
        )


def _fila_texto_1x2(r: dict, nombres: dict[int, str]) -> str:
    """Versión 1X2 puro de la línea de resumen (LightGBM no emite λ/over)."""
    p = r["partido"]
    if r["pro_local"] == max(r["pro_local"], r["pro_empate"], r["pro_visita"]):
        favorito = nombres[p.id_local]
    elif r["pro_visita"] >= r["pro_empate"]:
        favorito = nombres[p.id_visitante]
    else:
        favorito = "EMPATE"
    return (
        f"{p.utc_date:%m-%d} {nombres[p.id_local]:<26}{nombres[p.id_visitante]:<26}"
        f"1X2 {r['pro_local']:.1%}/{r['pro_empate']:.1%}/{r['pro_visita']:.1%}  → {favorito}"
    )


def main() -> None:
    consola_utf8()
    parser = argparse.ArgumentParser(description="LightGBM 1X2 (Fase 5c)")
    parser.add_argument("--liga", default="PD", help="Código de liga (PD/PL/SA/BL1/CL)")
    parser.add_argument("--todas", action="store_true", help="Las 5 ligas del MVP")
    parser.add_argument("--peores", type=int, default=0, help="Nº fallos caros a listar")
    parser.add_argument("--guardar", action="store_true", help="Evaluaciones LGBM → reales_vs_previsto")
    parser.add_argument("--vivas", action="store_true", help="Predicciones vivas LGBM → prediccion")
    args = parser.parse_args()

    from pipeline.config import LIGAS_MVP, SEASON

    ligas = list(LIGAS_MVP) if args.todas else [args.liga]

    filas_totales: list[dict] = []
    filas_base_totales: list[dict] = []
    saltados_totales = 0
    saltados_base_totales = 0
    ws_liga: dict[str, float] = {}

    for liga in ligas:
        filas_base, saltados_base = evaluar_liga(liga, SEASON)  # baseline, para comparar
        filas_lgbm, saltados, mejor_w, ll_w = evaluar_liga_lgbm(liga, SEASON)
        if not filas_lgbm:
            print(f"\n[{liga}] sin partidos FINISHED evaluables")
            continue

        _imprimir_resumen_liga(
            f"{liga} · walk-forward 2026",
            {
                NOMBRE_MODELO: (_agregar(filas_base), saltados_base),
                NOMBRE_MODELO_LGBM: (_agregar(filas_lgbm), saltados),
            },
        )
        print(
            f"  mezcla w={mejor_w:.2f} · log loss con mezcla {ll_w:.4f}"
            " (grid 0.00…1.00, paso 0.05)"
        )

        nombres = _nombres_equipos(
            sorted(
                {f["partido"].id_local for f in filas_lgbm}
                | {f["partido"].id_visitante for f in filas_lgbm}
            )
        )
        if args.peores > 0:
            _imprimir_peores(filas_lgbm, nombres, args.peores)

        filas_base_totales.extend(filas_base)
        filas_totales.extend(filas_lgbm)
        saltados_totales += saltados
        saltados_base_totales += saltados_base
        ws_liga[liga] = mejor_w

        if args.guardar:
            guardadas = _persistir(filas_lgbm, NOMBRE_MODELO_LGBM)
            print(f"  💾 {guardadas} evaluaciones {NOMBRE_MODELO_LGBM} en 'reales_vs_previsto'.")

    if filas_totales and len(ligas) > 1:
        _imprimir_resumen_liga(
            "TOTAL 5 LIGAS · walk-forward",
            {
                NOMBRE_MODELO: (_agregar(filas_base_totales), saltados_base_totales),
                NOMBRE_MODELO_LGBM: (_agregar(filas_totales), saltados_totales),
            },
        )

    if args.vivas:
        guardadas = 0
        for liga in ligas:
            historia = HistoriaLiga(liga, SEASON)
            with SessionLocal() as session:
                partidos = session.execute(_select_partidos(liga, SEASON)).scalars().all()
                pool = _pool_de_liga(historia, partidos)
                X = np.array([r["x"] for r in pool])
                y = np.array([r["y"] for r in pool])
                booster = lgb.train(
                    PARAMS, lgb.Dataset(X, label=y), num_boost_round=PARAMS["n_estimators"]
                )
                print(
                    f"\n────── {liga} · {NOMBRE_MODELO_LGBM} entrenado con {len(pool)}"
                    f" FINISHED · predicciones vivas ──────"
                )

                pendientes = _proximos(session, liga, SEASON, 999)
                if not pendientes:
                    print(f"[{liga}] sin partidos SCHEDULED/TIMED pendientes")
                    continue

                nombres = _nombres_equipos(
                    sorted({t for m in pendientes for t in (m.id_local, m.id_visitante)})
                )

                def _predecir_con_lgbm(
                    h,
                    id_local,
                    id_visitante,
                    fecha,
                    _booster=booster,
                    _w=ws_liga[liga],
                    _evidencia=len(pool),
                ):
                    fila = _fila_lgbm(_booster, h, id_local, id_visitante, fecha)
                    for c in ("local", "empate", "visita"):
                        fila[f"pro_{c}"] = _w * fila[f"pro_{c}"] + (1.0 - _w) / 3.0
                    fila["mezcla_uniforme"] = _w
                    fila["datos"] = _evidencia
                    return fila

                resultados, _ = predecir_y_guardar(
                    liga,
                    pendientes,
                    nombres,
                    guardar=True,
                    predecir_fn=_predecir_con_lgbm,
                    modelo=NOMBRE_MODELO_LGBM,
                )
                guardadas += len(resultados)
                for r in resultados[:3]:
                    print(" ", _fila_texto_1x2(r, nombres))

        print(
            f"\n💾 Persistidas {guardadas} predicciones ({NOMBRE_MODELO_LGBM}) en tabla 'prediccion'."
        )


if __name__ == "__main__":
    main()
