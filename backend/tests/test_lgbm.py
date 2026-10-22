# -*- coding: utf-8 -*-
"""Pruebas de LightGBM v1 (Fase 5c) — puras, sin base de datos.

Contratos del tercer modelo:
- etiqueta entera 0/1/2 (el mapeo fijo con el que LightGBM ordena las clases);
- la mezcla con la uniforme: w=0 → uniforme pura, w=1 → árbol puro,
  y SIEMPRE suma 1 (es la garantía de probabilidad válida);
- W_GRID de 21 valores con paso 0.05 (lo que el grid-search barrió);
- los NaN para features faltantes: LightGBM los maneja de fábrica —
  preferimos NaN honestos a ceros mentirosos.
"""

import math

import pytest

from backend.app.modelo_lgbm import W_GRID, _a_numeros, _etiqueta_de, _mezclar


def test_etiqueta_de_mapeo_fijo_0_1_2():
    assert _etiqueta_de(2, 1) == 0   # gana el local
    assert _etiqueta_de(1, 1) == 1   # empate
    assert _etiqueta_de(0, 2) == 2   # gana el visitante


def test_w_0_es_la_uniforme_pura():
    mez = _mezclar({"pro_local": 0.9, "pro_empate": 0.05, "pro_visita": 0.05}, 0.0)
    for v in mez.values():
        assert v == pytest.approx(1 / 3)
    assert sum(mez.values()) == pytest.approx(1.0)


def test_w_1_deja_el_arbol_puro():
    arbol = {"pro_local": 0.6, "pro_empate": 0.25, "pro_visita": 0.15}
    mez = _mezclar(arbol, 1.0)
    for clave, v in arbol.items():
        assert mez[clave] == pytest.approx(v)


def test_mezcla_intermedia_siempre_suma_uno():
    probs = {"pro_local": 0.7, "pro_empate": 0.2, "pro_visita": 0.1}
    for w in W_GRID:
        mez = _mezclar(probs, w)
        assert sum(mez.values()) == pytest.approx(1.0, abs=1e-12), f"w={w} rompió el 1X2"
        # cada componente responde a la fórmula del proyecto
        assert mez["pro_local"] == pytest.approx(w * 0.7 + (1 - w) / 3)


def test_cuadricula_w_de_21_valores():
    assert len(W_GRID) == 21
    assert W_GRID[0] == 0.00
    assert W_GRID[-1] == 1.00
    assert W_GRID[4] == pytest.approx(0.20)


def test_a_numeros_de_none_a_nan():
    v = _a_numeros({"a": 3, "b": None, "c": 0.5})
    assert v[0] == 3.0
    assert math.isnan(v[1])   # None → NaN honesto (LightGBM lo entiende)
    assert v[2] == pytest.approx(0.5)
