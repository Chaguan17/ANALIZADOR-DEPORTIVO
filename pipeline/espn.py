"""ESPN (site.api.espn.com) — fuente de tiros/tarjetas/cornes (Fases 15-16).

Elegida por el dueño (2026-10-23) tras auditar las fuentes gratuitas contra
las primarias: football-data.org free NO entrega bookings/lineups en el
detalle de partido; Understat tiene los datos pero su robots.txt es
`Disallow: /` (prohíbe el scraping); ESPN entrega por partido y por equipo
totalShots · shotsOnTarget · yellowCards · redCards · wonCorners (+28 stats),
eventos de tarjeta por jugador con minuto, alineaciones y líderes de tiros.
Cubre 5/5 ligas del MVP INCLUYENDO la Champions League. Honradez: API no
oficial (la que consume la app de ESPN), sin clave; el robots.txt de ese
host no declara reglas (403 al pedirlo).

Este módulo es la pieza OFFLINE de esa fuente (sin BD, sin red):
- `normalizar` y `resolver_equipo`: el matcher nombre ESPN → equipo
  football-data (mismo código que usa la ingesta viva en backend.app.espn).
- CLI `mapear`: auditoría dev-time a partir de los JSON crudos en disco
  (scoreboards + equipos por liga); reporta cobertura y goteos por si hay
  que añadir pares manuales a `pipeline/mapping_espn.json`.

JSON vivo de mapping (`pipeline/mapping_espn.json`):
    {
      "_meta": {"nota": "solo pares manuales; el resto se resuelve en vivo"},
      "manual": {"PD": {"Nombre ESPN": "Nombre football-data exacto"}}
    }

La DESCARGA+INGESTA incremental en línea vive en `backend/app.espn`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata

from .config import RAW_DIR, REPO_ROOT, SEASON

# Código football-data → código ESPN (única fuente de verdad del mapping)
ESPN_LIGAS: dict[str, str] = {
    "PD": "esp.1",
    "PL": "eng.1",
    "SA": "ita.1",
    "BL1": "ger.1",
    "CL": "uefa.champions",
}

CRUDAESPN = RAW_DIR / "espn"
RUTA_MAPPING = REPO_ROOT / "pipeline" / "mapping_espn.json"

# Tokens genéricos (prefijos legales) que no distinguen equipos.
_STOP = frozenset(
    {"fc", "cf", "afc", "ac", "sc", "ss", "ssc", "rc", "cd", "ca", "club", "de", "del", "the"}
)


# Caracteres que NFD no descompone (letras propias, no acentos): la
# comparación tiene que verlas iguales a su ASCII habitual, porque ESPN y
# football-data las escriben distinto ("Bodø/Glimt" ↔ "FK Bodø/Glimt").
_TRANSLIT = str.maketrans({
    "ø": "o", "Ø": "O",
    "æ": "ae", "Æ": "AE",
    "ß": "ss",
    "đ": "d", "Đ": "D",
    "ł": "l", "Ł": "L",
    "ħ": "h", "Ħ": "H",
    "ŧ": "t", "Ŧ": "T",
})


def normalizar(nombre: str) -> frozenset[str]:
    """Nombre → conjunto de tokens comparables (sin acentos, minúsculas).

    Quita acentos (NFD), translitera las letras que NFD no descompone
    (ø→o, æ→ae, ß→ss, đ/ł/ħ/ŧ), baja a minúsculas, sustituye toda la
    puntuación por espacio y descarta tokens genéricos. Las cifras se
    conservan: "04" de "Schalke 04" distingue equipos.
    """
    limpio = nombre.translate(_TRANSLIT)
    limpio = unicodedata.normalize("NFD", limpio)
    limpio = "".join(c for c in limpio if unicodedata.category(c) != "Mn")
    limpio = limpio.lower()
    limpio = re.sub(r"[^0-9a-z]+", " ", limpio)
    tokens = {t for t in limpio.split() if t and t not in _STOP}
    return frozenset(tokens)


def _cargar_manual() -> dict[str, dict[str, str]]:
    """Pares manuales del mapping comprometido: {liga_fd: {nombre_espn: nombre_fd}}."""
    if not RUTA_MAPPING.exists():
        return {}
    data = json.loads(RUTA_MAPPING.read_text(encoding="utf-8"))
    manual = data.get("manual") or {}
    return {liga: dict(nombres) for liga, nombres in manual.items() if isinstance(nombres, dict)}


class _Ambiguous:
    """Sentinela: el nombre ESPN encaja con más de un equipo football-data."""


AMBIGUO = _Ambiguous()


def resolver_equipo(
    nombre_espn: str,
    nombres_fd: list[str],
    manual: dict[str, str] | None = None,
) -> "str | None | _Ambiguous":
    """Matchea un nombre ESPN contra un nombre football-data.

    Estrategia (igual que en la ingesta viva):
    1. Par definido a mano (comparación normalizada exacta).
    2. Contención de tokens: los tokens del nombre ESPN deben caber DENTRO
       de los tokens del nombre football-data (ESPN usa formas cortas:
       "Osasuna" ⊆ "CA Osasuna").

    Devuelve el nombre football-data exacto, la centinela `Ambiguous` si el
    match no es único (hay que definirlo a mano) o None si no hay match.
    """
    objetivo = normalizar(nombre_espn)
    if not objetivo:
        return None

    if manual:
        for nombre_manual, nombre_fd in manual.items():
            if normalizar(nombre_espn) == normalizar(nombre_manual):
                return nombre_fd

    candidatos: list[str] = []
    for nombre_fd in nombres_fd:
        tokens_fd = normalizar(nombre_fd)
        if not tokens_fd:
            continue
        if objetivo <= tokens_fd:
            candidatos.append(nombre_fd)
            continue
        # contención inversa para nombres de idéntica longitud lega
        if tokens_fd <= objetivo:
            candidatos.append(nombre_fd)

    if len(candidatos) == 1:
        return candidatos[0]
    if len(candidatos) > 1:
        return AMBIGUO
    return None


def indice_eventos(data: dict) -> list[dict]:
    """Scoreboard crudo → [{id, fecha_iso, local: {id, nombre}, visitante: {...}}].

    Tolerante: los eventos malformados se descartan (la API no es oficial y
    su forma puede variar); nada rompe el flujo por un evento raro.
    """
    salida: list[dict] = []
    for ev in data.get("events") or []:
        try:
            eid = str(ev["id"])
            fecha = str(ev["date"])[:10]  # ISO con hora → solo el día
            comp = (ev.get("competitions") or [{}])[0]
            lados: dict[str, dict | None] = {"local": None, "visitante": None}
            for c in comp.get("competitors") or []:
                lado = c.get("homeAway")
                if lado in ("home", "away"):
                    lados["local" if lado == "home" else "visitante"] = {
                        "id": (c.get("team") or {}).get("id"),
                        "nombre": (c.get("team") or {}).get("displayName") or "",
                    }
            if all(lados[k] for k in ("local", "visitante")):
                salida.append(
                    {"id": eid, "fecha": fecha, "local": lados["local"], "visitante": lados["visitante"]}
                )
        except (KeyError, TypeError, IndexError):
            continue
    return salida


def emparejar_partidos(
    partidos_fd: list[dict],
    indice: dict[str, list[dict]],
    resolver: "callable[[str], str | None | _Ambiguous]",
) -> tuple[dict[int, str], list[dict]]:
    """Cada partido football-data con fecha+local+visitante → id de evento ESPN.

    partidos_fd: [{"id_api", "fecha_iso" (día UTC), "home_nombre", "away_nombre"}]
    indice: {fecha_iso: [eventos de ESPN de ese día]}
    resolver: nombre ESPN → nombre football-data (o None/Ambiguous).

    Devuelve ({partido_id_api: evento_id}, [goteos con motivo]).
    Los goteos incluyen los partidos sin evento en ESPN y los que no
    se dejan emparejar (nombre no mapeado o ambiguo) — honestos siempre.
    """
    empar: dict[int, str] = {}
    goteos: list[dict] = []
    for p in partidos_fd:
        cand = [
            e for e in indice.get(p["fecha_iso"], [])
        ]
        pare = None
        motivo: str | None = None
        for e in cand:
            nb_local = resolver(e["local"]["nombre"])
            nb_visit = resolver(e["visitante"]["nombre"])
            if isinstance(nb_local, _Ambiguous) or isinstance(nb_visit, _Ambiguous):
                motivo = f"nombre ambiguo: {e['local']['nombre']} / {e['visitante']['nombre']}"
                continue
            if nb_local is None or nb_visit is None:
                motivo = f"sin match: {e['local']['nombre']} / {e['visitante']['nombre']}"
                continue
            if nb_local == p["home_nombre"] and nb_visit == p["away_nombre"]:
                if pare is not None:
                    motivo = "más de un evento ESPN encaja"
                    pare = None
                    break
                pare = e["id"]
        if pare is not None:
            empar[p["id_api"]] = pare
        else:
            goteos.append({**p, "motivo": motivo or "sin evento ESPN esa fecha"})
    return empar, goteos


def _consola_utf8() -> None:
    """Consola Windows (cp1252) + tildes = UTF-8 forzado (patrón de pipeline)."""
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def _equipos_fd(liga_fd: str) -> list[str]:
    ruta = RAW_DIR / liga_fd / f"equipos_{SEASON}.json"
    if not ruta.exists():
        return []
    data = json.loads(ruta.read_text(encoding="utf-8"))
    return [t.get("name", "") for t in data.get("teams", [])]


def _partidos_fd(liga_fd: str) -> list[dict]:
    """Partidos del crudo football-data → [{id_api, fecha_iso, home_nombre, away_nombre}]."""
    ruta = RAW_DIR / liga_fd / f"partidos_{SEASON}.json"
    if not ruta.exists():
        return []
    data = json.loads(ruta.read_text(encoding="utf-8"))
    salida: list[dict] = []
    for m in data.get("matches", []):
        salida.append(
            {
                "id_api": int(m["id"]),
                "fecha_iso": str(m["utcDate"])[:10],
                "home_nombre": ((m.get("homeTeam") or {}).get("name")) or "",
                "away_nombre": ((m.get("awayTeam") or {}).get("name")) or "",
                "estado": m.get("status") or "",
            }
        )
    return salida


def main() -> int:
    _consola_utf8()
    parser = argparse.ArgumentParser(description="ESPN: mapeo + auditoría offline (Fases 15-16)")
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("mapear", help="Audita cobertura ESPN↔football-data con los crudos en disco")
    args = parser.parse_args()

    if args.comando != "mapear":  # pragma: no cover
        parser.error("comando desconocido")

    manual = _cargar_manual()
    todo_ok = True
    for liga_fd, codigo_espn in ESPN_LIGAS.items():
        equipos = _equipos_fd(liga_fd)
        if not equipos:
            print(f"[{liga_fd}] sin crudo de equipos — omito la liga")
            todo_ok = False
            continue

        cuadro: dict[str, list[dict]] = {}
        nombres_vistos: dict[str, int] = {}
        for ruta in sorted((CRUDAESPN / liga_fd).glob("scoreboard_*.json")):
            data = json.loads(ruta.read_text(encoding="utf-8"))
            for ev in indice_eventos(data):
                cuadro.setdefault(ruta.stem.removeprefix("scoreboard_"), []).append(ev)
                for lado in ("local", "visitante"):
                    nombre = ev[lado]["nombre"]
                    if nombre:
                        nombres_vistos[nombre] = nombres_vistos.get(nombre, 0) + 1

        def resolver(nb: str) -> str | None | _Ambiguous:
            return resolver_equipo(nb, equipos, manual.get(liga_fd))

        mapeados: dict[str, str] = {}
        ambiguos: list[str] = []
        fallos: list[str] = []
        for nb in sorted(nombres_vistos):
            r = resolver(nb)
            if isinstance(r, _Ambiguous):
                encaje = [e for e in equipos if normalizar(nb) <= normalizar(e)]
                ambiguos.append(f"{nb} (encaja con: {', '.join(encaje)})")
            elif r is None:
                fallos.append(nb)
            else:
                mapeados[nb] = r

        print(f"\n══ [{liga_fd}] ({len(nombres_vistos)} nombres ESPN vistos) ══")
        print(f"   mapeados: {len(mapeados)} · ambiguos: {len(ambiguos)} · sin match: {len(fallos)}")
        for a in ambiguos:
            print(f"   AMBIGUO: {a}")
        for f in fallos:
            print(f"   SIN MATCH: {f}")

        partidos = _partidos_fd(liga_fd)
        indice = cuadro
        jugados = [p for p in partidos if p["estado"] == "FINISHED"]
        empar, goteos = emparejar_partidos(jugados, indice, resolver)
        print(f"   partidos jugados FD: {len(jugados)} · emparejados con ESPN: {len(empar)}")
        if goteos:
            todo_ok = False
            for g in goteos[:12]:
                print(f"   SIN EVENTO: {g['fecha_iso']} {g['home_nombre']} vs {g['away_nombre']} — {g['motivo']}")

    print()
    if todo_ok:
        print("Auditoría COMPLETA: todos los jugados tienen evento ESPN y equipo mapeado ✓")
        return 0
    print("Auditoría con goteos: revisa las líneas SIN MATCH / SIN EVENTO de arriba.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
