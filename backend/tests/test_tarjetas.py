"""Pruebas del modelo de tarjetas y su núcleo rates (Fase 15) — todo puro.

La matemática se comprueba a mano: shrinkage (totales + k·media)/(n + k),
Poisson renormalizada, walk-forward con omisión de debutantes, conteo de
apariciones por jugador (rosters unidos a keyEvents) y los rankings.
"""

from datetime import datetime, timezone

from backend.app.rates import (
    evaluar_walk_forward,
    mejor_jugadores,
    pmf_poisson,
    prob_over,
    prob_under,
    tasa_encogida,
    tasas_por_equipo,
)
from backend.app.tarjetas import (
    bloques_de,
    contados_por_jugador,
    equipos_tarjetas,
    extraer_tarjetas,
    lam_de,
    prediccion_de_filas,
    propensos_equipo,
    total_de,
)

ESTA_F = datetime(2026, 8, 15, 19, 0, tzinfo=timezone.utc)
OTRA_F = datetime(2026, 8, 22, 19, 0, tzinfo=timezone.utc)


def _bloque(amarillas: int, rojas: int, por_jugador: list[dict] | None = None) -> dict:
    return {"amarillas": amarillas, "rojas": rojas, "fuente": "espn",
            "por_jugador": por_jugador or []}


def _jug(nombre: str) -> dict:
    return {"nombre": nombre, "titular": True, "entra": False}


def _fila(
    pid: int,
    fecha: datetime,
    local: int,
    visitante: int,
    blk_l: dict | None = None,
    blk_v: dict | None = None,
    jug_l: list[dict] | None = None,
    jug_v: list[dict] | None = None,
) -> dict:
    datos_l = {"tarjetas": blk_l, "espn": {"alineacion": jug_l or []}} if blk_l is not None else {}
    datos_v = {"tarjetas": blk_v, "espn": {"alineacion": jug_v or []}} if blk_v is not None else {}
    return {
        "fecha": fecha,
        "partido": pid,
        "local": local,
        "visitante": visitante,
        "datos_l": datos_l,
        "datos_v": datos_v,
    }


# ────────────────────────────── núcleo rates ────────────────────────────────


def test_tasa_encogida_matematica_y_debutante():
    assert tasa_encogida(3, 1, 2.5) == (3 + 6 * 2.5) / 7
    assert tasa_encogida(0, 0, 2.5) == 2.5  # sin partidos = prior de liga
    assert tasa_encogida(10, 10, 1.0) == (10 + 6) / 16


def test_pmf_poisson_y_over_under():
    assert pmf_poisson(0)[0] == 1.0
    assert abs(sum(pmf_poisson(4.6)) - 1.0) < 1e-9
    lam = 4.0
    over25 = prob_over(lam, 2.5)
    # P(k ≤ 2 | λ=4) = e⁻⁴(1 + 4 + 8) = 0.2381033… ⇒ over = 0.7618967…
    assert abs(over25 - (1 - 0.2381033068)) < 1e-6
    assert abs(prob_under(lam, 2.5) + over25 - 1.0) < 1e-9
    assert prob_over(0.0, 2.5) == 0.0
    # la línea .5 es inclusive con el corte: over 3.5 = P(k ≥ 4)
    assert abs(prob_over(lam, 3.5) - 0.5665298791) < 1e-6


def test_tasas_por_equipo_con_media_de_la_misma_historia():
    historia = [
        {"local": 1, "visitante": 2, "tar_l": 3.0, "tar_v": 2.0},
    ]

    def extraer(fila: dict) -> list[tuple[int, float]]:
        return [(fila["local"], fila["tar_l"]), (fila["visitante"], fila["tar_v"])]

    tasas = tasas_por_equipo(historia, extraer)
    # media de liga = (3+2)/2 apariciones = 2.5; cada equipo encoge con SU total
    assert tasas[1] == (3 + 6 * 2.5) / 7
    assert tasas[2] == (2 + 6 * 2.5) / 7


def test_evaluar_walk_forward_omite_debutante_y_cuenta():
    filas = [
        {"fecha": ESTA_F, "partido": 1, "local": 1, "visitante": 2, "real": 5.0},
        {"fecha": OTRA_F, "partido": 2, "local": 1, "visitante": 2, "real": 4.0},
    ]

    def lam_de(historia: list[dict], fila: dict) -> float | None:
        if not historia:
            return None  # debutante
        return 2.0 * ((3 + 6 * 2.5) / 7)  # 36/7 ≈ 5.14 con la media del primer juego

    calidad = evaluar_walk_forward(filas, lam_de, (4.5,))
    assert calidad["omisiones"] == 1
    r = calidad["lineas"]["4.5"]
    assert r["evaluados"] == 1
    # λ≈5.14 → P(over 4.5) ≈ 0.589 > 0.5 predice over; real 4 < 4.5 falla
    assert r["aciertos"] == 0
    assert abs(r["mae"] - abs(36 / 7 - 4)) < 1e-6


