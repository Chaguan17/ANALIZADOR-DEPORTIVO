"""Pruebas del modelo de CORNES (Fase 16) — todo puro, sin BD ni red.

La matemática se comprueba a mano (la misma del núcleo rates): extractor
del bloque `cornes` (wonCorners de ESPN), λ con historia, calidad
walk-forward con omisión de debutantes y totales por equipo.
"""

from datetime import datetime, timezone

from backend.app.cornes import (
    bloques_de,
    calidad_de_filas,
    equipos_cornes,
    extraer_cornes,
    lam_de,
    prediccion_de_filas,
    total_de,
)
from backend.app.rates import prob_over

ESTA_F = datetime(2026, 8, 15, 19, 0, tzinfo=timezone.utc)
OTRA_F = datetime(2026, 8, 22, 19, 0, tzinfo=timezone.utc)


def _bloque(total: int) -> dict:
    return {"total": total, "fuente": "espn"}


def _fila(
    pid: int,
    fecha: datetime,
    local: int,
    visitante: int,
    blk_l: dict | None = None,
    blk_v: dict | None = None,
) -> dict:
    datos_l = {"cornes": blk_l} if blk_l is not None else {}
    datos_v = {"cornes": blk_v} if blk_v is not None else {}
    return {
        "fecha": fecha,
        "partido": pid,
        "local": local,
        "visitante": visitante,
        "datos_l": datos_l,
        "datos_v": datos_v,
    }


def test_bloques_total_y_extraer():
    bl, bv = _bloque(8), _bloque(4)
    fila = _fila(1, ESTA_F, 1, 2, bl, bv)
    assert bloques_de(fila) == (bl, bv)
    assert total_de(bl) == 8 and total_de(None) is None
    assert extraer_cornes(fila) == [(1, 8.0), (2, 4.0)]
    # fila sin bloque: ni bloques ni extracción
    vacia = _fila(2, OTRA_F, 1, 2)
    assert bloques_de(vacia) == (None, None)
    assert extraer_cornes(vacia) == []
    # fila con un solo lado: solo ese lado entra
    solo_v = {"fecha": ESTA_F, "partido": 9, "local": 1, "visitante": 2,
              "datos_l": {}, "datos_v": {"cornes": _bloque(5)}}
    assert extraer_cornes(solo_v) == [(2, 5.0)]


def test_lam_con_historia_y_debutante():
    """Local 8, visitante 4 → media de liga 6; con k=6:
    λ = (8+36)/7 + (4+36)/7 = 12.0 exacto."""
    historia = [_fila(1, ESTA_F, 1, 2, _bloque(8), _bloque(4))]
    lam = lam_de(historia, {"local": 1, "visitante": 2})
    assert abs(lam - 12.0) < 1e-9
    # sin historia: debutante → None (honesto)
    assert lam_de([], {"local": 1, "visitante": 2}) is None
    # historia a la que le falta el bloque de un lado: sin tasa para ese equipo
    rota = [_fila(1, ESTA_F, 1, 2, _bloque(8), None)]
    assert lam_de(rota, {"local": 1, "visitante": 2}) is None


def test_prediccion_y_debutante():
    historia = [_fila(1, ESTA_F, 1, 2, _bloque(8), _bloque(4))]
    pred = prediccion_de_filas(historia, 1, 2, OTRA_F)
    assert pred is not None
    assert pred["cornes_esperados"] == 12.0
    assert pred["prob_over_9_5"] == round(prob_over(12.0, 9.5), 4)
    assert pred["prob_over_11_5"] == round(prob_over(12.0, 11.5), 4)
    assert pred["por_equipo"]["local"] == round((8 + 6 * 6) / 7, 2)      # 44/7
    assert pred["por_equipo"]["visitante"] == round((4 + 6 * 6) / 7, 2)  # 40/7
    # sin historia: sin predicción
    assert prediccion_de_filas([], 1, 2, OTRA_F) is None
    # historia incompleta (un equipo sin tasa): tampoco
    rota = [_fila(1, ESTA_F, 1, 2, _bloque(8), None)]
    assert prediccion_de_filas(rota, 1, 2, OTRA_F) is None


def test_calidad_omision_de_arranque():
    """La primera fila no tiene historia → omitida; la segunda se evalúa
    con λ=12.0 contra real 16 (acierto over en ambas líneas) y MAE 4.0."""
    filas = [
        _fila(1, ESTA_F, 1, 2, _bloque(8), _bloque(4)),
        _fila(2, OTRA_F, 1, 2, _bloque(10), _bloque(6)),
    ]
    calidad = calidad_de_filas(filas)
    assert calidad["omisiones"] == 1
    for linea in ("9.5", "11.5"):
        r = calidad["lineas"][linea]
        assert r["evaluados"] == 1
        assert r["aciertos"] == 1
        assert r["accuracy"] == 1.0
    assert calidad["lineas"]["9.5"]["mae"] == 4.0
    assert calidad["lineas"]["11.5"]["mae"] == 4.0


def test_calidad_salta_las_filas_sin_bloque_de_cornes():
    """Una fila marca-de-vacío (ambos lados sin bloque) NO entra al evaluado."""
    filas = [
        _fila(1, ESTA_F, 1, 2, _bloque(8), _bloque(4)),
        _fila(2, OTRA_F, 1, 2, None, None),
    ]
    calidad = calidad_de_filas(filas)
    assert calidad["omisiones"] == 1  # solo la primera
    # la vacía ya NO evalúa con real=0 (antes del fix evaluados sería 1)
    assert calidad["lineas"]["9.5"]["evaluados"] == 0


def test_equipos_cornes_totales_y_tasas_encogidas():
    filas = [
        _fila(1, ESTA_F, 1, 2, _bloque(8), _bloque(4)),
        _fila(2, OTRA_F, 1, 2, _bloque(10), _bloque(6)),
    ]
    crews = equipos_cornes(filas)
    # media de liga: 28/4 = 7 → t1 (18+42)/8 = 7.5 · t2 (10+42)/8 = 6.5
    assert crews[1] == {"partidos": 2, "cornes": 18, "tasa": 7.5}
    assert crews[2] == {"partidos": 2, "cornes": 10, "tasa": 6.5}
    # fila incompleta: su lado con datos aporta a las tasas, NO a los totales
    incompleta = {"fecha": OTRA_F, "partido": 3, "local": 1, "visitante": 2,
                  "datos_l": {}, "datos_v": {"cornes": _bloque(99)}}
    crews2 = equipos_cornes(filas + [incompleta])
    assert crews2[2]["cornes"] == 10 and crews2[1]["cornes"] == 18
