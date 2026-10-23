"""Pruebas de la fuente ESPN (Fases 15-16) — todo puro, sin BD ni red.

Las fixtures sintéticas reproducen LAS ESTRUCTURAS VERIFICADAS de
site.api.espn.com (sondas del 2026-10-23):
- scoreboard: events[].date ISO; competitions[0].competitors con homeAway.
- summary: boxscore.teams[].statistics (name/displayValue); keyEvents con
  type.text "Yellow/Red Card", participants[0].athlete y clock.displayValue;
  rosters[].roster[] con athlete.displayName/starter/subbedIn; leaders[] con
  team.id y categoría "totalShots".
"""

from backend.app.espn import (
    apariciones_de_rosters,
    cruces_de_summary,
    datos_por_equipo,
    minuto_de_clock,
    stats_de_boxscore,
    tarjetas_de_keyevents,
    tiros_de_leaders,
)
from pipeline.espn import AMBIGUO, indice_eventos, normalizar, resolver_equipo

# ─────────────────────────── fixtures sintéticas ────────────────────────────


def _summary() -> dict:
    return {
        "header": {
            "competitions": [
                {
                    "id": "401882840",
                    "date": "2026-10-18T11:00Z",
                    "competitors": [
                        {"homeAway": "home", "team": {"id": "97", "displayName": "Osasuna"}},
                        {"homeAway": "away", "team": {"id": "87", "displayName": "Racing Santander"}},
                    ],
                }
            ]
        },
        "boxscore": {
            "teams": [
                {
                    "team": {"id": "97", "displayName": "Osasuna"},
                    "statistics": [
                        {"name": "totalShots", "displayValue": "20"},
                        {"name": "shotsOnTarget", "displayValue": "7"},
                        {"name": "yellowCards", "displayValue": "2"},
                        {"name": "redCards", "displayValue": "0"},
                        {"name": "wonCorners", "displayValue": "7"},
                    ],
                },
                {
                    "team": {"id": "87", "displayName": "Racing Santander"},
                    "statistics": [
                        {"name": "totalShots", "displayValue": "9"},
                        {"name": "shotsOnTarget", "displayValue": "3"},
                        {"name": "yellowCards", "displayValue": "3"},
                        {"name": "redCards", "displayValue": "1"},
                        {"name": "wonCorners", "displayValue": "4"},
                    ],
                },
            ]
        },
        "keyEvents": [
            {
                "type": {"text": "Yellow Card"},
                "participants": [{"athlete": {"displayName": "Alejandro Catena"}}],
                "clock": {"value": 353.0, "displayValue": "6'"},
                "team": {"id": "97", "displayName": "Osasuna"},
            },
            {
                "type": {"text": "Red Card"},
                "participants": [{"athlete": {"displayName": "Javi Serrano"}}],
                "clock": {"value": 3810.0, "displayValue": "85'"},
                "team": {"id": "87", "displayName": "Racing Santander"},
            },
            {
                # evento sin jugador: se descarta (los totales vienen del boxscore)
                "type": {"text": "Yellow Card"},
                "participants": [],
                "clock": {"displayValue": "30'"},
                "team": {"id": "87"},
            },
        ],
        "rosters": [
            {
                "team": {"id": "97"},
                "roster": [
                    {"athlete": {"displayName": "Aitor Fernández"}, "starter": True,
                     "subbedIn": False, "subbedOut": True},
                    {"athlete": {"displayName": "Raúl García"}, "starter": False,
                     "subbedIn": True, "subbedOut": False},
                    {"athlete": {"displayName": "Suplente No Usado"}, "starter": False,
                     "subbedIn": False, "subbedOut": False},
                    {"athlete": {"displayName": "Sin Jugar"}, "starter": False,
                     "subbedIn": None, "subbedOut": None},
                ],
            },
            {
                "team": {"id": "87"},
                "roster": [{"athlete": {"displayName": "Vinícius Faria"}, "starter": True,
                            "subbedIn": False, "subbedOut": False}],
            },
        ],
        "leaders": [
            {
                "team": {"id": "97", "displayName": "Osasuna"},
                "leaders": [
                    {"name": "totalShots",
                     "leaders": [{"athlete": {"displayName": "Ante Budimir"},
                                  "displayValue": "4"}]},
                    {"name": "accuratePasses",
                     "leaders": [{"athlete": {"displayName": "Alfredo Sáenz"},
                                  "displayValue": "22"}]},
                ],
            },
            {
                "team": {"id": "87"},
                "leaders": [
                    {"name": "totalShots",
                     "leaders": [{"athlete": {"displayName": "Sergio Canales"},
                                  "displayValue": "3"}]},
                ],
            },
        ],
    }


