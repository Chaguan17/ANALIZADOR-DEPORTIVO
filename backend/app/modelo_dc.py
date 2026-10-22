"""Dixon-Coles — FASE 5b: corrección de marcadores bajos sobre el Poisson doble.

Idea (Dixon & Coles, 1997): la Poisson independiente pesa mal los marcadores
bajos — el fútbol real devuelve MÁS 0-0 y 1-1 de lo que propone el producto
Po(i)·Po(j) (los empates con pocos goles se tragan el reloj) y algo menos de
1-0/0-1. La corrección multiplica esas 4 celdas del grid por un factor τ:

    τ(0,0) = 1 − λ·μ·ρ       τ(0,1) = 1 + λ·ρ
    τ(1,0) = 1 + μ·ρ         τ(1,1) = 1 − ρ
    τ(cualquier otra celda) = 1

Convención de signo: ρ NEGATIVO sube las celdas 0-0 y 1-1 y baja 1-0/0-1
(el hallazgo empírico clásico: en ligas europeas el MLE suele caer en
ρ ≈ −0.03 … −0.12). Cualquier τ que trate de volverse negativo se clampa a 0.0
y la renormalización del helper reparte esa masa — el guardián "1X2 ≈ 1" vivo.

Qué NO cambia: las intensidades λ y μ son EXACTAMENTE las del baseline
(mismas fuerzas contraídas, mismo piso, misma cúpula) — Dixon-Coles solo
repondera el grid con τ. Y hay un INVARIANTE algebraico (comprobado en esta
sesión al 15º decimal): como P(1|λ)·P(1|μ) = λμ·P(0|λ)·P(0|μ), P(1|λ)·P(0|μ) =
λ·w00 y P(0|λ)·P(1|μ) = μ·w00, la variación de masa total es
ρ·(−λμ·w00 + λ·w01 + μ·w10 − w11) = ρ·(−λμw00 + λμw00 + λμw00 − λμw00) = 0.
Las 4 celdas τ viven todas DENTRO del bloque under-2.5 y conservan su masa →
τ REORDENA la 1X2 pero NO altera las probabilidades over/under 2.5.
La mejora del O2.5 (débil en PL/SA según Fase 7) vendrá por otro camino.

Matiz honesto del ajuste de ρ (documentado en CONTEXTO §3):
- λ/μ ya son walk-forward (sin filtración de futuro).
- ρ se ajusta por liga con grid-search minimizando el log loss de la MISMA
  evaluación con la que comparamos (matiz in-sample de 1 solo parámetro:
  riesgo de sobreajuste mínimo, aceptado y documentado).

CLI:
    python -m backend.app.modelo_dc --liga PD           # demo comparación
    python -m backend.app.modelo_dc --todas --guardar   # evaluaciones DC → reales_vs_previsto
    python -m backend.app.modelo_dc --todas --vivas     # predicciones vivas DC → prediccion
"""

from __future__ import annotations

import argparse
import math
from functools import partial

from .consola import consola_utf8
from .db import SessionLocal
from .evaluacion import (
    EPSILON,
    _agregar,
    _imprimir_peores,
    _persistir,
    evaluar_liga,
)
from .features import _nombres_equipos, _proximos
from .modelo import (
    NOMBRE_MODELO,
    ParametrosLiga,
    _cupir_lambda,
    _fila_texto,
    _pmf_poisson,
    predecir_y_guardar,
    probabilidades_1x2,
)

NOMBRE_MODELO_DC = "poisson_dc"
# ρ por liga: grid-search −0.300 … 0.050 en pasos de 0.0125 (29 candidatos)
# (ampliado porque LaLiga marcaba el límite interior −0.200 en la primera prueba)
RHO_GRID: list[float] = [round(-0.300 + i * 0.0125, 4) for i in range(29)]


def tau(x: int, y: int, lam: float, mu: float, rho: float) -> float:
    """Peso τ de Dixon-Coles para la celda (x goles local, y goles visita).

    lam = λ del local, mu = λ del visitante. Clamp a 0.0 por celda: con λ
    extremos y ρ positivo el término 1 − λ·μ·ρ podría volverse negativo.
    """
    if x == 0 and y == 0:
        return max(1.0 - lam * mu * rho, 0.0)
    if x == 0 and y == 1:
        return max(1.0 + lam * rho, 0.0)
    if x == 1 and y == 0:
        return max(1.0 + mu * rho, 0.0)
    if x == 1 and y == 1:
        return max(1.0 - rho, 0.0)
    return 1.0


def _probabilidades_dc(lam_local: float, lam_visita: float, rho: float) -> dict:
    """Grid 1X2/over-under del Poisson doble reponderado con τ(rho)."""
    pmf_l = _pmf_poisson(lam_local)
    pmf_v = _pmf_poisson(lam_visita)
    return probabilidades_1x2(
        pmf_l,
        pmf_v,
        peso=lambda i, j: tau(i, j, lam_local, lam_visita, rho),
    )


