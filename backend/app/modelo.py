"""Modelo de equipo — baseline POISSON DOBLE (Fase 5).

Matemática (paso a paso sincera):
1. Parámetros LIGA hasta la fecha del partido (regla de oro walk-forward):
   μ_casa  = promedio de goles de los locales · μ_visita = promedio de los visitantes
2. Fuerza relativa por equipo (goles propios / goles promedio del rol):
   atk_l = goles_metidos_en_casa_local / μ_casa · dfn_v = goles_concedidos_fuera_visita / μ_casa
   atk_v = goles_metidos_fuera_visita / μ_visita · dfn_l = goles_concedidos_en_casa_local / μ_visita
3. Intensidades del partido:  λ_local = μ_casa · atk_l · dfn_v  ·  λ_visita = μ_visita · atk_v · dfn_l
4. P(marcador i-j) = Poisson(i | λ_local) · Poisson(j | λ_visita) sumando el grid 0..MAX.
   De ahí: P(local)/P(empate)/P(visita), over/under 2.5 y el marcador más probable.

Reglas del proyecto respetadas:
- Sin filtración: TODO se calcula con partidos con fecha < la del partido a predecir.
- Equipos sin historial en el rol (recién ascendidos): fuerza neutral = 1.0 (fallback documentado).
- Persistencia idempotente: una predicción "viva" por (partido, modelo) — delete+insert
  aprovechando la restricción UNIQUE de la tabla `prediccion`.

CLI:
    python -m backend.app.modelo                    # demo: imprime PD, próximos 3
    python -m backend.app.modelo --liga PL          # demo Premier
    python -m backend.app.modelo --todas --guardar  # calcula y GUARDA en Postgres
"""

from __future__ import annotations

import argparse
import math
from collections import defaultdict
from datetime import datetime

from sqlalchemy import delete as sa_delete

from .consola import consola_utf8
from .db import SessionLocal
from .features import HistoriaLiga
from .models import Prediccion

NOMBRE_MODELO = "poisson_doble"
MAX_GOLES = 8  # grid de marcadores 0..8 × 0..8 (suficiente para 99.9%)

# Protecciones de modelado (desviaciones del Poisson crudo, documentadas en CONTEXTO):
# 1) K_SHRINK: contracción de fuerzas hacia la media (1.0) según nº de partidos
#    evidenciados — muestras chiquitas (recién ascendidos, Champions con 3 fechas)
#    no pueden dominar la señal. Fuerza_final = 1 + (cruda - 1)·j/(j+K).
# 2) MIN/MAX_FUERZA: recorte de rangos plausibles de la fuerza tras contracción.
# 3) LAMBDA_MIN/MAX: cúpula de intensidad por partido (goles esperados razonables) —
#    el producto multiplicativo puede explotar si ambos factores son extremos.
K_SHRINK = 8
MIN_FUERZA, MAX_FUERZA = 0.4, 2.5
LAMBDA_MIN, LAMBDA_MAX = 0.2, 4.5
MU_MINIMO = 0.1  # piso de medias de liga (evita división por cero en arranque frío)


def _pmf_poisson(lam: float) -> list[float]:
    """P(X = k) para k = 0..MAX_GOLES con media λ (distribución de Poisson)."""
    return [math.exp(-lam) * lam**k / math.factorial(k) for k in range(MAX_GOLES + 1)]


def _encoger(cruda: float, j: int, k: int = K_SHRINK) -> float:
    """Aproxima la fuerza cruda a la media conforme j crece (contracción bayesiana simple)."""
    contraída = 1.0 + (cruda - 1.0) * (j / (j + k))
    return min(max(contraída, MIN_FUERZA), MAX_FUERZA)


def _cupir_lambda(lam: float) -> float:
    """Intensidad de goles esperados dentro de rangos realistas del fútbol."""
    return min(max(lam, LAMBDA_MIN), LAMBDA_MAX)


def probabilidades_1x2(
    pmf_local: list[float],
    pmf_visita: list[float],
    peso=None,
) -> dict:
    """Grid de marcadores (0..MAX)² → distribución completa 1X2.

    `peso(i, j)` (opcional) repondera cada celda — es la puerta de entrada de
    Dixon-Coles (modelo_dc.py): la Poisson independiente pesa mal los marcadores
    bajos (0-0/1-0/0-1/1-1). Con peso=None sirve el Poisson doble puro.
    El grid trunca las colas (marcadores 9+) → renormalizamos repartiendo esa masa.
    """
    pro_local = pro_empate = pro_visita = 0.0
    pro_under25 = 0.0
    mejor_marca = (0, 0)
    mejor_pro = 0.0
    for i, pl in enumerate(pmf_local):
        for j, pv in enumerate(pmf_visita):
            p = pl * pv
            if peso is not None:
                p *= peso(i, j)
            if i > j:
                pro_local += p
            elif i == j:
                pro_empate += p
            else:
                pro_visita += p
            if i + j <= 2:
                pro_under25 += p
            if p > mejor_pro:
                mejor_pro, mejor_marca = p, (i, j)

    masa_grid = pro_local + pro_empate + pro_visita
    pro_local /= masa_grid
    pro_empate /= masa_grid
    pro_visita /= masa_grid
    pro_under25 /= masa_grid

    total = pro_local + pro_empate + pro_visita
    assert abs(total - 1.0) < 1e-9, f"1X2 no suma 1 tras renormalizar: {total!r}"  # guardián

    return {
        "pro_local": pro_local,
        "pro_empate": pro_empate,
        "pro_visita": pro_visita,
        "pro_over25": 1.0 - pro_under25,
        "pro_under25": pro_under25,
        "marcador_estimado": f"{mejor_marca[0]}-{mejor_marca[1]}",
        "masa_grid": masa_grid,
    }


