# -*- coding: utf-8 -*-
"""Pruebas del Dixon-Coles (Fase 5b) — puras, sin base de datos.

El hallazgo estrella de la Fase 5b convertido en guardian de prueba:
    τ solo repondera las 4 celdas de marcadores bajos (0-0, 0-1, 1-0, 1-1),
    y su suma de ajustes GANANCIA/PERDIDA es cero → la masa del grid
    NO cambia → P(over 2.5) y P(under 2.5) quedan INVARIANTES.
Es la prueba de que el "bonus de empates" de DC no contamina el mercado
de goles (que es trabajo exclusivo del Poisson doble).
"""

import pytest

from backend.app.modelo_dc import RHO_GRID, _probabilidades_dc, tau


def test_tau_no_toca_las_celdas_altas():
    # cualquier marcador fuera de las 4 celdas bajas pesa 1.0
    assert tau(2, 3, 2.5, 2.0, -0.2) == 1.0
    assert tau(1, 2, 2.5, 2.0, -0.2) == 1.0
    assert tau(3, 0, 2.5, 2.0, 0.05) == 1.0


def test_tau_dirige_el_flujo_hacia_los_empates_cuando_rho_negativo():
    lam, mu = 2.5, 2.0
    # ρ negativo: 0-0 y 1-1 se ENGRUESAN (más empates), 0-1 y 1-0 se adelgazan
    assert tau(0, 0, lam, mu, -0.2) == pytest.approx(1.0 - lam * mu * (-0.2))
    assert tau(1, 1, lam, mu, -0.2) == pytest.approx(1.0 - (-0.2))
    assert tau(0, 1, lam, mu, -0.2) == pytest.approx(1.0 + lam * (-0.2))
    assert tau(1, 0, lam, mu, -0.2) == pytest.approx(1.0 + mu * (-0.2))


def test_tau_con_rho_positivo_invierte_la_corriente():
    lam, mu = 2.5, 2.0
    assert tau(0, 0, lam, mu, 0.05) < 1.0
    assert tau(1, 1, lam, mu, 0.05) < 1.0
    assert tau(0, 1, lam, mu, 0.05) > 1.0
    assert tau(1, 0, lam, mu, 0.05) > 1.0


def test_tau_clampa_a_cero_en_rincones_extremos():
    """Con λ·μ·ρ ≥ 1 la fórmula daría peso negativo → se clampa a 0.0.

    Rincon real: λ=μ=4.5 (la cúpula) con ρ=+0.05 → 1 − 10.125·0.05 < 0.
    Documentado en CONTEXTO; por eso la invarianza exacta de over/under
    solo se garantiza con λ moderadas (ver test siguiente).
    """
    assert tau(0, 0, 4.5, 4.5, 0.05) == 0.0
    # y el clamp NUNCA debe activarse sin necesidad: λ chiquita con ρ=−0.3
    # pesa 1 + 0.01·(−0.3) = 0.997 (positivo, sin clamp)
    assert tau(0, 1, 0.01, 4.5, -0.3) == pytest.approx(0.997)


def test_cuadricula_rho_tiene_29_pasos_de_0_0125():
    assert len(RHO_GRID) == 29
    assert RHO_GRID[0] == pytest.approx(-0.300)
    assert RHO_GRID[-1] == pytest.approx(0.050)
    # monotona creciente (la direccionalidad importa para el grid-search)
    assert RHO_GRID == sorted(RHO_GRID)


def test_invarianza_del_mercado_de_goles():
    """Aporte clave de DC: τ NO altera over/under 2.5 para λ moderadas.

    Con λ_local=2.8, λ_visita=2.2 y todo el grid de ρ, ninguna de las 4
    celdas bajas se clampa (el menor peso es 1 − 2.8·2.2·0.05 = 0.692 > 0),
    así que la invarianza es EXACTA (Δmasa = 0 comprobado en la Fase 5b).
    """
    for rho in (-0.300, -0.075, 0.0, 0.050):
        base = _probabilidades_dc(2.8, 2.2, 0.0)
        con_rho = _probabilidades_dc(2.8, 2.2, rho)
        assert con_rho["pro_under25"] == pytest.approx(
            base["pro_under25"], abs=1e-12
        ), f"ρ={rho}: under 2.5 cambió (¡τ contaminó el mercado de goles!)"
        assert con_rho["pro_over25"] == pytest.approx(base["pro_over25"], abs=1e-12)
        # y la masa total quedó intacta (requisito de la invarianza)
        assert con_rho["masa_grid"] == pytest.approx(base["masa_grid"], abs=1e-12)


def test_1x2_del_dc_sigue_sumando_uno():
    for rho in RHO_GRID:
        r = _probabilidades_dc(1.9, 1.4, rho)
        total = r["pro_local"] + r["pro_empate"] + r["pro_visita"]
        assert abs(total - 1.0) < 1e-9, f"ρ={rho} rompió el 1X2"


def test_el_rincón_del_clamp_rompe_la_invarianza_exacta_y_se_documenta():
    """Con λ=μ=4.5 y ρ=+0.05 la celda 0-0 clampa → masa ≠ base.

    NO es un bug: es el rincon límite ya documentado (CONTEXTO, Fase 5b);
    en la práctica las intensidades reales rara vez tocan la cúpula.
    La prueba lo deja escrito para que nadie se asombre mañana.
    """
    base = _probabilidades_dc(4.5, 4.5, 0.0)
    con_rho = _probabilidades_dc(4.5, 4.5, 0.05)
    assert con_rho["masa_grid"] != pytest.approx(base["masa_grid"], abs=1e-9)
