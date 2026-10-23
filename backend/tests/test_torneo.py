"""Pruebas del torneo vivo de los modelos (Fase 13) — solo lógica pura, sin BD.

El builder `construir_torneo` come agregados por (modelo, liga) tal como los
produce `leer_ledger`; aquí se le dan filas sintéticas y se comprueba la
aritmética completa del ranking: tasas, promedios ponderados, recortes por
liga, over/under 2.5 opcional, orden del podio y tolerancia a ledgers vacíos.
"""

from backend.app.torneo import construir_torneo, tasa_de


def _agg(
    modelo: str,
    liga: str,
    evaluados: int,
    aciertos: int,
    ll: float | None = None,
    brier: float | None = None,
    o25e: int = 0,
    o25a: int = 0,
) -> dict:
    return dict(
        modelo=modelo,
        liga=liga,
        evaluados=evaluados,
        aciertos=aciertos,
        log_loss=ll,
        brier=brier,
        o25_evaluados=o25e,
        o25_aciertos=o25a,
    )


def test_tasa_de():
    assert tasa_de(0, 0) is None
    assert tasa_de(3, 4) == 0.75


def test_torneo_vacio_es_lista_vacia():
    assert construir_torneo([], {}) == []


def test_totales_por_modelo_y_log_loss_ponderado():
    aggs = [
        _agg("poisson_doble", "PD", 10, 6, ll=1.0, brier=0.60),
        _agg("poisson_doble", "PL", 10, 4, ll=1.2, brier=0.70),
    ]
    formas = {"poisson_doble": [{"x": 1}, {"x": 2}]}
    filas = construir_torneo(aggs, formas)
    assert len(filas) == 1
    t = filas[0]
    assert t["evaluados"] == 20
    assert t["aciertos"] == 10
    assert t["accuracy"] == 0.5
    # promedio ponderado por n: (1.0*10 + 1.2*10)/20
    assert abs(t["log_loss"] - 1.1) < 1e-12
    assert abs(t["brier"] - 0.65) < 1e-12
    # la forma viaja amarrada al modelo que la pidió
    assert t["forma"] == [{"x": 1}, {"x": 2}]


def test_o25_solo_para_quien_emite():
    aggs = [
        _agg("poisson_doble", "PD", 4, 2, o25e=5, o25a=4),
        _agg("poisson_doble", "PL", 4, 2, o25e=3, o25a=1),
        _agg("lightgbm_v1", "PD", 4, 2),  # sin O2.5 (no lo emite)
    ]
    filas = {f["modelo"]: f for f in construir_torneo(aggs, {})}
    assert filas["poisson_doble"]["o25"] == {
        "evaluados": 8,
        "aciertos": 5,
        "accuracy": 5 / 8,
    }
    assert filas["lightgbm_v1"]["o25"] is None


def test_por_liga_en_orden_del_mvp():
    aggs = [
        _agg("poisson_doble", liga, 2, 1)
        for liga in ("SA", "BL1", "CL", "PD", "PL")  # orden alfabético del SQL
    ]
    opciones = [fl["liga"] for fl in construir_torneo(aggs, {})[0]["por_liga"]]
    assert opciones == ["PD", "PL", "SA", "BL1", "CL"]


def test_podio_por_accuracy_y_desempate():
    aggs = [
        # empate en tasa, mismo n → decide el orden histórico (el de nacimiento)
        _agg("poisson_doble", "PD", 10, 6),
        _agg("poisson_dc", "PD", 10, 6),
        # menor tasa → al fondo
        _agg("lightgbm_v1", "PD", 8, 4),
        # el mismo accuracy 60% pero CON MÁS evaluados → sube por el desempate
        _agg("poisson_dc", "PL", 20, 12),
    ]
    orden = [f["modelo"] for f in construir_torneo(aggs, {})]
    # 1º DC (30 evals, 60% con n mayor en el desempate) · 2º Poisson (6/10,
    # mismo 60% con menos evaluados) · 3º LightGBM (50%)
    assert orden[0] == "poisson_dc"
    assert orden[1] == "poisson_doble"
    assert orden[2] == "lightgbm_v1"
    podio = construir_torneo(aggs, {})
    assert podio[0]["evaluados"] == 30
    # el DC con dos ligas suma bien su propio total (30 evals, 18 ok = 60%)
    dc = [f for f in podio if f["modelo"] == "poisson_dc"][0]
    assert (dc["evaluados"], dc["aciertos"], dc["accuracy"]) == (30, 18, 0.6)


def test_forma_alerta_para_modelos_sin_filas():
    aggs = [_agg("poisson_doble", "PD", 5, 3)]
    filas = construir_torneo(aggs, {"lightgbm_v1": [{"y": 1}]})
    assert filas[0]["forma"] == []  # poisson_doble no pidió forma
