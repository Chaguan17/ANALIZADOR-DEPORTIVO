# -*- coding: utf-8 -*-
"""Pruebas del baseline POISSON DOBLE (Fase 5) — puras, sin base de datos.

Los guardianes matemáticos del proyecto convertidos en pruebas:
- la PMF de Poisson es una distribución (masa ~1 dentro del grid);
- la contracción bayesiana empuja hacia 1.0 con poca evidencia;
- el 1X2 renormalizado SIEMPRE suma 1 (hay un assert-guardián en el código);
- con peso identico (=1), el resultado es el Poisson doble puro.
"""


import pytest

from backend.app.modelo import (
    LAMBDA_MAX,
    LAMBDA_MIN,
    MAX_FUERZA,
    MAX_GOLES,
    MIN_FUERZA,
    _cupir_lambda,
    _encoger,
    _pmf_poisson,
    probabilidades_1x2,
)


def test_pmf_poisson_es_distribucion():
    """Masa ~1 dentro del grid (el rabo fuera de 8 goles es despreciable)."""
    p = _pmf_poisson(2.7)
    assert len(p) == MAX_GOLES + 1
    assert sum(p) <= 1.0
    assert sum(p) > 0.99  # 0.2% se va en el rabo k>8, documentado
    # caso determinista: λ=0 → todo en 0
    assert _pmf_poisson(0.0)[0] == pytest.approx(1.0)


def test_encoger_contraccion_bayesiana():
    # sin evidencia (j=0) → fuerza neutral 1.0
    assert _encoger(2.0, j=0) == pytest.approx(1.0)
    # con mucha evidencia → casi la fuerza cruda
    assert _encoger(2.0, j=1000) == pytest.approx(1.9920, abs=1e-3)
    # cositas conocidas: j=8 con K=8 → mitad del camino hacia 1.5
    assert _encoger(1.5, j=8) == pytest.approx(1.25)


def test_encoger_respeta_los_limites_de_fuerza():
    # fuerzas absurdas quedan recortadas al rango plausible
    assert _encoger(9.0, j=100) == MAX_FUERZA
    assert _encoger(0.1, j=100) == MIN_FUERZA


def test_cupir_lambda_rango_realista():
    assert _cupir_lambda(0.05) == LAMBDA_MIN
    assert _cupir_lambda(99.0) == LAMBDA_MAX
    assert _cupir_lambda(2.3) == pytest.approx(2.3)


def test_1x2_suma_uno_y_reparte_cajas():
    r = probabilidades_1x2(_pmf_poisson(2.3), _pmf_poisson(1.2))
    total = r["pro_local"] + r["pro_empate"] + r["pro_visita"]
    assert abs(total - 1.0) < 1e-9
    # over + under se construyen como complementarios
    assert r["pro_over25"] + r["pro_under25"] == pytest.approx(1.0, abs=1e-12)
    # la masa del grid es la probabilidad sin renormalizar (0 < masa ≤ 1)
    assert 0.0 < r["masa_grid"] <= 1.0
    # la PMF ya renormalizada no puede exceder el 100% por celda
    assert max(r["pro_local"], r["pro_empate"], r["pro_visita"]) <= 1.0


def test_1x2_simetria_con_intensidades_iguales():
    """λ idénticos → el modelo no favorece a nadie (simetría del Poisson doble)."""
    r = probabilidades_1x2(_pmf_poisson(1.3), _pmf_poisson(1.3))
    assert r["pro_local"] == pytest.approx(r["pro_visita"], abs=1e-12)
    # y el marcador más probable es el (1-1)
    assert r["marcador_estimado"] == "1-1"


def test_1x2_marcador_mas_probable_coincide_con_argmax():
    """λ_local=2.3 (modo 2) · λ_visita=1.2 (modo 1) → marcador estimado 2-1."""
    r = probabilidades_1x2(_pmf_poisson(2.3), _pmf_poisson(1.2))
    assert r["marcador_estimado"] == "2-1"
    # el local es favorito claro
    assert r["pro_local"] > r["pro_visita"]


def test_peso_identidad_devuelve_el_poisson_puro():
    """La puerta de entrada de Dixon-Coles con τ≡1 debe dejar TODO igual."""
    pmf_l = _pmf_poisson(2.3)
    pmf_v = _pmf_poisson(1.2)
    base = probabilidades_1x2(pmf_l, pmf_v)
    con_peso = probabilidades_1x2(pmf_l, pmf_v, peso=lambda i, j: 1.0)
    for clave in ("pro_local", "pro_empate", "pro_visita", "masa_grid"):
        assert base[clave] == pytest.approx(con_peso[clave], abs=1e-15)