def predecir_dc(
    historia,
    id_local: int,
    id_visitante: int,
    fecha,
    rho: float = -0.05,
) -> dict:
    """Predicción Dixon-Coles: mismas fuerzas que el baseline, grid reponderado.

    Devuelve el mismo shape de dict que `predecir()` + "rho".
    """
    params = ParametrosLiga(historia).calcular(fecha)

    lam_local = _cupir_lambda(
        params["mu_casa"]
        * params["atk_casa"].get(id_local, 1.0)
        * params["dfn_fuera"].get(id_visitante, 1.0)
    )
    lam_visita = _cupir_lambda(
        params["mu_visita"]
        * params["atk_fuera"].get(id_visitante, 1.0)
        * params["dfn_casa"].get(id_local, 1.0)
    )

    grid = _probabilidades_dc(lam_local, lam_visita, rho)

    return {
        "lam_local": lam_local,
        "lam_visita": lam_visita,
        **grid,
        "mu_casa": params["mu_casa"],
        "mu_visita": params["mu_visita"],
        "atk_casa_local": params["atk_casa"].get(id_local, 1.0),
        "dfn_fuera_visita": params["dfn_fuera"].get(id_visitante, 1.0),
        "atk_fuera_visita": params["atk_fuera"].get(id_visitante, 1.0),
        "dfn_casa_local": params["dfn_casa"].get(id_local, 1.0),
        "datos": params["partidos_hasta"],
        "rho": rho,
    }


def ajustar_rho(filas_base: list[dict]) -> tuple[float, float]:
    """Grid-search de ρ para una liga: minimiza el log loss walk-forward.

    Devuelve (mejor_rho, log_loss_con_ese_rho).
    """
    if not filas_base:
        return 0.0, 0.0

    mejor_rho = 0.0
    mejor_ll = math.inf
    for rho in RHO_GRID:
        ll_total = 0.0
        for f in filas_base:
            grid = _probabilidades_dc(f["lam_local"], f["lam_visita"], rho)
            p_real = grid["pro_" + f["real"]]
            ll_total += -math.log(max(p_real, EPSILON))
        ll = ll_total / len(filas_base)
        if ll < mejor_ll:
            mejor_rho, mejor_ll = rho, ll
    return mejor_rho, mejor_ll


def _filas_dc_de(filas_base: list[dict], rho: float) -> list[dict]:
    """Recomputa las filas de evaluación con τ(rho) — mismas λ, nuevos pesos.

    Partimos de las filas del baseline (que ya traen partido, λ y resultado)
    para GARANTIZAR que la única diferencia es el reponderado del grid.
    """
    filas: list[dict] = []
    for f in filas_base:
        p = f["partido"]
        grid = _probabilidades_dc(f["lam_local"], f["lam_visita"], rho)
        probs = {
            "local": float(grid["pro_local"]),
            "empate": float(grid["pro_empate"]),
            "visita": float(grid["pro_visita"]),
        }
        real = f["real"]
        favorito = max(probs, key=probs.get)
        filas.append(
            {
                "partido": p,
                "probs": probs,
                "real": real,
                "favorito": favorito,
                "acierto": favorito == real,
                "log_loss": -math.log(max(probs[real], EPSILON)),
                "brier": sum(
                    (probs[c] - (1.0 if c == real else 0.0)) ** 2 for c in probs
                ),
                "lam_local": f["lam_local"],
                "lam_visita": f["lam_visita"],
                "over_real": f["over_real"],
                "acierto_o25": (float(grid["pro_over25"]) > 0.5) == f["over_real"],
                "brier_o25": (
                    float(grid["pro_over25"]) - (1.0 if f["over_real"] else 0.0)
                ) ** 2,
                "mae_goles": f["mae_goles"],  # λ sin cambios → mismo error de goles
                "rho": rho,
            }
        )
    return filas


# (clave, formato valor, formato Δ, etiqueta, menor es mejor)
_METRICAS = [
    ("accuracy", "{:.1%}", "{:+.1%}", "Accuracy 1X2", False),
    ("log_loss", "{:.4f}", "{:+.4f}", "Log loss", True),
    ("brier", "{:.4f}", "{:+.4f}", "Brier 1X2", True),
    ("accuracy_o25", "{:.1%}", "{:+.1%}", "Accuracy O2.5", False),
    ("brier_o25", "{:.4f}", "{:+.4f}", "Brier O2.5", True),
    ("mae_goles", "{:.3f}", "{:+.3f}", "MAE goles", True),
]