def test_mejor_jugadores_orden_y_minimo():
    contados = {
        "x": {"nombre": "x", "amarillas": 3, "rojas": 0, "apariciones": 4},
        "y": {"nombre": "y", "amarillas": 1, "rojas": 0, "apariciones": 2},
        "z": {"nombre": "z", "amarillas": 1, "rojas": 0, "apariciones": 1},  # bajo el mínimo
    }
    filas = mejor_jugadores(contados, min_apariciones=2, top=2, numerador="amarillas")
    assert [f["nombre"] for f in filas] == ["x", "y"]
    assert filas[0]["tasa"] == 0.75 and filas[1]["tasa"] == 0.5
    z = mejor_jugadores(contados, min_apariciones=2, top=3, numerador="amarillas")[2]
    assert z["tasa"] is None  # sin tasa, al final


# ───────────────────────────── modelo tarjetas ──────────────────────────────


def test_bloques_totales_y_extraer():
    bl, bv = _bloque(2, 0), _bloque(3, 1)
    fila = _fila(1, ESTA_F, 1, 2, bl, bv)
    assert bloques_de(fila) == (bl, bv)
    assert total_de(bl) == 2 and total_de(bv) == 4
    assert total_de(None) is None
    vacia = _fila(2, OTRA_F, 1, 2)
    assert bloques_de(vacia) == (None, None)
    assert extraer_tarjetas(fila) == [(1, 2.0), (2, 4.0)]
    # la fila incompleta solo entrega el lado con datos
    solo_v = {"fecha": ESTA_F, "partido": 9, "local": 1, "visitante": 2,
              "datos_l": {}, "datos_v": {"tarjetas": _bloque(1, 0)}}
    assert extraer_tarjetas(solo_v) == [(2, 1.0)]


def test_contados_por_jugador_union_roster_y_tarjeta():
    bl = _bloque(2, 0, por_jugador=[
        {"nombre": "Catena", "minuto": 6, "tipo": "amarilla"},
        {"nombre": "Catena", "minuto": 88, "tipo": "amarilla"},
        {"nombre": "Puro Ruido", "minuto": 70, "tipo": "roja"},
    ])
    fila = _fila(1, ESTA_F, 1, 2, bl, None, jug_l=[_jug("Catena"), _jug("Otto")])
    contados = contados_por_jugador([fila], 1)
    # Catena cuenta UNA aparición (peculiar: el roster lo trae y sale en 2 eventos)
    assert contados["Catena"]["apariciones"] == 1
    assert contados["Catena"]["amarillas"] == 2
    assert contados["Otto"]["apariciones"] == 1 and contados["Otto"]["amarillas"] == 0
    # el lado visitante (equipo 2) no ve tarjetas del lado del equipo 1
    assert contados_por_jugador([fila], 2) == {}


def test_propensos_equipo_minimo_y_orden():
    filas = []
    for i in range(4):
        filas.append(_fila(
            i + 1,
            ESTA_F if i < 2 else OTRA_F,
            1, 2,
            _bloque(1, 0, por_jugador=[{"nombre": "Propenso", "minuto": 10 + i, "tipo": "amarilla"}]),
            _bloque(0, 0),
            jug_l=[_jug("Propenso"), _jug("Compadre")],
            jug_v=[],
        ))
    ranking = propensos_equipo(filas, 1)
    propenso = next(f for f in ranking if f["nombre"] == "Propenso")
    assert propenso["amarillas"] == 4 and propenso["apariciones"] == 4
    assert propenso["tasa"] == 1.0
    compadre = next(f for f in ranking if f["nombre"] == "Compadre")
    assert compadre["amarillas"] == 0 and compadre["tasa"] == 0.0


def test_equipos_tarjetas_por_filas_completas():
    filas = [
        _fila(1, ESTA_F, 1, 2, _bloque(2, 0), _bloque(3, 1)),
        _fila(2, OTRA_F, 1, 2, _bloque(1, 1), _bloque(0, 0)),
    ]
    crews = equipos_tarjetas(filas)
    assert crews[1] == {"partidos": 2, "tarjetas": 4, "tasa": round(2.0, 2)}
    assert crews[2] == {"partidos": 2, "tarjetas": 4, "tasa": round(2.0, 2)}
    # una fila sin lado local no entra al recuento comparativo
    incompleta = {"fecha": ESTA_F, "partido": 3, "local": 1, "visitante": 2,
                  "datos_l": {}, "datos_v": {"tarjetas": _bloque(5, 0)}}
    crews2 = equipos_tarjetas(filas + [incompleta])
    assert crews2[2]["tarjetas"] == 4 and crews2[1]["tarjetas"] == 4


def test_prediccion_de_filas_walk_forward():
    historia = [
        _fila(1, ESTA_F, 1, 2, _bloque(3, 0), _bloque(2, 0)),
    ]
    lam = lam_de(historia, {"local": 1, "visitante": 2})
    # λ = (3 + 6·2.5)/7 + (2 + 6·2.5)/7 = 35/7 = 5.0 exacto
    assert lam is not None and abs(lam - 5.0) < 1e-9

    pred = prediccion_de_filas(historia, 1, 2, OTRA_F)
    assert pred is not None
    assert pred["tarjetas_esperadas"] == 5.0
    # el payload redondea la probabilidad a 4 decimales (contrato del endpoint)
    assert pred["prob_over_2_5"] == round(prob_over(lam, 2.5), 4)
    assert 0.0 <= pred["prob_over_2_5"] <= 1.0

    # si algún equipo NO aparece en la historia: sin predicción (honestidad)
    historial_roto = [
        _fila(1, ESTA_F, 1, 2, _bloque(3, 0), None),
    ]
    assert prediccion_de_filas(historial_roto, 1, 2, OTRA_F) is None
