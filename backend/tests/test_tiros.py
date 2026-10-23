"""Pruebas del modelo de TIROS (Fase 16) — todo puro, sin BD ni red.

La matemática se comprueba a mano (la misma del núcleo rates): extractores
de los dos streams (tiros / a puerta), λ por stream, tiradores por aparición
(unión roster ∪ leaders) y la calidad walk-forward dos-streams.
"""

from datetime import datetime, timezone

from backend.app.rates import prob_over
from backend.app.tiros import (
    LINEA_A_PUERTA,
    LINEA_TIROS,
    a_puerta_de,
    bloques_de,
    calidad_a_lineas,
    calidad_de_filas,
    contados_de_tiros,
    equipos_tiros,
    extraer_a_puerta,
    extraer_tiros,
    lam_a_puerta_de,
    lam_total_de,
    prediccion_de_filas,
    tiradores_equipo,
    tiradores_liga,
    total_de,
)

ESTA_F = datetime(2026, 8, 15, 19, 0, tzinfo=timezone.utc)
OTRA_F = datetime(2026, 8, 22, 19, 0, tzinfo=timezone.utc)


def _bloque(total: int, a_puerta: int) -> dict:
    return {"total": total, "a_puerta": a_puerta, "fuente": "espn"}


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
    tira_l: list[dict] | None = None,
    tira_v: list[dict] | None = None,
) -> dict:
    datos_l = (
        {
            "tiros": blk_l,
            "espn": {"alineacion": jug_l or [], "tiros_jugador": tira_l or []},
        }
        if blk_l is not None
        else {}
    )
    datos_v = (
        {
            "tiros": blk_v,
            "espn": {"alineacion": jug_v or [], "tiros_jugador": tira_v or []},
        }
        if blk_v is not None
        else {}
    )
    return {
        "fecha": fecha,
        "partido": pid,
        "local": local,
        "visitante": visitante,
        "datos_l": datos_l,
        "datos_v": datos_v,
    }


# ─────────────────────────── extracción pura ───────────────────────────────


def test_bloques_totales_y_extraer_dos_streams():
    bl, bv = _bloque(15, 6), _bloque(9, 3)
    fila = _fila(1, ESTA_F, 1, 2, bl, bv)
    assert bloques_de(fila) == (bl, bv)
    assert total_de(bl) == 15 and total_de(None) is None
    assert a_puerta_de(bl) == 6 and a_puerta_de(None) is None
    assert extraer_tiros(fila) == [(1, 15.0), (2, 9.0)]
    assert extraer_a_puerta(fila) == [(1, 6.0), (2, 3.0)]
    # la fila sin bloque entrega (None, None) y extractores vacíos
    vacia = _fila(2, OTRA_F, 1, 2)
    assert bloques_de(vacia) == (None, None)
    assert extraer_tiros(vacia) == []
    # fila con un solo lado: solo ese lado entra
    solo_v = {"fecha": ESTA_F, "partido": 9, "local": 1, "visitante": 2,
              "datos_l": {}, "datos_v": {"tiros": _bloque(10, 2)}}
    assert extraer_tiros(solo_v) == [(2, 10.0)]
    assert extraer_a_puerta(solo_v) == [(2, 2.0)]


def test_lam_two_streams_distintos():
    """Local 15/6, visitante 9/3 → media-liga total 12, media a puerta 4.5;
    con k=6: λ_tiros = (15+72)/7 + (9+72)/7 = 24.0 exacto y
    λ_a_puerta = (6+27)/7 + (3+27)/7 = 9.0 exacto: DOS PMF separadas."""
    historia = [
        _fila(1, ESTA_F, 1, 2, _bloque(15, 6), _bloque(9, 3)),
    ]
    lam_t = lam_total_de(historia, {"local": 1, "visitante": 2})
    lam_ap = lam_a_puerta_de(historia, {"local": 1, "visitante": 2})
    assert abs(lam_t - 24.0) < 1e-9
    assert abs(lam_ap - 9.0) < 1e-9
    # sin historia: debutante → None (honesto)
    assert lam_total_de([], {"local": 1, "visitante": 2}) is None
    assert lam_a_puerta_de([], {"local": 1, "visitante": 2}) is None


def test_prediccion_walk_forward_y_debutante():
    historia = [
        _fila(1, ESTA_F, 1, 2, _bloque(15, 6), _bloque(9, 3)),
    ]
    pred = prediccion_de_filas(historia, 1, 2, OTRA_F)
    assert pred is not None
    assert pred["tiros_esperados"] == 24.0
    assert pred["a_puerta_esperados"] == 9.0
    assert pred["prob_over_23_5"] == round(prob_over(24.0, LINEA_TIROS), 4)
    assert pred["prob_a_puerta_over_8_5"] == round(prob_over(9.0, LINEA_A_PUERTA), 4)
    assert pred["por_equipo"]["local"]["tiros"] == round((15 + 6 * 12) / 7, 2)
    assert pred["por_equipo"]["visitante"]["a_puerta"] == round((3 + 6 * 4.5) / 7, 2)

    # sin historia: sin predicción (honestidad) — partido debutante
    assert prediccion_de_filas([], 1, 2, OTRA_F) is None
    # historia que solo ve a UN equipo: tampoco
    rota = [_fila(1, ESTA_F, 1, 2, _bloque(15, 6), None)]
    assert prediccion_de_filas(rota, 1, 2, OTRA_F) is None