# ───────────────────────── pipeline: matcher y evento ───────────────────────


def test_normalizar_sin_acentos_y_sin_tokens_genericos():
    assert normalizar("Borussia Mönchengladbach") == frozenset({"borussia", "monchengladbach"})
    assert normalizar("CA Osasuna") == frozenset({"osasuna"})
    assert normalizar("1. FC Köln") == frozenset({"1", "koln"})
    assert normalizar("  FC  BAYERN  ") == frozenset({"bayern"})


def test_normalizar_translitera_letras_sin_descomposicion():
    # ø/æ/ß/đ/ł no se descomponen en NFD: Football-data las escribe nativas
    # y ESPN a veces ASCII ("Bodø/Glimt" ↔ "Bodo/Glimt"), con el prefijo
    # legal solo en un lado (contención de tokens: {bodo, glimt} ⊆ {fk, ...}).
    assert normalizar("FK Bodø/Glimt") == frozenset({"fk", "bodo", "glimt"})
    assert normalizar("Bodo/Glimt") == frozenset({"bodo", "glimt"})
    assert normalizar("Bodo/Glimt") <= normalizar("FK Bodø/Glimt")
    assert normalizar("SønderjyskE") == frozenset({"sonderjyske"})
    assert normalizar("Ruch Chorzów") == frozenset({"ruch", "chorzow"})


def test_resolver_por_contencion():
    fd = ["Real Racing Club de Santander", "CA Osasuna", "Manchester United FC"]
    assert resolver_equipo("Osasuna", fd) == "CA Osasuna"
    assert resolver_equipo("Racing Santander", fd) == "Real Racing Club de Santander"
    assert resolver_equipo("Manchester United", fd) == "Manchester United FC"


def test_resolver_manual_gana_y_ambiguo_alerta():
    fd = ["FC Bayern München", "Bayern Leverkusen"]
    assert resolver_equipo("Bayern Munich", fd, {"Bayern Munich": "FC Bayern München"}) == (
        "FC Bayern München"
    )
    # "Bayern" encaja con los dos: ambiguo exige par manual
    assert resolver_equipo("Bayern", fd) is AMBIGUO
    assert resolver_equipo("Deportivo Capital", fd) is None


def test_indice_eventos_extrae_por_homeway():
    data = {
        "events": [
            {
                "id": "401882840",
                "date": "2026-10-18T11:00Z",
                "competitions": [
                    {"competitors": [
                        {"homeAway": "home", "team": {"id": "97", "displayName": "Osasuna"}},
                        {"homeAway": "away", "team": {"id": "87", "displayName": "Racing Santander"}},
                    ]}
                ],
            },
            # evento malformado: se descarta sin romper
            {"id": "mal", "date": "2026-10-18T12:00Z", "competitions": []},
        ]
    }
    eventos = indice_eventos(data)
    assert len(eventos) == 1
    e = eventos[0]
    assert e["id"] == "401882840"
    assert e["fecha"] == "2026-10-18"
    assert e["local"]["nombre"] == "Osasuna" and e["visitante"]["nombre"] == "Racing Santander"


# ───────────────────────── back/app: parsers del summary ────────────────────


def test_stats_de_boxscore_por_id():
    stats = stats_de_boxscore(_summary())
    assert stats["97"]["totalShots"] == 20
    assert stats["97"]["shotsOnTarget"] == 7
    assert stats["97"]["yellowCards"] == 2
    assert stats["87"]["redCards"] == 1
    assert stats["87"]["wonCorners"] == 4
    assert stats_de_boxscore({"boxscore": {}}) is None  # sin stats ⇒ fila vacía


def test_minuto_de_clock():
    assert minuto_de_clock({"displayValue": "6'"}) == 6
    assert minuto_de_clock({"displayValue": "45+2'"}) == 45
    assert minuto_de_clock(None) is None
    assert minuto_de_clock({"displayValue": ""}) is None


