# -*- coding: utf-8 -*-
"""Pruebas de la evaluación walk-forward (Fase 7) — puras, sin base de datos.

Los contratos duros de la métrica honesta:
- _resultado_de mapea goles → resultado en ESPAÑOL y sin ambigüedad;
- _agregar es tolerante a los None del tercer modelo (LightGBM no emite
  over/under ni λ): promedia solo lo que existe y honestamente devuelve
  None cuando no existe nada;
- lista vacía → None (jamás inventar un 0 como promedio).
"""

import pytest

from backend.app.evaluacion import MIN_EVIDENCIA, _agregar, _resultado_de


def test_resultado_de_mapea_goles():
    assert _resultado_de(2, 1) == "local"
    assert _resultado_de(1, 1) == "empate"
    assert _resultado_de(0, 3) == "visita"


def test_agregar_sobre_filas_completas():
    def fila(acierto, real, over_real, log_loss=None, brier=None):
        return {
            "real": real,
            "over_real": over_real,
            "acierto": acierto,
            "log_loss": log_loss,
            "brier": brier,
        }

    r1 = fila(1, "local", True, log_loss=0.9, brier=0.2)
    r2 = fila(0, "visita", False, log_loss=1.1, brier=0.3)
    r3 = fila(1, "empate", False)  # sin log_loss ni brier (como LightGBM no parte)

    res = _agregar([r1, r2, r3])
    assert res is not None
    assert res["n"] == 3
    assert res["accuracy"] == pytest.approx(2 / 3)
    # baseline del "siempre local": 1 de 3 filas con real='local'
    assert res["baseline_local"] == pytest.approx(1 / 3)
    # tolerancia a None: log loss promedió SOLO las 2 filas que sí lo traen
    assert res["log_loss"] == pytest.approx(1.0)
    assert res["brier"] == pytest.approx(0.25)
    # el baseline de over promedia la fracción de partidos con over real
    assert res["baseline_over"] == pytest.approx(1 / 3)


def test_agregar_tolerante_a_none_total():
    filas = [
        {"real": "local", "over_real": True, "acierto": 1, "log_loss": None},
        {"real": "visita", "over_real": False, "acierto": 0, "log_loss": None},
    ]
    res = _agregar(filas)
    assert res is not None
    assert res["log_loss"] is None  # nadie trae log_loss → None honesto
    assert res["accuracy"] == pytest.approx(0.5)


def test_agregar_lista_vacia_es_none():
    assert _agregar([]) is None


def test_minimo_de_evidencia_apaga_el_calentamiento():
    """Guardián de contrato: sin al menos 2 partidos previos no se evalúa.

    Es la razón de que LightGBM evalúe menos partidos que el baseline:
    su calentamiento necesita las 3 clases, no solo el mínimo de filas.
    """
    assert MIN_EVIDENCIA == 2