def test_calidad_dos_streams_con_omision_de_arranque():
    filas = [
        _fila(1, ESTA_F, 1, 2, _bloque(15, 6), _bloque(9, 3)),
        _fila(2, OTRA_F, 1, 2, _bloque(10, 4), _bloque(8, 2)),
    ]
    calidad = calidad_de_filas(filas)
    total_q = calidad["total"]
    ap_q = calidad["a_puerta"]
    # la primera fila no tiene historia → omitida en AMBOS streams
    assert total_q["omisiones"] == 1 and ap_q["omisiones"] == 1
    assert total_q["lineas"]["23.5"]["evaluados"] == 1
    assert ap_q["lineas"]["8.5"]["evaluados"] == 1
    # los streams no comparten bloque de resultados
    assert "8.5" not in total_q["lineas"] and "23.5" not in ap_q["lineas"]

    juntas = calidad_a_lineas(calidad)
    assert set(juntas["lineas"]) == {"23.5", "8.5"}
    assert juntas["omisiones"] == 1  # el MAX de ambos (mismo tipo de omisión)


def test_contados_de_tiros_union_roster_y_leaders():
    fila = _fila(
        1, ESTA_F, 1, 2, _bloque(15, 6), None,
        jug_l=[_jug("Mbappe"), _jug("Companero")],
        tira_l=[{"nombre": "Mbappe", "tiros": 3}, {"nombre": "SoloLeader", "tiros": 2}],
    )
    contados = contados_de_tiros([fila], 1)
    assert contados["Mbappe"] == {"nombre": "Mbappe", "tiros": 3, "apariciones": 1}
    assert contados["Companero"]["tiros"] == 0 and contados["Companero"]["apariciones"] == 1
    # quien solo sale en los leaders TAMBIÉN cuenta como aparición (jugó)
    assert contados["SoloLeader"]["tiros"] == 2
    # el lado visitante no ve los tiros del equipo 1
    assert contados_de_tiros([fila], 2) == {}


def test_tiradores_equipo_tasa_por_aparicion_y_minimo():
    filas = [
        _fila(1, ESTA_F, 1, 2, _bloque(15, 6), _bloque(9, 3),
              jug_l=[_jug("Favorito"), _jug("Raro")],
              tira_l=[{"nombre": "Favorito", "tiros": 4}]),
        _fila(2, OTRA_F, 1, 2, _bloque(15, 6), _bloque(9, 3),
              jug_l=[_jug("Favorito"), _jug("Raro")],
              tira_l=[{"nombre": "Favorito", "tiros": 2}]),
    ]
    ranking = tiradores_equipo(filas, 1)
    fav = next(f for f in ranking if f["nombre"] == "Favorito")
    assert fav["tiros"] == 6 and fav["apariciones"] == 2 and fav["tasa"] == 3.0
    raro = next(f for f in ranking if f["nombre"] == "Raro")
    assert raro["apariciones"] == 2 and raro["tiros"] == 0 and raro["tasa"] == 0.0


def test_tiradores_liga_agrega_y_fija_el_equipo_primer_visto():
    filas = [
        _fila(1, ESTA_F, 1, 2, _bloque(10, 4), _bloque(10, 4),
              jug_l=[_jug("A"), _jug("B")], jug_v=[_jug("A")],
              tira_l=[{"nombre": "A", "tiros": 5}],
              tira_v=[{"nombre": "A", "tiros": 1}]),
    ]
    salida = tiradores_liga(filas, top=5)
    d = salida[0]
    assert d["nombre"] == "A"
    # el equipo fijado es el PRIMERO que lo vio (equipo 1) — mismo criterio
    # de propensos_liga (no re-resuelve el nombre, honestidad del agregado)
    assert d["equipo_id_api"] == 1
    assert d["tiros"] == 6 and d["apariciones"] == 2


def test_equipos_tiros_totales_crudos_y_tasas_encogidas():
    filas = [
        _fila(1, ESTA_F, 1, 2, _bloque(15, 6), _bloque(9, 3)),
        _fila(2, OTRA_F, 1, 2, _bloque(10, 4), _bloque(8, 2)),
    ]
    crews = equipos_tiros(filas)
    # media de liga: tiros 42/4 = 10.5 · a puerta 15/4 = 3.75
    assert crews[1] == {
        "partidos": 2,
        "tiros": 25,
        "a_puerta": 10,
        "tasa_tiros": round((25 + 6 * 10.5) / 8, 2),
        "tasa_a_puerta": round((10 + 6 * 3.75) / 8, 2),
    }
    # fila incompleta: su lado con datos aporta a las tasas, NO a los totales
    incompleta = {"fecha": OTRA_F, "partido": 3, "local": 1, "visitante": 2,
                  "datos_l": {}, "datos_v": {"tiros": _bloque(99, 1)}}
    crews2 = equipos_tiros(filas + [incompleta])
    assert crews2[2]["tiros"] == 17 and crews2[1]["tiros"] == 25


def test_calidad_salta_las_filas_sin_bloque_de_tiros():
    """Una fila marca-de-vacío (ambos lados sin bloque) NO entra al evaluado."""
    filas = [
        _fila(1, ESTA_F, 1, 2, _bloque(15, 6), _bloque(9, 3)),
        _fila(2, OTRA_F, 1, 2, None, None),  # vacía: ni total ni a puerta
    ]
    calidad = calidad_de_filas(filas)
    assert calidad["total"]["omisiones"] == 1  # solo la primera
    # la vacía ya NO evalúa con real=0 (antes del fix evaluados sería 1)
    assert calidad["total"]["lineas"]["23.5"]["evaluados"] == 0
