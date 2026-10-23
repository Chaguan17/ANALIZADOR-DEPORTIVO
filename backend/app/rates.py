"""Núcleo compartido de los modelos de ESTADÍSTICAS por equipo-partido (Fases 15-16).

Los tres dominios nuevos (tarjetas, tiros, cornes) comparten la misma
maquinaria, que vive aquí una sola vez:

- TASA POR EQUIPO con shrinkage hacia la media de la liga
  ``(totales + k·media) / (partidos + k)`` — la misma idea de regularización
  bayesiana que ``K_SHRINK`` en modelo.py (goles), aquí en forma de rate.
- POISSON para el total del partido: λ del partido = suma de las tasas de
  ambos equipos, y P(over/under línea) saliendo de la PMF truncada y
  renormalizada (mismo trato que modelo.py).
- CALIDAD WALK-FORWARD: para cada partido jugado se predice SOLO con los
  partidos estrictamente anteriores (regla de oro del proyecto) y se mide
  acierto over/under por línea + MAE de λ.
- Diferencia honesta con modelo.py: aquí NO hay factor local/visitante.
  Con ~10 partidos por equipo en la temporada joven, dividir la muestra por
  rol la dejaría en ~5: la regla "todo lo medible se mide; lo que no, se
  declara" gana y la tasa se calcula sobre el total del equipo. La media de
  referencia también es la del evento por equipo en la liga.

`prediccion` / `reales_vs_previsto` NO se tocan: estos modelos se calculan
on-request, sin tablas nuevas y sin cron extra.
"""

from __future__ import annotations

from collections.abc import Callable
from math import exp

K_TASA = 6  # pseudo-partidos de "prior" hacia la media de liga
TECHO_POISSON = 60  # cota alta de eventos por partido (tiros máx ~40: sobra)


# ───────────────────────────── tasas y Poisson ──────────────────────────────


def tasa_encogida(totales: float, partidos: int, media_liga: float, k: int = K_TASA) -> float:
    """Tasa por partido con shrinkage: ``(totales + k·media) / (partidos + k)``.

    Con 0 partidos devuelve la media de liga (equipo debutante = prior puro).
    """
    if partidos + k <= 0:
        return media_liga
    return (totales + k * media_liga) / (partidos + k)


def pmf_poisson(lam: float, techo: int = TECHO_POISSON) -> list[float]:
    """PMF de Poisson(λ) en k=0..techo, renormalizada (cola cortada)."""
    if lam <= 0:
        pmf = [1.0] + [0.0] * techo
        return pmf
    pmf: list[float] = []
    p = exp(-lam)
    pmf.append(p)
    for k in range(1, techo + 1):
        p = p * lam / k
        pmf.append(p)
    total = sum(pmf)
    if total <= 0:  # no debería pasar, pero la honestidad primero
        return [1.0] + [0.0] * techo
    return [x / total for x in pmf]


def prob_over(lam: float, linea: float) -> float:
    """P(total eventos > línea) con Poisson(λ). El total es entero: la línea
    .5 separa limpia (over ⇔ k ≥ ceil), under = −over."""
    pmf = pmf_poisson(lam)
    corte = int(linea)  # 2.5 → under = P(k ≤ 2); 23.5 → P(k ≤ 23)
    under = sum(pmf[: corte + 1])
    return max(0.0, min(1.0, 1.0 - under))


def prob_under(lam: float, linea: float) -> float:
    return max(0.0, min(1.0, 1.0 - prob_over(lam, linea)))


# ─────────────────────────── tasas por equipo (historia) ────────────────────

Extractor = Callable[[dict], list[tuple[int, float]]]
"""extraer(fila) → [(equipo_id, eventos_del_equipo_en_ese_partido), ...]"""