class ParametrosLiga:
    """Fuerzas de ataque/ defensa + medias de liga, calculadas SOLO con partidos < fecha."""

    def __init__(self, historia: HistoriaLiga) -> None:
        self.historia = historia

    def calcular(self, hasta: datetime) -> dict:
        mu_casa_goles = 0.0
        mu_visita_goles = 0.0
        n = 0
        gf_casa: dict[int, int] = defaultdict(int)
        gc_casa: dict[int, int] = defaultdict(int)
        j_casa: dict[int, int] = defaultdict(int)
        gf_fuera: dict[int, int] = defaultdict(int)
        gc_fuera: dict[int, int] = defaultdict(int)
        j_fuera: dict[int, int] = defaultdict(int)

        for r in self.historia.partidos:
            if r.fecha >= hasta:
                break  # partidos ordenados por fecha → puedo cortar temprano
            mu_casa_goles += r.goles_local
            mu_visita_goles += r.goles_visitante
            n += 1
            gf_casa[r.id_local] += r.goles_local
            gc_casa[r.id_local] += r.goles_visitante
            j_casa[r.id_local] += 1
            gf_fuera[r.id_visitante] += r.goles_visitante
            gc_fuera[r.id_visitante] += r.goles_local
            j_fuera[r.id_visitante] += 1

        if n == 0:
            raise ValueError("No hay partidos terminados antes de esa fecha (¿fecha inválida?).")

        mu_casa = mu_casa_goles / n
        mu_visita = mu_visita_goles / n
        # Piso defensivo: en los primeros partidos los μ pueden ser 0.0
        # (p. ej., único partido previo con visita sin marcar) → nunca dividir por 0.
        # Con la contracción K_SHRINK activa, las fuerzas con j pequeño están
        # pegadas a 1.0, así que el piso no genera λ explosivos.
        mu_casa = max(mu_casa, MU_MINIMO)
        mu_visita = max(mu_visita, MU_MINIMO)
        todos = set(gf_casa) | set(gf_fuera) | set(gc_casa) | set(gc_fuera)

        atk_casa: dict[int, float] = {}
        dfn_casa: dict[int, float] = {}
        atk_fuera: dict[int, float] = {}
        dfn_fuera: dict[int, float] = {}
        for eq in todos:
            # ataque local: metidos en casa vs media de liga; defensa local: concedidos vs μ_visita
            # (cada fuerza se CONTRAE hacia 1.0 según su propio j: j_casa o j_fuera)
            atk_casa[eq] = _encoger((gf_casa[eq] / j_casa[eq]) / mu_casa, j_casa[eq]) if j_casa[eq] else 1.0
            dfn_casa[eq] = _encoger((gc_casa[eq] / j_casa[eq]) / mu_visita, j_casa[eq]) if j_casa[eq] else 1.0
            atk_fuera[eq] = _encoger((gf_fuera[eq] / j_fuera[eq]) / mu_visita, j_fuera[eq]) if j_fuera[eq] else 1.0
            dfn_fuera[eq] = _encoger((gc_fuera[eq] / j_fuera[eq]) / mu_casa, j_fuera[eq]) if j_fuera[eq] else 1.0

        return {
            "mu_casa": mu_casa,
            "mu_visita": mu_visita,
            "partidos_hasta": n,
            "atk_casa": atk_casa,
            "dfn_casa": dfn_casa,
            "atk_fuera": atk_fuera,
            "dfn_fuera": dfn_fuera,
        }


def predecir(
    historia: HistoriaLiga,
    id_local: int,
    id_visitante: int,
    fecha: datetime,
) -> dict:
    """Genera la predicción completa del enfrentamiento (sin persistir)."""
    params = ParametrosLiga(historia).calcular(fecha)

    # Cúpula de λ: el producto multiplicativo puede explotar si atk y dfn son
    # extremos a la vez (Champions con 3 fechas) → se acopla a lo realista.
    # Equipos que aún no han jugado (arranque frío) → fuerza neutral 1.0.
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

    pmf_l = _pmf_poisson(lam_local)
    pmf_v = _pmf_poisson(lam_visita)
    grid = probabilidades_1x2(pmf_l, pmf_v)

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
        "datos": params["partidos_hasta"],  # nº de partidos usados como evidencia
    }