def test_tarjetas_de_keyevents_filtrado():
    tarjetas = tarjetas_de_keyevents(_summary())
    assert [(t["nombre"], t["tipo"], t["minuto"], t["equipo"]) for t in tarjetas] == [
        ("Alejandro Catena", "amarilla", 6, "97"),
        ("Javi Serrano", "roja", 85, "87"),
    ]


def test_apariciones_de_rosters_jugo_o_no():
    apariencias = apariciones_de_rosters(_summary())
    nombres_osasuna = [j["nombre"] for j in apariencias["97"]]
    # jugó: el titular sustituido y el que entró; NO el suplente sin usar ni el None
    assert "Aitor Fernández" in nombres_osasuna
    assert "Raúl García" in nombres_osasuna
    assert "Suplente No Usado" not in nombres_osasuna
    assert "Sin Jugar" not in nombres_osasuna
    titular = next(j for j in apariencias["97"] if j["nombre"] == "Aitor Fernández")
    assert titular["titular"] is True and titular["entra"] is False
    entra = next(j for j in apariencias["97"] if j["nombre"] == "Raúl García")
    assert entra["titular"] is False and entra["entra"] is True


def test_tiros_de_leaders_por_equipo():
    tiros = tiros_de_leaders(_summary())
    assert tiros["97"] == [{"nombre": "Ante Budimir", "tiros": 4}]
    # la categoría no totalShots no se ingiere
    assert all("Alfredo Sáenz" != j["nombre"] for j in tiros["97"])
    assert tiros["87"] == [{"nombre": "Sergio Canales", "tiros": 3}]


# ─────────────────────────── cruces y JSONB final ───────────────────────────


def _names(nombres_fd: list[str]):
    def resolver(nombre_espn: str, nombres=nombres_fd):
        objetivo = normalizar(nombre_espn)
        candidatos = [n for n in nombres if objetivo <= normalizar(n)]
        if len(candidatos) == 1:
            return {"CA Osasuna": 111, "Real Racing Club de Santander": 222}[candidatos[0]]
        if len(candidatos) > 1:
            return AMBIGUO
        return None

    return resolver


def test_cruces_y_datos_por_equipo():
    summary = _summary()
    cruces = cruces_de_summary(summary, _names(["CA Osasuna", "Real Racing Club de Santander"]),
                               111, 222)
    assert cruces == {"97": (111, "home"), "87": (222, "away")}

    recibido = datos_por_equipo(summary, cruces)
    assert set(recibido) == {111, 222}

    local = recibido[111]
    assert local["tiros"] == {"total": 20, "a_puerta": 7, "fuente": "espn"}
    assert local["tarjetas"]["amarillas"] == 2 and local["tarjetas"]["rojas"] == 0
    assert local["tarjetas"]["por_jugador"][0]["nombre"] == "Alejandro Catena"
    assert local["tarjetas"]["por_jugador"][0]["minuto"] == 6
    assert local["cornes"] == {"total": 7, "fuente": "espn"}
    alineacion = local["espn"]["alineacion"]
    assert {j["nombre"] for j in alineacion} == {"Aitor Fernández", "Raúl García"}
    assert local["espn"]["evento"] == "401882840"
    assert local["espn"]["lado"] == "home"
    assert local["espn"]["tiros_jugador"] == [{"nombre": "Ante Budimir", "tiros": 4}]

    visita = recibido[222]
    assert visita["tiros"]["total"] == 9
    assert visita["tarjetas"]["amarillas"] == 3 and visita["tarjetas"]["rojas"] == 1
    assert visita["cornes"]["total"] == 4
    assert visita["espn"]["lado"] == "away"


def test_cruces_rechaza_lados_cruzados():
    # el local football-data resulta ser el away de ESPN: se niega el cruce
    cruz = cruces_de_summary(_summary(), _names(["CA Osasuna", "Real Racing Club de Santander"]),
                             222, 111)
    assert cruz is None


def test_cruces_rechaza_nombre_sin_mapping():
    cruz = cruces_de_summary(_summary(), _names(["Rivales Faltantes"]), 111, 222)
    assert cruz is None