def tasas_por_equipo(
    historia: list[dict],
    extraer: Extractor,
    k: int = K_TASA,
) -> dict[int, float]:
    """{equipo_id: tasa_encogida} con la media de liga calculada de la MISMA
    historia (por aparición de equipo, no por partido).

    Equipos sin partidos en la historia no aparecen en el dict (el juego
    llamador decide el fallback honesto).
    """
    totales: dict[int, float] = {}
    apariciones: dict[int, int] = {}
    total_eventos = 0.0
    total_apariciones = 0
    for fila in historia:
        for equipo_id, eventos in extraer(fila):
            totales[equipo_id] = totales.get(equipo_id, 0.0) + eventos
            apariciones[equipo_id] = apariciones.get(equipo_id, 0) + 1
        total_eventos += sum(e for _, e in extraer(fila))
        total_apariciones += len(extraer(fila))
    media_liga = (total_eventos / total_apariciones) if total_apariciones else 0.0
    return {
        equipo_id: tasa_encogida(totales[equipo_id], apariciones[equipo_id], media_liga, k)
        for equipo_id in totales
    }


# ────────────────────────────── calidad walk-forward ────────────────────────


def evaluar_walk_forward(
    filas: list[dict],
    lam_de: Callable[[list[dict], dict], float | None],
    lineas: tuple[float, ...],
) -> dict:
    """Calidad honesta O/U por línea + MAE de λ, SOLO con historia previa.

    filas: [{fecha: datetime, ...}] — se ordenan por fecha antes de iterar.
    lam_de(historia, fila) → λ del total (o None: fila no evaluable, p.ej.
    algún equipo debutante con la muestra recién abierta; se cuentan como
    'omisiones' y aparecen en el informe).
    Devuelve:
    {\"lineas\": {\"2.5\": {\"evaluados\", \"aciertos\", \"accuracy\", \"mae\"}},
     \"omisiones\": n}
    """
    orden = sorted(filas, key=lambda f: (f["fecha"], f.get("partido", 0)))
    bruto = {str(linea): {"evaluados": 0, "aciertos": 0, "error": 0.0} for linea in lineas}
    omisiones = 0
    for i, fila in enumerate(orden):
        historia = orden[:i]  # regla de oro: nada de la fila misma ni del futuro
        lam = lam_de(historia, fila)
        if lam is None:
            omisiones += 1
            continue
        for linea in lineas:
            r = bruto[str(linea)]
            r["evaluados"] += 1
            if (prob_over(lam, linea) > 0.5) == (fila["real"] > linea):
                r["aciertos"] += 1
            r["error"] += abs(lam - fila["real"])
    lineas_salida: dict[str, dict] = {}
    for linea in lineas:
        r = bruto[str(linea)]
        n = r["evaluados"]
        lineas_salida[str(linea)] = {
            "evaluados": n,
            "aciertos": r["aciertos"],
            "accuracy": (r["aciertos"] / n) if n else None,
            "mae": (r["error"] / n) if n else None,
        }
    return {"omisiones": omisiones, "lineas": lineas_salida}


# ─────────────────────────── propensos por jugador ──────────────────────────


def mejor_jugadores(
    contados: dict[str, dict],
    min_apariciones: int,
    top: int,
    numerador: str,
) -> list[dict]:
    """Filtra y ordena la tabla de jugadores por tasa de `numerador`.

    contados: {nombre: {…contadores…, "apariciones": n}} ya agregados.
    A cada fila se le añade "tasa" = numerador/apariciones (None si corre con
    menos apariciones que el mínimo) y se ordena: primero los que tienen tasa
    (mayor tasa primero), después los excluidos ordenados por volumen.
    """
    filas: list[dict] = []
    for nombre, c in contados.items():
        apariciones = c.get("apariciones", 0)
        eventos = c.get(numerador, 0)
        fila = dict(c)
        fila["apariciones"] = apariciones
        fila["tasa"] = (
            round(eventos / apariciones, 3) if apariciones >= min_apariciones else None
        )
        filas.append(fila)
    filas.sort(
        key=lambda f: (
            f["tasa"] is None,          # los sin tasa al final
            -(f["tasa"] or 0.0),        # mayor tasa primero
            -f.get(numerador, 0),       # a igual tasa, más volumen primero
        )
    )
    return filas[:top]


__all__ = [
    "K_TASA",
    "TECHO_POISSON",
    "evaluar_walk_forward",
    "mejor_jugadores",
    "pmf_poisson",
    "prob_over",
    "prob_under",
    "tasa_encogida",
    "tasas_por_equipo",
]