def predecir_y_guardar(
    liga: str,
    partidos_pendientes: list,
    nombres: dict[int, str],
    guardar: bool = False,
    predecir_fn=None,
    modelo: str = NOMBRE_MODELO,
) -> tuple[list[dict], int]:
    """Predice una lista de partidos (ya filtrados por liga) y opcionalmente los persiste.

    `predecir_fn` permite inyectar otra variante (p. ej. Dixon-Coles con su ρ por liga);
    por defecto usa el baseline `predecir()`.
    """
    predecir_el = predecir_fn or predecir
    historia = HistoriaLiga(liga, partidos_pendientes[0].temporada if partidos_pendientes else 0)
    resultados: list[dict] = []
    for p in partidos_pendientes:
        pr = predecir_el(historia, p.id_local, p.id_visitante, p.utc_date)
        pr["partido"] = p
        resultados.append(pr)

    if guardar:
        with SessionLocal.begin() as session:
            # idempotencia: la predicción "viva" única por (partido, modelo)
            session.execute(
                sa_delete(Prediccion).where(
                    Prediccion.partido_id_api.in_(
                        [r["partido"].id_api for r in resultados]
                    ),
                    Prediccion.modelo == modelo,
                )
            )
            for r in resultados:
                p = r["partido"]
                session.add(
                    Prediccion(
                        partido_id_api=p.id_api,
                        modelo=modelo,
                        prob_local=r["pro_local"],
                        prob_empate=r["pro_empate"],
                        prob_visita=r["pro_visita"],
                        goles_esperados_local=r["lam_local"],
                        goles_esperados_visita=r["lam_visita"],
                        marcador_estimado=r["marcador_estimado"],
                        prob_over25=r["pro_over25"],
                        prob_under25=r["pro_under25"],
                        datos={
                            "liga": p.liga,
                            "fecha_utc": p.utc_date.isoformat(),
                            "id_local": p.id_local,
                            "id_visitante": p.id_visitante,
                            "mu_casa": r["mu_casa"],
                            "mu_visita": r["mu_visita"],
                            "atk_casa_local": r["atk_casa_local"],
                            "dfn_fuera_visita": r["dfn_fuera_visita"],
                            "atk_fuera_visita": r["atk_fuera_visita"],
                            "dfn_casa_local": r["dfn_casa_local"],
                            "partidos_evidencia": r["datos"],
                            "masa_grid": r["masa_grid"],
                            "rho": r.get("rho"),  # solo Dixon-Coles la lleva
                        },
                    )
                )
    return resultados, len(resultados)


def _fila_texto(r: dict, nombres: dict[int, str]) -> str:
    p = r["partido"]
    favorito = (
        nombres[p.id_local]
        if r["pro_local"] == max(r["pro_local"], r["pro_empate"], r["pro_visita"])
        else nombres[p.id_visitante]
        if r["pro_visita"] >= r["pro_empate"]
        else "EMPATE"
    )
    return (
        f"{p.utc_date:%m-%d} {nombres[p.id_local]:<26}{nombres[p.id_visitante]:<26}"
        f"λ {r['lam_local']:.2f}-{r['lam_visita']:.2f}  "
        f"1X2 {r['pro_local']:.1%}/{r['pro_empate']:.1%}/{r['pro_visita']:.1%}  "
        f"O2.5 {r['pro_over25']:.1%}  {r['marcador_estimado']}  → {favorito}"
    )


def main() -> None:
    consola_utf8()
    parser = argparse.ArgumentParser(description="Predicciones Poisson doble (Fase 5)")
    parser.add_argument("--liga", default="PD", help="Código de liga (PD/PL/SA/BL1/CL)")
    parser.add_argument("--todas", action="store_true", help="Tomar las 5 ligas del MVP")
    parser.add_argument("--prox", type=int, default=3, help="Nº próximos partidos por liga")
    parser.add_argument("--guardar", action="store_true", help="Persistir en tabla prediccion")
    args = parser.parse_args()

    from pipeline.config import LIGAS_MVP, SEASON

    ligas = list(LIGAS_MVP) if args.todas else [args.liga]

    with SessionLocal() as session:
        from .features import _nombres_equipos, _proximos

        guardadas = 0
        for liga in ligas:
            pendientes = _proximos(session, liga, SEASON, args.prox)
            if not pendientes:
                print(f"[{liga}] sin partidos SCHEDULED/TIMED pendientes")
                continue
            nombres = _nombres_equipos(
                sorted({t for m in pendientes for t in (m.id_local, m.id_visitante)})
            )
            print(f"\n────── {liga} · temporada {SEASON} · próximos {len(pendientes)} ────")
            resultados, _ = predecir_y_guardar(liga, pendientes, nombres, args.guardar)
            guardadas += len(resultados) if args.guardar else 0
            for r in resultados:
                print(" ", _fila_texto(r, nombres))

        if args.guardar:
            print(f"\n💾 Persistidas {guardadas} predicciones ({NOMBRE_MODELO}) en tabla 'prediccion'.")


if __name__ == "__main__":
    main()
