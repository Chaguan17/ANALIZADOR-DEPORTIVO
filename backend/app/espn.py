"""ESPN — ingesta incremental de tiros/tarjetas/cornes a stats_partido (Fases 15-16).

El ESTADO de esta ingesta es la base de datos: un partido football-data
terminado "necesita" ESPN mientras no tenga fila en `stats_partido` para el
equipo local. Por eso la descarga vive aquí y no en pipeline/: en el runner
de GitHub Actions el disco se borra en cada corrida, y lo único que sobrevive
entre corridas es la BD — con eso el ciclo queda idempotente y reanudable.
Los crudos igualmente se guardan en `pipeline/raw/espn/` (caché-first en el
disco del momento; en Actions son efímeros y también sirve lo BD-estado).

De dónde sale cada dato (1 summary ESPN = 1 partido completo):
- boxscore.teams[].statistics → totalShots · shotsOnTarget · yellowCards ·
  redCards · wonCorners por equipo (+28 stats que el proyecto no usa aún).
- keyEvents → eventos de tarjeta por jugador (nombre · minuto · tipo).
- rosters[].roster → apariciones por jugador (jugó = titular o entró; los
  suplentes no usados van `false` y NO cuentan como aparición).
- leaders[] (agrupa por equipo, con team.id) → totalShots por jugador: solo
  los líderes viajan (parcial POR DISEÑO de la fuente; se usa como mejor
  esfuerzo para el ranking de tiradores, nunca como total del equipo).

JSONB que esta ingesta deja en cada fila (partido_id_api, equipo_id_api):
    datos["tiros"]    = {"total": int, "a_puerta": int, "fuente": "espn"}
    datos["tarjetas"] = {"amarillas": int, "rojas": int, "fuente": "espn",
                         "por_jugador": [{"nombre", "minuto", "tipo"}]}
    datos["cornes"]   = {"total": int, "fuente": "espn"}
    datos["espn"]     = {"evento": id, "fecha": iso, "lado": "home|away",
                         "alineacion": [{"nombre", "titular", "entra"}],
                         "tiros_jugador": [{"nombre", "tiros"}]}
    (si el summary no trajo stats: fila marca {"espn": {"evento", "vacio":
    true, "fecha"}} — para NO reintentar un partido que nunca traerá nada.

Honestidad de fuente: ESPN es un endpoint no oficial (el que consume su
app), sin clave y sin contrato — puede cambiar de forma. Aquí TODO es
tolerante: eventos malformados se descartan, un fallo puntual no aborta la
corrida y el exit es siempre 0 (el cron NO se pone rojo por ESPN; el informe
`estado` es el termómetro visible y la auditoría del workflow lo imprime).

El matcher de equipos (nombre ESPN → football-data) vive en pipeline/espn.py:
primero el mapping manual comprometido en mapping_espn.json y, si no hay par
manual, contención de tokens contra los nombres reales de la BD. Un nombre
nuevo o ambiguo se registra y se salta: la corrección es añadir el par
manual (dev-time), no parchear la ingesta.

CLI:
    python -m backend.app.espn actualizar --limite 40   # descarga + carga
    python -m backend.app.espn cargar                   # carga crudos ya en disco
    python -m backend.app.espn estado                   # cobertura por liga
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
from sqlalchemy import or_, select

# matcher y códigos de liga: una sola fuente de verdad en pipeline/
from pipeline.espn import (
    AMBIGUO,
    CRUDAESPN,
    ESPN_LIGAS,
    _Ambiguous,
    indice_eventos,
    resolver_equipo,
)

from .config import REPO_ROOT
from .consola import consola_utf8
from .db import SessionLocal
from .models import Equipo, Partido, StatsPartido

logger = logging.getLogger("espn")

RUTA_MAPPING = REPO_ROOT / "pipeline" / "mapping_espn.json"

_PACE_S = 2.5          # cortesía con un endpoint no oficial
_TIMEOUT_S = 30.0
_INTENTOS = 3
_UA = "analizador-deportivo/0.2 (github.com/Chaguan17/ANALIZADOR-DEPORTIVO)"

FRONTERA_DIAS = 10     # días hacia adelante en que también se baja scoreboard

# Los 5 stats por equipo que este proyecto ingiere hoy (ESPN trae 28)
STATS = ("totalShots", "shotsOnTarget", "yellowCards", "redCards", "wonCorners")


# ─────────────────────────── cliente HTTP con cortesía ──────────────────────


class ClienteESPN:
    """httpx con pacing, reintentos para 429/5xx y caché-first a disco."""

    def __init__(self, raw_dir: Path | None = None) -> None:
        self.raw_dir = raw_dir or CRUDAESPN
        self._http = httpx.Client(
            headers={"User-Agent": _UA, "Accept": "application/json"},
            timeout=_TIMEOUT_S,
        )
        self._ultimo: float = 0.0

    def _paso(self) -> None:
        delta = time.monotonic() - self._ultimo
        if delta < _PACE_S:
            time.sleep(_PACE_S - delta)

    def get_json(self, url: str, save_path: Path) -> dict | None:
        """JSON cache-first; None si la fuente falla (nunca levanta excepción)."""
        try:
            if save_path.exists():
                return json.loads(save_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            logger.warning("crudo ilegible %s (%s); re-bajo", save_path, e)

        for intento in range(1, _INTENTOS + 1):
            self._paso()
            try:
                r = self._http.get(url)
                self._ultimo = time.monotonic()
                if r.status_code == 200:
                    data = r.json()
                    self._guardar(save_path, data)
                    return data
                if r.status_code == 429 or r.status_code >= 500:
                    logger.warning(
                        "HTTP %s en %s (intento %s/%s)",
                        r.status_code, url, intento, _INTENTOS,
                    )
                    time.sleep(3 * 2 ** (intento - 1))  # 3, 6, 12 s
                    continue
                # 4xx: definitivo — no reintenta ni rompe
                logger.error("HTTP %s (definitivo) en %s", r.status_code, url)
                return None
            except httpx.HTTPError as e:
                logger.warning(
                    "fallo de red en %s (intento %s/%s): %s",
                    url, intento, _INTENTOS, e,
                )
                time.sleep(3 * 2 ** (intento - 1))
        logger.error("agotados %s intentos para %s", _INTENTOS, url)
        return None

    def _guardar(self, save_path: Path, data: dict) -> None:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    def close(self) -> None:
        self._http.close()


def url_scoreboard(codigo: str, dia_iso: str) -> str:
    """Scoreboard por UN solo día (los rangos devuelven 400; verificado 2026-10-23)."""
    return f"https://site.api.espn.com/apis/site/v2/sports/soccer/{codigo}/scoreboard?dates={dia_iso.replace('-', '')}"


def url_summary(codigo: str, evento: str) -> str:
    return f"https://site.api.espn.com/apis/site/v2/sports/soccer/{codigo}/summary?event={evento}"


def ruta_scoreboard(liga_fd: str, dia_iso: str, raw_dir: Path) -> Path:
    return raw_dir / liga_fd / f"scoreboard_{dia_iso}.json"


def ruta_summary(liga_fd: str, evento: str, raw_dir: Path) -> Path:
    return raw_dir / liga_fd / f"summary_{evento}.json"


# ─────────────────────────── extracción del summary ─────────────────────────


def _stat_int(valor: object) -> int | None:
    if valor is None:
        return None
    try:
        return int(str(valor).strip())
    except ValueError:
        return None


def stats_de_boxscore(summary: dict) -> dict[str, dict[str, int]] | None:
    """{id_equipo_espn: {nombre_stat: valor}} con las 5 stats del proyecto.

    None ⇔ el summary no trae boxscore (la fuente se negó o aún no lo carga):
    el llamador marcará la fila como "vacío" para no reintentar.
    """
    grupos = ((summary.get("boxscore") or {}).get("teams")) or []
    if not grupos:
        return None
    salida: dict[str, dict[str, int]] = {}
    for grupo in grupos:
        e_id = str((grupo.get("team") or {}).get("id") or "")
        if not e_id:
            continue
        fila: dict[str, int] = {}
        for stat in grupo.get("statistics") or []:
            nombre = stat.get("name")
            if nombre in STATS:
                v = _stat_int(stat.get("displayValue"))
                if v is not None:
                    fila[str(nombre)] = v
        salida[e_id] = fila
    return salida


_MINUTO = re.compile(r"(\d+)")


def minuto_de_clock(clock: dict | None) -> int | None:
    """clock.displayValue "6'" / "45+2'" → 6 / 45 (minuto base; display only)."""
    if not clock:
        return None
    texto = str(clock.get("displayValue") or "")
    m = _MINUTO.search(texto)
    return int(m.group(1)) if m else None


def tarjetas_de_keyevents(summary: dict) -> list[dict]:
    """Eventos de tarjeta: [{"equipo", "nombre", "minuto", "tipo"}]."""
    eventos: list[dict] = []
    for ke in summary.get("keyEvents") or []:
        tipo = str(((ke.get("type") or {}).get("text") or "")).lower()
        if "yellow card" in tipo:
            clase = "amarilla"
        elif "red card" in tipo:
            clase = "roja"
        else:
            continue
        participantes = ke.get("participants") or []
        nombre = ""
        if participantes:
            nombre = str(((participantes[0].get("athlete") or {}).get("displayName")) or "")
        if not nombre:  # sin jugador el detalle no sirve: fuera (los totales van por boxscore)
            continue
        e_id = str((ke.get("team") or {}).get("id") or "")
        if not e_id:
            continue
        eventos.append({
            "equipo": e_id,
            "nombre": nombre,
            "minuto": minuto_de_clock(ke.get("clock")),
            "tipo": clase,
        })
    return eventos


def _jugo_partido(entrada: dict) -> bool:
    """¿Entró al campo? Titular=True; un suplente no usado llega con `false`."""
    return (
        bool(entrada.get("starter"))
        or bool(entrada.get("subbedIn"))
        or bool(entrada.get("subbedOut"))
    )


def apariciones_de_rosters(summary: dict) -> dict[str, list[dict]]:
    """{id_equipo_espn: [{"nombre", "titular", "entra"}]} — solo quienes jugaron."""
    salida: dict[str, list[dict]] = {}
    for grupo in summary.get("rosters") or []:
        e_id = str((grupo.get("team") or {}).get("id") or "")
        if not e_id:
            continue
        filas: list[dict] = []
        for entrada in grupo.get("roster") or []:
            nombre = str(((entrada.get("athlete") or {}).get("displayName")) or "")
            if not nombre:
                continue
            titular = bool(entrada.get("starter"))
            entra = bool(entrada.get("subbedIn"))
            if _jugo_partido(entrada):
                filas.append({"nombre": nombre, "titular": titular, "entra": entra})
        salida[e_id] = filas
    return salida


def tiros_de_leaders(summary: dict) -> dict[str, list[dict]]:
    """{id_equipo_espn: [{"nombre", "tiros"}]} — líderes de totalShots del evento."""
    salida: dict[str, list[dict]] = {}
    for grupo in summary.get("leaders") or []:
        e_id = str((grupo.get("team") or {}).get("id") or "")
        if not e_id:
            continue
        filas: list[dict] = []
        for categoria in grupo.get("leaders") or []:
            if categoria.get("name") != "totalShots":
                continue
            for registro in categoria.get("leaders") or []:
                nombre = str(((registro.get("athlete") or {}).get("displayName")) or "")
                tiros = _stat_int(registro.get("displayValue"))
                if nombre and tiros is not None:
                    filas.append({"nombre": nombre, "tiros": tiros})
        salida[e_id] = filas
    return salida


def _lados_de_header(summary: dict) -> dict[str, str]:
    """{id_equipo_espn: "home"|"away"} cruzado con el header (no por orden)."""
    lados: dict[str, str] = {}
    try:
        comp = ((summary.get("header") or {}).get("competitions") or [{}])[0]
        for c in comp.get("competitors") or []:
            e_id = str(((c.get("team") or {}).get("id")) or "")
            lado = c.get("homeAway")
            if e_id and lado in ("home", "away"):
                lados[e_id] = str(lado)
    except (IndexError, TypeError, AttributeError):
        pass
    return lados


def _nombres_de_boxscore(summary: dict) -> dict[str, str]:
    nombres: dict[str, str] = {}
    for grupo in ((summary.get("boxscore") or {}).get("teams")) or []:
        equ = grupo.get("team") or {}
        e_id = str(equ.get("id") or "")
        if e_id:
            nombres[e_id] = str(equ.get("displayName") or "")
    return nombres


def fecha_de_summary(summary: dict) -> str | None:
    try:
        comp = ((summary.get("header") or {}).get("competitions") or [{}])[0]
        return str(comp.get("date"))[:10] or None
    except (IndexError, TypeError, AttributeError):
        return None


def evento_de_summary(summary: dict) -> str | None:
    try:
        comp = ((summary.get("header") or {}).get("competitions") or [{}])[0]
        return str(comp.get("id")) or None
    except (IndexError, TypeError, AttributeError):
        return None


def vacio_de_summary(summary: dict) -> dict:
    """Fila-marca para un summary que no trajo datos: NO se reintenta."""
    return {"espn": {
        "evento": evento_de_summary(summary),
        "fecha": fecha_de_summary(summary),
        "vacio": True,
    }}


# ────────────────────────── nombre ESPN → equipo FD ─────────────────────────


def _manual_de_liga(liga_fd: str) -> dict[str, str]:
    try:
        data = json.loads(RUTA_MAPPING.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    manual = data.get("manual") or {}
    return dict(manual.get(liga_fd) or {})


def resolver_de_liga(session, liga_fd: str):
    """resolver(nombre_espn) → id_equipo_fd | None | AMBIGUO, para una liga.

    Manual primero (mapping comprometido) y luego contención de tokens contra
    los nombres REALES que la BD conoce para esa liga (ManU del mapping auto
    vive contra el snapshot de equipos, no contra un diccionario fijo).
    """
    filas = session.execute(
        select(Equipo.id_api, Equipo.nombre)
        .where(
            or_(
                Equipo.id_api.in_(select(Partido.id_local).where(Partido.liga == liga_fd)),
                Equipo.id_api.in_(select(Partido.id_visitante).where(Partido.liga == liga_fd)),
            )
        )
    ).all()
    id_por_nombre = {nombre: e_id for e_id, nombre in filas}
    manual = _manual_de_liga(liga_fd)

    def resolver(nombre_espn: str) -> int | None | _Ambiguous:
        nb_fd = resolver_equipo(nombre_espn, list(id_por_nombre), manual)
        if isinstance(nb_fd, _Ambiguous):
            return AMBIGUO
        if nb_fd is None:
            return None
        return id_por_nombre.get(nb_fd)

    return resolver


# ─────────────────────────── emparejamiento resumen ↔ FD ────────────────────


def cruces_de_summary(
    summary: dict,
    resolver,
    id_local_fd: int,
    id_visit_fd: int,
) -> dict[str, tuple[int, str]] | None:
    """{id_equipo_espn: (equipo_id_fd, "home"|"away")} para UN partido FD.

    Valida que el lado home del summary sea el equipo football-data local.
    None si se empata mal (nombre sin mapping / ambiguo / lados cruzados) —
    el llamador registrará el motivo y esta fuente no se miente.
    """
    lados = _lados_de_header(summary)
    nombres = _nombres_de_boxscore(summary)
    cruces: dict[str, tuple[int, str]] = {}
    for e_id, lado in lados.items():
        if lado == "?" or not e_id:
            continue
        nb = resolver(nombres.get(e_id, ""))
        if isinstance(nb, _Ambiguous):
            logger.error("nombre AMBIGUO para %s: %s", e_id, nombres.get(e_id))
            return None
        if nb is None:
            logger.error("sin mapping ESPN→FD para %r (Evento %s)", nombres.get(e_id), evento_de_summary(summary))
            return None
        esperado = id_local_fd if lado == "home" else id_visit_fd
        if nb != esperado:
            logger.error(
                "los lados no coinciden: ESPN %s (home) resolvió a id %s, esperaba %s",
                nombres.get(e_id), nb, esperado,
            )
            return None
        cruces[e_id] = (nb, lado)
    if len(cruces) < 2:
        return None
    return cruces


def datos_por_equipo(
    summary: dict,
    cruces: dict[str, tuple[int, str]],
) -> dict[int, dict]:
    """Summary validado → {id_equipo_fd: datos_jsonb} (las filas listas)."""
    stats = stats_de_boxscore(summary)
    if stats is None:
        return {}
    tarjetas = tarjetas_de_keyevents(summary)
    apariciones = apariciones_de_rosters(summary)
    tiros_jugadores = tiros_de_leaders(summary)
    evento = evento_de_summary(summary)
    fecha = fecha_de_summary(summary)

    salida: dict[int, dict] = {}
    for e_id, fila_stats in stats.items():
        cruce = cruces.get(e_id)
        if cruce is None:
            continue
        id_fd, lado = cruce
        por_jugador = [
            {"nombre": t["nombre"], "minuto": t["minuto"], "tipo": t["tipo"]}
            for t in sorted(
                (t for t in tarjetas if t["equipo"] == e_id),
                key=lambda t: (t["minuto"] or 0, t["nombre"]),
            )
        ]
        # boxscore manda en los totales; keyEvents llenan el detalle por jugador
        amarillas = fila_stats.get(
            "yellowCards", sum(1 for t in por_jugador if t["tipo"] == "amarilla")
        )
        rojas = fila_stats.get("redCards", sum(1 for t in por_jugador if t["tipo"] == "roja"))
        salida[id_fd] = {
            "tiros": {
                "total": fila_stats.get("totalShots", 0),
                "a_puerta": fila_stats.get("shotsOnTarget", 0),
                "fuente": "espn",
            },
            "tarjetas": {
                "amarillas": amarillas,
                "rojas": rojas,
                "fuente": "espn",
                "por_jugador": por_jugador,
            },
            "cornes": {"total": fila_stats.get("wonCorners", 0), "fuente": "espn"},
            "espn": {
                "evento": evento,
                "fecha": fecha,
                "lado": lado,
                "alineacion": apariciones.get(e_id, []),
                "tiros_jugador": tiros_jugadores.get(e_id, []),
            },
        }
    return salida


def upsert_stats(session, id_partido: int, id_equipo: int, datos: dict) -> bool:
    """Merge-upsert idempotente por (partido, equipo); True ⇔ fila nueva."""
    fila = session.scalars(
        select(StatsPartido).where(
            StatsPartido.partido_id_api == id_partido,
            StatsPartido.equipo_id_api == id_equipo,
        )
    ).first()
    if fila is None:
        session.add(
            StatsPartido(partido_id_api=id_partido, equipo_id_api=id_equipo, datos=dict(datos))
        )
        return True
    base = dict(fila.datos or {})
    base.update(datos)  # las claves del crudo manda sobre lo viejo (re-ingesta)
    fila.datos = base   # asignación (no mutación) → SQLAlchemy marca el cambio
    return False


# ────────────────────────────── consultas de estado ─────────────────────────


def fechas_de_liga(session, liga_fd: str, hoy: date) -> set[str]:
    """Días (ISO) con partidos FD que la ventana vigente exige mirar: todos los
    FINISHED + los próximos llamados por FRONTERA_DIAS (pre-pairing del cron)."""
    filas = session.execute(
        select(Partido.utc_date, Partido.estado).where(Partido.liga == liga_fd)
    ).all()
    salida: set[str] = set()
    tope = hoy + timedelta(days=FRONTERA_DIAS)
    for utc_dt, estado in filas:
        dia = utc_dt.date()
        if estado == "FINISHED" or (
            estado in ("SCHEDULED", "TIMED") and hoy <= dia <= tope
        ):
            salida.add(dia.isoformat())
    return salida


def partidos_sin_datos(session, liga_fd: str) -> list[Partido]:
    """FINISHED de la liga sin ninguna fila ESPN en stats_partido (el pendiente)."""
    filas = session.execute(
        select(Partido).where(Partido.liga == liga_fd, Partido.estado == "FINISHED")
    ).scalars().all()
    with_stats = {
        p for (p,) in session.execute(
            select(StatsPartido.partido_id_api).distinct()
        ).all()
    }
    return [p for p in filas if p.id_api not in with_stats]


def cobertura(session, liga_fd: str) -> tuple[int, int, int]:
    """(jugados, con datos, filas) de la liga — el termómetro de `estado`."""
    jugados = session.scalars(
        select(Partido.id_api)
        .where(Partido.liga == liga_fd, Partido.estado == "FINISHED")
    ).all()
    total_jugados = len(set(jugados))

    filas = session.execute(
        select(StatsPartido.partido_id_api, StatsPartido.equipo_id_api)
        .join(Partido, Partido.id_api == StatsPartido.partido_id_api)
        .where(Partido.liga == liga_fd)
    ).all()
    con_datos = len({p for p, _ in filas})
    return total_jugados, con_datos, len(filas)


# ─────────────────────────────────── acciones ───────────────────────────────


def _nombres_de_partido(session, partido: Partido) -> dict[int, str] | None:
    p_ids = {partido.id_local, partido.id_visitante}
    filas = session.execute(
        select(Equipo.id_api, Equipo.nombre).where(Equipo.id_api.in_(p_ids))
    ).all()
    if len(filas) < 2:
        logger.error("partido %s sin sus dos equipos en la BD", partido.id_api)
        return None
    return {e_id: nb for e_id, nb in filas}


def actualizar(limite: int = 40, raw_dir: Path | None = None) -> dict:
    """Ciclo del cron: scoreboards por fecha del momento + summaries pendientes.

    Presupuesto `limite` sobre el TOTAL de peticiones hechas en ESTA invitada
    (scoreboard + summary cuentan igual). Nunca levanta: devuelve un dict de
    conteos y termina con exit 0.
    """
    raw_dir = raw_dir or CRUDAESPN
    hoy = datetime.now(timezone.utc).date()
    conteos = {"scoreboards": 0, "summaries": 0, "nuevas_filas": 0, "actualizadas": 0,
               "sin_evento": 0, "sin_mapping": 0, "vacias": 0}

    cliente = ClienteESPN(raw_dir)
    try:
        with SessionLocal() as session:
            for liga_fd, codigo in ESPN_LIGAS.items():
                if limite - conteos["scoreboards"] - conteos["summaries"] <= 0:
                    logger.warning("presupuesto agotado antes de %s; reanudo en la próxima", liga_fd)
                    break

                # 1) scoreboards de los días exigidos (cache-first, cuenta como req nueva)
                dias = sorted(fechas_de_liga(session, liga_fd, hoy))
                scoreboards: dict[str, dict | None] = {}
                for dia in dias:
                    ruta = ruta_scoreboard(liga_fd, dia, raw_dir)
                    _antes = ruta.exists()
                    sb = cliente.get_json(url_scoreboard(codigo, dia), ruta)
                    scoreboards[dia] = sb
                    if sb is not None and not _antes:
                        conteos["scoreboards"] += 1
                    if limite - conteos["scoreboards"] - conteos["summaries"] <= 0:
                        break

                resolver = resolver_de_liga(session, liga_fd)

                # 2) partidos pendientes → evento ESPN → summary → stats_partido
                detalles = partidos_sin_datos(session, liga_fd)
                for p in detalles:
                    if limite - conteos["summaries"] - conteos["scoreboards"] <= 0:
                        logger.warning("presupuesto agotado en summaries de %s; queda pendiente", liga_fd)
                        break
                    nombres = _nombres_de_partido(session, p)
                    if nombres is None:
                        continue
                    eventos_dia = [
                        e
                        for e in indice_eventos(scoreboards.get(p.utc_date.date().isoformat()) or {})
                        if e["fecha"] == p.utc_date.date().isoformat()
                    ]
                    if not eventos_dia:
                        conteos["sin_evento"] += 1
                        logger.info(
                            "pendiente %s %s vs %s: sin evento ESPN esa fecha",
                            p.id_api, nombres[p.id_local], nombres[p.id_visitante],
                        )
                        continue
                    evento_id = None
                    motivo = "sin mapping ESPN→FD (nombre nuevo o ambiguo)"
                    for e in eventos_dia:
                        ev_local = resolver(e["local"]["nombre"])
                        ev_visit = resolver(e["visitante"]["nombre"])
                        if isinstance(ev_local, _Ambiguous) or isinstance(ev_visit, _Ambiguous):
                            motivo = f"nombre AMBIGUO en ESPN: {e['local']['nombre']} / {e['visitante']['nombre']}"
                            continue
                        if ev_local is None or ev_visit is None:
                            motivo = f"sin mapping ESPN→FD: {e['local']['nombre']} / {e['visitante']['nombre']}"
                            continue
                        if ev_local == p.id_local and ev_visit == p.id_visitante:
                            if evento_id is not None:
                                motivo = "más de un evento ESPN encaja"
                                evento_id = None
                                break
                            evento_id = e["id"]
                    if evento_id is None:
                        conteos["sin_evento"] += 1
                        logger.info("pendiente %s %s vs %s: %s", p.id_api, nombres[p.id_local], nombres[p.id_visitante], motivo)
                        continue

                    ruta = ruta_summary(liga_fd, evento_id, raw_dir)
                    _antes = ruta.exists()
                    data = cliente.get_json(url_summary(codigo, evento_id), ruta)
                    if data is not None and not _antes:
                        conteos["summaries"] += 1
                    if data is None:
                        logger.warning("summary %s no disponible; queda pendiente", evento_id)
                        continue

                    cruces = cruces_de_summary(data, resolver, p.id_local, p.id_visitante)
                    if cruces is None:
                        conteos["sin_mapping"] += 1
                        continue
                    filas = datos_por_equipo(data, cruces)
                    if filas:
                        for id_equipo, datos in filas.items():
                            nueva_fila = upsert_stats(session, p.id_api, id_equipo, datos)
                            if nueva_fila:
                                conteos["nuevas_filas"] += 1
                            else:
                                conteos["actualizadas"] += 1
                    else:
                        # stats vacías: fila-marca (ambos lados) para NO reintentar
                        for id_equipo in (p.id_local, p.id_visitante):
                            subio = upsert_stats(session, p.id_api, id_equipo, vacio_de_summary(data))
                            conteos["nuevas_filas"] += 1 if subio else 0
                        conteos["vacias"] += 1
                    session.commit()
            session.commit()
    finally:
        cliente.close()
    return conteos


def cargar(raw_dir: Path | None = None) -> dict:
    """Replay offline: trots crudos ya en disco → stats_partido (sin bajar más).

    Determina el partido FD de cada summary buscando su evento en el
    scoreboard de la misma fecha (caché de disco) y cruzando por nombre.
    """
    raw_dir = raw_dir or CRUDAESPN
    conteos = {"filas": {"nuevas": 0, "actualizadas": 0}, "vacias": 0, "sin_scoreboard": 0, "sin_partido": 0}
    with SessionLocal() as session:
        for liga_fd, _codigo in ESPN_LIGAS.items():
            resolver = resolver_de_liga(session, liga_fd)
            for ruta in sorted((raw_dir / liga_fd).glob("summary_*.json")):
                try:
                    summary = json.loads(ruta.read_text(encoding="utf-8"))
                except (OSError, ValueError) as e:
                    logger.warning("crudo ilegible %s: %s", ruta, e)
                    continue
                fecha = fecha_de_summary(summary)
                evento = evento_de_summary(summary)
                if not fecha or not evento:
                    continue
                ruta_sb = raw_dir / liga_fd / f"scoreboard_{fecha}.json"
                if not ruta_sb.exists():
                    conteos["sin_scoreboard"] += 1
                    continue
                try:
                    sb = json.loads(ruta_sb.read_text(encoding="utf-8"))
                except (OSError, ValueError) as e:
                    logger.warning("crudo ilegible %s: %s", ruta_sb, e)
                    continue
                ev = next(
                    (e for e in indice_eventos(sb) if e["id"] == evento), None
                )
                if ev is None:
                    conteos["sin_scoreboard"] += 1
                    continue
                nb_local = resolver(ev["local"]["nombre"])
                nb_visit = resolver(ev["visitante"]["nombre"])
                if isinstance(nb_local, _Ambiguous):
                    nb_local = None
                if isinstance(nb_visit, _Ambiguous):
                    nb_visit = None
                if nb_local is None or nb_visit is None:
                    conteos["sin_partido"] += 1
                    logger.info("sin mapping para el evento %s (%s)", evento, ruta_sb.name)
                    continue
                p = session.scalars(
                    select(Partido).where(
                        Partido.liga == liga_fd,
                        Partido.id_local == nb_local,
                        Partido.id_visitante == nb_visit,
                        Partido.utc_date >= datetime.fromisoformat(fecha),
                        Partido.utc_date < datetime.fromisoformat(fecha) + timedelta(days=1),
                    )
                ).first()
                if p is None:
                    conteos["sin_partido"] += 1
                    continue
                cruces = cruces_de_summary(summary, resolver, p.id_local, p.id_visitante)
                if cruces is None:
                    continue
                filas = datos_por_equipo(summary, cruces)
                if not filas:
                    vacio = vacio_de_summary(summary)
                    for id_equipo in (p.id_local, p.id_visitante):
                        if upsert_stats(session, p.id_api, id_equipo, vacio):
                            conteos["filas"]["nuevas"] += 1
                    conteos["vacias"] += 1
                else:
                    for id_equipo, datos in filas.items():
                        nueva = upsert_stats(session, p.id_api, id_equipo, datos)
                        conteos["filas"]["nuevas" if nueva else "actualizadas"] += 1
                session.commit()
    return conteos


def estado() -> None:
    print("Cobertura ESPN por liga (jugados · con datos · filas):")
    with SessionLocal() as session:
        for liga_fd in ESPN_LIGAS:
            j, c, f = cobertura(session, liga_fd)
            print(f"   {liga_fd}: {c}/{j} jugados con datos ({f} filas)")


def main() -> int:
    consola_utf8()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s espn: %(message)s")
    parser = argparse.ArgumentParser(description="ESPN → stats_partido (Fases 15-16)")
    sub = parser.add_subparsers(dest="comando", required=True)

    p_act = sub.add_parser("actualizar", help="descarga + carga (el ciclo del cron)")
    p_act.add_argument("--limite", type=int, default=40, help="presupuesto de requests")
    sub.add_parser("cargar", help="replay: crudos ya en disco → BD")
    sub.add_parser("estado", help="conteo de cobertura por liga")
    args = parser.parse_args()

    if args.comando == "actualizar":
        c = actualizar(args.limite)
        print("ESPN actualizar:", {k: v for k, v in c.items()})
        return 0
    if args.comando == "cargar":
        c = cargar()
        print("ESPN cargar:", c)
        return 0
    estado()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