def _imprimir_comparacion(
    titulo: str,
    agg_base: dict,
    agg_dc: dict,
    rho: float | None = None,
    ll_rho: float | None = None,
    n: int = 0,
    saltados: int = 0,
) -> None:
    print(f"\n────── {titulo} · {NOMBRE_MODELO} vs {NOMBRE_MODELO_DC} ──────")
    print(f"  Partidos: {n}   (saltados calentamiento: {saltados})")
    if rho is not None:
        print(
            f"  ρ ajustada: {rho:+.4f}   log loss búsqueda: {ll_rho:.4f}"
            f"   (baseline: {agg_base['log_loss']:.4f})"
        )
    for clave, fmt_val, fmt_delta, nombre, menor_es_mejor in _METRICAS:
        vb, vd = agg_base[clave], agg_dc[clave]
        delta = vd - vb
        mejor = delta < 0 if menor_es_mejor else delta > 0
        imperceptible = abs(delta) < 1e-12
        flecha = "➖" if imperceptible else ("✅" if mejor else "❌")
        print(
            f"  {nombre:<16}{fmt_val.format(vb):>9} → {fmt_val.format(vd):>9}"
            f"   Δ {fmt_delta.format(delta)} {flecha}"
        )


def main() -> None:
    consola_utf8()
    parser = argparse.ArgumentParser(description="Dixon-Coles (Fase 5b)")
    parser.add_argument("--liga", default="PD", help="Código de liga (PD/PL/SA/BL1/CL)")
    parser.add_argument("--todas", action="store_true", help="Las 5 ligas del MVP")
    parser.add_argument("--peores", type=int, default=0, help="Nº fallos caros DC a listar")
    parser.add_argument("--guardar", action="store_true", help="Evaluaciones DC → reales_vs_previsto")
    parser.add_argument("--vivas", action="store_true", help="Predicciones vivas DC → prediccion")
    args = parser.parse_args()

    from pipeline.config import LIGAS_MVP, SEASON

    ligas = list(LIGAS_MVP) if args.todas else [args.liga]

    rhos: dict[str, float] = {}
    filas_base_totales: list[dict] = []
    filas_dc_totales: list[dict] = []
    saltados_totales = 0

    for liga in ligas:
        filas_base, saltados = evaluar_liga(liga, SEASON)
        if not filas_base:
            print(f"\n[{liga}] sin partidos FINISHED evaluables")
            continue

        agg_base = _agregar(filas_base)
        rho, ll_rho = ajustar_rho(filas_base)
        rhos[liga] = rho
        filas_dc = _filas_dc_de(filas_base, rho)
        agg_dc = _agregar(filas_dc)

        nombres = _nombres_equipos(
            sorted(
                {f["partido"].id_local for f in filas_base}
                | {f["partido"].id_visitante for f in filas_base}
            )
        )
        _imprimir_comparacion(
            liga, agg_base, agg_dc, rho, ll_rho, len(filas_base), saltados
        )
        if args.peores > 0:
            _imprimir_peores(filas_dc, nombres, args.peores)

        filas_base_totales.extend(filas_base)
        filas_dc_totales.extend(filas_dc)
        saltados_totales += saltados

        if args.guardar:
            guardadas = _persistir(filas_dc, NOMBRE_MODELO_DC)
            print(f"  💾 {guardadas} evaluaciones {NOMBRE_MODELO_DC} en 'reales_vs_previsto'.")

    if filas_dc_totales and len(ligas) > 1:
        agg_b = _agregar(filas_base_totales)
        agg_d = _agregar(filas_dc_totales)
        _imprimir_comparacion(
            "TOTAL 5 LIGAS", agg_b, agg_d, n=len(filas_dc_totales), saltados=saltados_totales
        )

    if args.vivas and rhos:
        with SessionLocal() as session:
            guardadas = 0
            for liga in ligas:
                if liga not in rhos:
                    continue
                pendientes = _proximos(session, liga, SEASON, 999)
                if not pendientes:
                    print(f"\n[{liga}] sin partidos SCHEDULED/TIMED pendientes")
                    continue
                nombres = _nombres_equipos(
                    sorted({t for m in pendientes for t in (m.id_local, m.id_visitante)})
                )
                print(
                    f"\n────── {liga} · predicciones vivas DC · ρ={rhos[liga]:+.4f} ──────"
                )
                resultados, _ = predecir_y_guardar(
                    liga,
                    pendientes,
                    nombres,
                    guardar=True,
                    predecir_fn=partial(predecir_dc, rho=rhos[liga]),
                    modelo=NOMBRE_MODELO_DC,
                )
                guardadas += len(resultados)
                for r in resultados[:3]:  # muestra 3 por liga, el resto va a la BD
                    print(" ", _fila_texto(r, nombres))
            print(
                f"\n💾 Persistidas {guardadas} predicciones ({NOMBRE_MODELO_DC}) en tabla 'prediccion'."
            )


if __name__ == "__main__":
    main()
