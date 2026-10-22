"""Cargador idempotente: JSON crudo (pipeline/raw/) → Postgres (Fase 3).

Principios:
1. **Upsert por id de la API** (session.merge): re-correr nunca duplica ni
   corrompe — inserta lo nuevo, deja lo idéntico igual, actualiza lo cambiado.
2. **Orden de carga:** equipos → jugadores → partidos → clasificacion
   (las FK exigen que equipos exista primero).
3. **Defensa en profundidad:** cualquier equipo referenciado (matches, goleadores,
   standings) se crea al vuelo si falta → la FK nunca se rompe.
4. **QA inmediato:** conteos por tabla + detección de duplicados lógicos.

Ejecutar:  python -m backend.app.load
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from .consola import consola_utf8
from .db import SessionLocal
from .models import Clasificacion, Equipo, Jugador, Partido

# Puente a la Fase 2 (single source of truth de ligas/temporada/carpeta cruda)
from pipeline.config import LIGAS_MVP, RAW_DIR, SEASON

logger = logging.getLogger("backend.load")

ARCHIVOS = {
    "equipos": f"equipos_{SEASON}.json",
    "clasificacion": f"clasificacion_{SEASON}.json",
    "partidos": f"partidos_{SEASON}.json",
    "goleadores": f"goleadores_{SEASON}.json",
}


def _parse_utc(zulu: str) -> datetime:
    """'2026-08-15T18:00:00Z' → datetime con zona horaria."""
    return datetime.fromisoformat(str(zulu).replace("Z", "+00:00"))


class Cargador:
    """Fusiona los JSON crudos de una temporada en Postgres."""

    def __init__(self, session: Session):
        self.session = session
        self.raw_dir_path = Path(RAW_DIR)
        self.equipos_vistos: set[int] = set(session.scalars(select(Equipo.id_api)))

    # ── Equipos: el guardián de las FK ────────────────────────────────────
    def upsert_equipo(self, team: dict | None) -> int | None:
        """Fusiona un equipo crudo; devuelve su id de API (None si el objeto es inválido)."""
        if not team or not team.get("id"):
            return None
        id_api = int(team["id"])
        if id_api in self.equipos_vistos:
            return id_api  # ya está en la BD (o ya fusionado en esta pasada)
        self.session.merge(
            Equipo(
                id_api=id_api,
                nombre=team.get("name") or "SIN NOMBRE",
                nombre_corto=team.get("shortName"),
                tla=team.get("tla"),
                fundacion=team.get("founded"),
                escudo_url=team.get("crest"),
            )
        )
        self.equipos_vistos.add(id_api)
        return id_api

    def _leer(self, code: str, archivo: str) -> dict:
        ruta = self.raw_dir_path / code / ARCHIVOS[archivo]
        if not ruta.exists():
            return {}
        return json.loads(ruta.read_text(encoding="utf-8"))

    # ── Fuentes ──────────────────────────────────────────────────────────
    def cargar_equipos(self) -> int:
        """Endpoint teams: la fuente principal (equipos oficiales de cada liga)."""
        antes = self._contar_equipos()
        for code in LIGAS_MVP:
            data = self._leer(code, "equipos")
            for team in data.get("teams", []):
                self.upsert_equipo(team)
        return self._contar_equipos() - antes

    def cargar_jugadores(self) -> int:
        """Jugadores extraídos de los top-10 goleadores por liga."""
        antes = self._contar(Jugador)
        for code in LIGAS_MVP:
            data = self._leer(code, "goleadores")
            for item in data.get("scorers", []) or []:
                player = item.get("player") or {}
                if not player.get("id"):
                    continue
                team_id = self.upsert_equipo(item.get("team"))
                fecha = player.get("dateOfBirth")
                self.session.merge(
                    Jugador(
                        id_api=int(player["id"]),
                        nombre=player.get("name") or "SIN NOMBRE",
                        fecha_nac=_parse_utc(fecha).date() if fecha else None,
                        nacionalidad=player.get("nationality"),
                        posicion=player.get("position"),
                        equipo_id_api=team_id,
                    )
                )
        return self._contar(Jugador) - antes

    def cargar_partidos(self) -> int:
        """Todos los partidos por liga; equipos vía FK seguro (creación al vuelo)."""
        antes = self._contar(Partido)
        for code in LIGAS_MVP:
            data = self._leer(code, "partidos")
            for m in data.get("matches", []) or []:
                marcador = m.get("score") or {}
                tento = marcador.get("fullTime") or {}
                medio = marcador.get("halfTime") or {}
                temporada = int(str((m.get("season") or {}).get("startDate", f"{SEASON}"))[:4])
                self.session.merge(
                    Partido(
                        id_api=int(m["id"]),
                        liga=code,
                        temporada=temporada,
                        etiqueta_etapa=m.get("stage"),
                        utc_date=_parse_utc(m["utcDate"]),
                        estado=m.get("status") or "SCHEDULED",
                        jornada=m.get("matchday"),
                        id_local=self.upsert_equipo(m.get("homeTeam")),
                        id_visitante=self.upsert_equipo(m.get("awayTeam")),
                        goles_local=tento.get("home"),
                        goles_visitante=tento.get("away"),
                        ganador=marcador.get("winner"),
                        medio_tiempo_local=medio.get("home"),
                        medio_tiempo_visitante=medio.get("away"),
                    )
                )
        return self._contar(Partido) - antes

    def cargar_clasificacion(self) -> int:
        """Filas de la tabla TOTAL del standings (por liga × temporada × equipo)."""
        antes = self._contar(Clasificacion)
        for code in LIGAS_MVP:
            data = self._leer(code, "clasificacion")
            for tabla in data.get("standings", []) or []:
                if tabla.get("type") != "TOTAL":
                    continue  # solo el agregado global; HOME/AWAY se derivan en Fase 4
                for fila in tabla.get("table", []) or []:
                    team_id = self.upsert_equipo(fila.get("team"))
                    if team_id is None:
                        continue
                    self.session.merge(
                        Clasificacion(
                            liga=code,
                            temporada=SEASON,
                            equipo_id_api=team_id,
                            posicion=fila["position"],
                            jugados=fila["playedGames"],
                            ganados=fila["won"],
                            empatados=fila["draw"],
                            perdidos=fila["lost"],
                            goles_favor=fila["goalsFor"],
                            goles_contra=fila["goalsAgainst"],
                            diferencia_goles=fila["goalDifference"],
                            puntos=fila["points"],
                            forma=fila.get("form"),
                        )
                    )
        return self._contar(Clasificacion) - antes

    # ── Utilidades ───────────────────────────────────────────────────────
    def _contar(self, model) -> int:
        return self.session.scalar(select(func.count()).select_from(model))

    def _contar_equipos(self) -> int:
        return self._contar(Equipo)


def main() -> None:
    consola_utf8()
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")
    print("=" * 60)
    print(f"FASE 3 · Carga idempotente JSON crudo → Postgres · temporada {SEASON}")
    print("=" * 60)

    try:
        with SessionLocal.begin() as session:
            cargador = Cargador(session)
            n_equipos = cargador.cargar_equipos()
            n_jugadores = cargador.cargar_jugadores()
            n_partidos = cargador.cargar_partidos()
            n_clasif = cargador.cargar_clasificacion()
            # commit automático al salir; rollback completo si algo falla
    except OperationalError:
        print(
            "\n✗ Postgres no responde. ¿Está levantado el contenedor?\n"
            "  → docker compose up -d db\n"
            "  → docker compose ps   (espera estado 'healthy')\n",
            end="",
        )
        raise SystemExit(1)

    print(f"\nnuevos equipos      {n_equipos}")
    print(f"nuevos jugadores    {n_jugadores}")
    print(f"nuevos partidos     {n_partidos}")
    print(f"nuevas filas tabla  {n_clasif}")

    # ── QA post-carga (sin cuota de API) ──────────────────────────────────
    with SessionLocal() as session:
        print("\nTotales en Postgres:")
        for nombre, model in (
            ("equipos", Equipo), ("jugadores", Jugador),
            ("partidos", Partido),
        ):
            total = session.scalar(select(func.count()).select_from(model))
            print(f"  {nombre:<14} {total}")
        clasif = session.scalar(select(func.count()).select_from(Clasificacion))
        print(f"  {'clasificacion':<14} {clasif} filas")

        por_liga = session.execute(
            select(Partido.liga, func.count())
            .group_by(Partido.liga)
            .order_by(Partido.liga)
        ).all()
        print("\nPartidos por liga: " + ", ".join(f"{c}={n}" for c, n in por_liga))

        # QA: ningún (liga, fecha, local) debe existir más de una vez
        duplicados = session.execute(
            select(Partido.liga, Partido.id_local, Partido.utc_date)
            .group_by(Partido.liga, Partido.id_local, Partido.utc_date)
            .having(func.count() > 1)
        ).all()
        print("\nQA anti-duplicados: " + (f"⚠️ {len(duplicados)} repetidos: {duplicados}" if duplicados else "OK"))


if __name__ == "__main__":
    main()
