# -*- coding: utf-8 -*-
"""Pruebas de los features del equipo (Fase 4) — puras, sin base de datos.

Las reglas de oro convertidas en guardianes:
- walk-forward: con `hasta` FILTRADA, los partidos con fecha ≥ hasta no existen
  (cortar el futuro es la esencia de la honestidad del proyecto);
- snapshot_tabla ordena por puntos/diferencia/golesfavor (la API no es
  punto-en-tiempo: aquí se recomputa localmente);
- equipos recién llegados (sin historial) → None/0, jamás inventados.

`HistoriaLiga` se alimenta de la BD en su constructor; para probar la lógica
pura se fabrica con `__new__` + registros falsos (los métodos de consulta
solo usan `self.partidos`).
"""

from datetime import datetime

import pytest

from backend.app.features import HistoriaLiga, Registro, features_de_partido


def dt(dia, mes=8, hora=12):
    return datetime(2026, mes, dia, hora)


def registro(id_api, dia, id_local, id_visitante, goles_l, goles_v):
    return Registro(
        id_api=id_api,
        fecha=dt(dia),
        id_local=id_local,
        id_visitante=id_visitante,
        goles_local=goles_l,
        goles_visitante=goles_v,
    )


ID_A, ID_B, ID_C = 100, 200, 300  # ids sintéticos (equipos A, B, C)


def historia_de_test():
    """Cinco partidos terminados, ordenados por fecha (como en la BD)."""
    h = HistoriaLiga.__new__(HistoriaLiga)  # se salta el __init__ (no toca la BD)
    h.liga = "TEST"
    h.partidos = [
        registro(1, 1, ID_A, ID_B, 2, 1),   # A gana en casa
        registro(2, 8, ID_B, ID_C, 1, 1),   # empate
        registro(3, 15, ID_C, ID_A, 0, 3),  # A gana de visitante
        registro(4, 22, ID_A, ID_C, 1, 1),  # empate
        registro(5, 29, ID_B, ID_A, 2, 2),  # empate (B en casa)
    ]
    return h


def test_forma_es_ventana_y_se_corta_en_el_tiempo():
    h = historia_de_test()
    # hasta el 20-08: A jugó R1 (3 pts, 2-1) y R3 (3 pts, 3-0 de visitante)
    f = h.forma(ID_A, hasta=dt(20), n=5)
    assert f["j"] == 2
    assert f["puntos"] == 6
    assert f["gf"] == 5
    assert f["gc"] == 1
    # el futuro no existe: después del 01-08 A no ha jugado nada (aún)
    f0 = h.forma(ID_A, hasta=dt(1), n=5)
    assert f0["j"] == 0 and f0["puntos"] == 0


def test_snapshot_tabla_orden_y_desempate():
    h = historia_de_test()
    tabla = h.snapshot_tabla(dt(5, 9))
    # A perfecta (8 pts) · B y C empardos en 2 pts → desempata diferencia de goles
    assert tabla[ID_A]["pos"] == 1
    assert tabla[ID_B]["pos"] == 2  # dg −1
    assert tabla[ID_C]["pos"] == 3  # dg −3
    assert tabla[ID_A]["pts"] == 8
    assert tabla[ID_A]["j"] == 4
    assert tabla[ID_C]["dg"] == -3
    # y también se corta en el tiempo: solo R1 antes del 03-08
    parcial = h.snapshot_tabla(dt(3))
    assert set(parcial) == {ID_A, ID_B}
    assert parcial[ID_A]["pts"] == 3


def test_h2h_toma_los_directos_en_ambos_roles():
    h = historia_de_test()
    hd = h.h2h(ID_A, ID_B, hasta=dt(5, 9))
    # directos A-B: R1 (A en casa 2-1) y R5 (B en casa 2-2)
    assert hd["j"] == 2
    assert hd["ganados_local"] == 1
    assert hd["empates"] == 1
    assert hd["ganados_visita"] == 0
    assert hd["gf_prom"] == pytest.approx((3 + 4) / 2)


def test_ultimo_antes_da_la_fecha_y_none_con_futuro_cortado():
    h = historia_de_test()
    assert h.ultimo_antes(ID_C, dt(30)) == dt(22)   # su R4
    assert h.ultimo_antes(ID_C, dt(8)) is None      # antes de jugar nada


def test_features_de_partido_31_features_con_valores_conocidos():
    h = historia_de_test()
    f = features_de_partido(h, ID_A, ID_B, dt(5, 9))
    assert len(f) == 31
    # forma (últimos 5): A jugó 4 (3+3+1+1 = 8 pts), B jugó 3 (0+1+1 = 2 pts)
    assert f["forma_pts5_local"] == 8 and f["forma_j5_local"] == 4
    assert f["forma_pts5_visita"] == 2 and f["forma_j5_visita"] == 3
    # por condición: A en casa por R1(2-1) y R4(1-1) → ppg 2.0
    assert f["ppg_casa_local"] == pytest.approx(2.0)
    assert f["gf_prom_casa_local"] == pytest.approx(1.5)
    # B de visitante solo R1 (perdió 2-1) → ppg 0.0
    assert f["ppg_fuera_visita"] == pytest.approx(0.0)
    # descanso: ambos jugaron el 29-08 (R5) → 7 días al 05-09
    assert f["descanso_local"] == 7 and f["descanso_visita"] == 7
    # tabla al día: A 1.º (8 pts, dg+4, 4 J) · B 2.º (2 pts, dg−1, 3 J)
    assert f["pos_local"] == 1 and f["tabla_pts_local"] == 8
    assert f["tabla_dg_local"] == 4 and f["tabla_j_local"] == 4
    assert f["pos_visita"] == 2 and f["tabla_dg_visita"] == -1
    assert f["tabla_j_visita"] == 3
    # h2h directo A-B: 2 juegos, 1 gana A, 1 empate, goles prom 3.5
    assert f["h2h_jugados"] == 2
    assert f["h2h_ganados_local"] == 1
    assert f["h2h_gf_prom"] == pytest.approx(3.5)


def test_features_de_un_equipo_nuevo_son_honestamente_vacios():
    """Equipo 999 sin historia: fuerza neutral documentada, celdas None — nada
    inventado (los NaN vacíos que LightGBM entiende de fábrica)."""
    h = historia_de_test()
    f = features_de_partido(h, ID_C, 999, dt(5, 9))
    assert len(f) == 31
    assert f["forma_pts5_visita"] is None  # sin ventana → None
    assert f["forma_j5_visita"] == 0
    assert f["ppg_fuera_visita"] is None
    assert f["descanso_visita"] is None
    assert f["pos_visita"] is None        # ni siquiera está en la tabla
    assert f["h2h_jugados"] == 0          # nunca se enfrentaron
