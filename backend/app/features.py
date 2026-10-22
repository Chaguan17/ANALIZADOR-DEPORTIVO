"""Features de rendimiento de equipos (FASE 4).

Regla de oro anti-filtración (data leakage):
    Un feature calculado para un partido SOLO puede usar información de
    partidos con fecha ANTERIOR a ese partido (walk-forward honesto).
    Esto garantiza que el backtesting de la Fase 7 y las predicciones reales
    midan lo mismo.

Catálogo documentado oficialmente en proyecto/00_CONTEXTO.md (sección 10):
    - forma_*       últimos N=5 partidos (puntos, goles fav/contra, nº jugados)
    - *_casa/fuera  rendimiento histórico como local / como visitante
    - descanso_*    días desde el último partido
    - tabla_*       snapshot de clasificación calculado SOLO con partidos previos
                    (no usa la tabla actual de la API: es impura en el tiempo)
    - h2h_*         historial directo local vs visitante (últimos N=6)

Notas: sin xG en el free tier (documentado); features de jugadores diferidos a
la Fase 6 (el top-10 de goleadores es el único dato de jugador disponible).

Demo:  python -m backend.app.features --liga PD --prox 1
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from .consola import consola_utf8
from .db import SessionLocal
from .models import Partido

N_FORMA = 5   # ventana de forma (en partidos, no en días)
N_H2H = 6     # profundidad del historial directo

# Solo partidos terminados cuentan para la historia del feature
ESTADO_JUGADO = "FINISHED"


@dataclass(frozen=True)
class Registro:
    """Partido terminado dentro de una liga-temporada (solo datos crudos, inmutable)."""

    id_api: int
    fecha: datetime
    id_local: int
    id_visitante: int
    goles_local: int
    goles_visitante: int


def _puntos_de(re: Registro, equipo: int) -> int:
    """Puntos de `equipo` en el registro (3 ganó, 1 empató, 0 perdió)."""
    gf = re.goles_local if re.id_local == equipo else re.goles_visitante
    gc = re.goles_visitante if re.id_local == equipo else re.goles_local
    if gf > gc:
        return 3
    if gf == gc:
        return 1
    return 0


class HistoriaLiga:
    """Historia ordenada en el tiempo de los partidos FINISHED de una liga-temporada."""

    def __init__(self, liga: str, temporada: int):
        with SessionLocal() as session:
            filas = session.execute(
                select(
                    Partido.id_api, Partido.utc_date,
                    Partido.id_local, Partido.id_visitante,
                    Partido.goles_local, Partido.goles_visitante,
                ).where(
                    Partido.liga == liga,
                    Partido.temporada == temporada,
                    Partido.estado == ESTADO_JUGADO,
                    Partido.goles_local.is_not(None),
                ).order_by(Partido.utc_date)
            ).all()
        self.liga = liga
        self.partidos: list[Registro] = [
            Registro(
                id_api=f.id_api, fecha=f.utc_date,
                id_local=f.id_local, id_visitante=f.id_visitante,
                goles_local=f.goles_local, goles_visitante=f.goles_visitante,
            )
            for f in filas
        ]

    # ── helpers de consulta (siempre fecha < hasta: regla de oro) ─────────
    def _previos_de(self, equipo: int, hasta: datetime) -> list[Registro]:
        return [
            r for r in self.partidos
            if r.fecha < hasta and (r.id_local == equipo or r.id_visitante == equipo)
        ]

    def forma(self, equipo: int, hasta: datetime, n: int = N_FORMA, como: str | None = None) -> dict:
        """Ventana de últimos N partidos: puntos, goles favor/contra, nº cubiertos."""
        if como == "local":
            base = [r for r in self._previos_de(equipo, hasta) if r.id_local == equipo]
        elif como == "visitante":
            base = [r for r in self._previos_de(equipo, hasta) if r.id_visitante == equipo]
        else:
            base = self._previos_de(equipo, hasta)
        ventana = base[-n:]
        return {
            "j": len(ventana),
            "puntos": sum(_puntos_de(r, equipo) for r in ventana),
            "gf": sum(r.goles_local if r.id_local == equipo else r.goles_visitante for r in ventana),
            "gc": sum(r.goles_visitante if r.id_local == equipo else r.goles_local for r in ventana),
        }

    def snapshot_tabla(self, hasta: datetime) -> dict[int, dict]:
        """Clasificación 'al día de la fecha' calculada con partidos FINISHED < hasta.

        Postura metodológica: la Clasificacion de la API es un snapshot del PRESENTE,
        no punto-en-tiempo; recomputar el ordenamiento local evita filtración.
        Orden: puntos ↓, diferencia de goles ↓, goles a favor ↓ (regla común de la liga).
        """
        acum: dict[int, dict[str, int]] = {}
        for r in self.partidos:
            if not (r.fecha < hasta):
                continue
            loc = acum.setdefault(r.id_local, {"pts": 0, "gf": 0, "gc": 0, "j": 0})
            vis = acum.setdefault(r.id_visitante, {"pts": 0, "gf": 0, "gc": 0, "j": 0})
            loc["j"] += 1
            vis["j"] += 1
            loc["gf"] += r.goles_local
            loc["gc"] += r.goles_visitante
            vis["gf"] += r.goles_visitante
            vis["gc"] += r.goles_local
            p_loc = _puntos_de(r, r.id_local)
            p_vis = _puntos_de(r, r.id_visitante)
            loc["pts"] += p_loc
            vis["pts"] += p_vis
        orden = sorted(
            acum.items(),
            key=lambda kv: (kv[1]["pts"], kv[1]["gf"] - kv[1]["gc"], kv[1]["gf"]),
            reverse=True,
        )
        return {
            eq: {"pos": i + 1, "pts": d["pts"], "dg": d["gf"] - d["gc"], "j": d["j"]}
            for i, (eq, d) in enumerate(orden)
        }

    def h2h(self, local: int, visitante: int, hasta: datetime, n: int = N_H2H) -> dict:
        """Historial directo (últimos n, sin importar quién fue local)."""
        recs = [
            r for r in self.partidos
            if r.fecha < hasta
            and ((r.id_local, r.id_visitante) in ((local, visitante), (visitante, local)))
        ]
        ventana = recs[-n:]
        v_local = sum(1 for r in ventana if _puntos_de(r, local) == 3)
        empates = sum(1 for r in ventana if _puntos_de(r, local) == 1)
        return {
            "j": len(ventana),
            "ganados_local": v_local,
            "empates": empates,
            "ganados_visita": len(ventana) - v_local - empates,
            "gf_prom": (sum(r.goles_local + r.goles_visitante for r in ventana) / len(ventana)) if ventana else None,
        }

    def ultimo_antes(self, equipo: int, hasta: datetime) -> datetime | None:
        """Fecha del último partido previo (insumo del cálculo de descanso)."""
        recs = self._previos_de(equipo, hasta)
        return recs[-1].fecha if recs else None


def features_de_partido(
    historia: HistoriaLiga, id_local: int, id_visitante: int, fecha: datetime
) -> dict[str, float | int | None]:
    """Vector de 31 features de EQUIPO para ese enfrentamiento (fecha-aware)."""
    f: dict[str, float | int | None] = {}

    # 1) Forma general (ventana 5)
    fl = historia.forma(id_local, fecha)
    fv = historia.forma(id_visitante, fecha)
    f["forma_pts5_local"] = fl["puntos"] if fl["j"] else None
    f["forma_gf5_local"] = fl["gf"] if fl["j"] else None
    f["forma_gc5_local"] = fl["gc"] if fl["j"] else None
    f["forma_j5_local"] = fl["j"]
    f["forma_pts5_visita"] = fv["puntos"] if fv["j"] else None
    f["forma_gf5_visita"] = fv["gf"] if fv["j"] else None
    f["forma_gc5_visita"] = fv["gc"] if fv["j"] else None
    f["forma_j5_visita"] = fv["j"]

    # 2) Comportamiento por condición (todo el historial previo disponible)
    casa = historia.forma(id_local, fecha, n=999, como="local")
    fuera = historia.forma(id_visitante, fecha, n=999, como="visitante")
    f["ppg_casa_local"] = round(casa["puntos"] / casa["j"], 3) if casa["j"] else None
    f["gf_prom_casa_local"] = round(casa["gf"] / casa["j"], 3) if casa["j"] else None
    f["gc_prom_casa_local"] = round(casa["gc"] / casa["j"], 3) if casa["j"] else None
    f["j_casa_local"] = casa["j"]
    f["ppg_fuera_visita"] = round(fuera["puntos"] / fuera["j"], 3) if fuera["j"] else None
    f["gf_prom_fuera_visita"] = round(fuera["gf"] / fuera["j"], 3) if fuera["j"] else None
    f["gc_prom_fuera_visita"] = round(fuera["gc"] / fuera["j"], 3) if fuera["j"] else None
    f["j_fuera_visita"] = fuera["j"]

    # 3) Descanso (días desde el último partido previo)
    ult_l = historia.ultimo_antes(id_local, fecha)
    ult_v = historia.ultimo_antes(id_visitante, fecha)
    f["descanso_local"] = (fecha - ult_l).days if ult_l else None
    f["descanso_visita"] = (fecha - ult_v).days if ult_v else None

    # 4) Snapshot de tabla al día del partido
    tabla = historia.snapshot_tabla(fecha)
    tl = tabla.get(id_local)
    tv = tabla.get(id_visitante)
    f["pos_local"] = tl["pos"] if tl else None
    f["pos_visita"] = tv["pos"] if tv else None
    f["tabla_pts_local"] = tl["pts"] if tl else None
    f["tabla_pts_visita"] = tv["pts"] if tv else None
    f["tabla_dg_local"] = tl["dg"] if tl else None
    f["tabla_dg_visita"] = tv["dg"] if tv else None
    f["tabla_j_local"] = tl["j"] if tl else None
    f["tabla_j_visita"] = tv["j"] if tv else None

    # 5) Historial directo
    h = historia.h2h(id_local, id_visitante, fecha)
    f["h2h_jugados"] = h["j"]
    f["h2h_ganados_local"] = h["ganados_local"]
    f["h2h_empates"] = h["empates"]
    f["h2h_ganados_visita"] = h["ganados_visita"]
    f["h2h_gf_prom"] = round(h["gf_prom"], 3) if h["gf_prom"] is not None else None

    return f


def _nombres_equipos(ids: list[int]) -> dict[int, str]:
    from .models import Equipo

    with SessionLocal() as session:
        filas = session.execute(
            select(Equipo.id_api, Equipo.nombre).where(Equipo.id_api.in_(ids))
        ).all()
    return {i: n for i, n in filas}


def _proximos(session, liga: str, temporada: int, n: int) -> list[Partido]:
    filas = session.execute(
        select(Partido)
        .where(
            Partido.liga == liga,
            Partido.temporada == temporada,
            Partido.estado.in_(("SCHEDULED", "TIMED")),
        )
        .order_by(Partido.utc_date)
    ).scalars().all()
    return list(filas)[:n]


def main() -> None:
    consola_utf8()
    parser = argparse.ArgumentParser(description="Features de equipo (Fase 4) — demo")
    parser.add_argument("--liga", default="PD", help="Código de liga (PD/PL/SA/BL1/CL)")
    parser.add_argument("--prox", type=int, default=1, help="Nº próximos partidos a analizar")
    args = parser.parse_args()

    from pipeline.config import SEASON

    with SessionLocal() as session:
        proximos = _proximos(session, args.liga, SEASON, args.prox)
        if not proximos:
            print(f"No hay partidos SCHEDULED/TIMED en {args.liga}.")
            return
        historia = HistoriaLiga(args.liga, SEASON)
        nombres = _nombres_equipos(
            sorted({t for m in proximos for t in (m.id_local, m.id_visitante)})
        )

        for p in proximos:
            print("=" * 70)
            print(
                f"{args.liga} · {p.utc_date:%Y-%m-%d} jornada {p.jornada}  |  "
                f"{nombres[p.id_local]} (id {p.id_local}) vs "
                f"{nombres[p.id_visitante]} (id {p.id_visitante})  ·  partido_id {p.id_api}"
            )
            print("=" * 70)
            feats = features_de_partido(historia, p.id_local, p.id_visitante, p.utc_date)
            for llave, valor in feats.items():
                print(f"  {llave:<24} {valor}")


if __name__ == "__main__":
    main()
