"""Modelos ORM — esquema Postgres de ANALIZADOR DEPORTIVO (Fase 3).

Diseño de datos:
- `equipos` y `jugadores` usan como clave primaria el **id de la API** → el upsert
  (session.merge) es naturalmente idempotente y reproducible entre sesiones.
- `partidos` conserva el estado crudo de la API (FINISHED/SCHEDULED/.../CANCELLED)
  y los marcadores completo + medio-tiempo; las métricas DERIVADAS se calcularán
  en Fases 4-5, nunca se sobrescriben los datos crudos.
- `clasificacion` = snapshot por equipo-por-liga-por-temporada (fuente: standings).
- `stats_partido` / `stats_jugador`: creadas vacías (JSONB extensibles), se llenan
  en Fases 4-8 con el insumo de modelos.
- `prediccion` / `reales_vs_previsto`: el corazón del sistema de aciertos (Fases 8, 13).
  Única predicción "viva" por (partido, modelo): la Fase 8 borra+reescribe al recalcular.

⚠️ Nota de esquema: el plano original hablaba de tablas `stats_*`; aquí `clasificacion`
se añade como tabla real (source-of-truth del endpoint standings). Cambio registrado
en proyecto/00_CONTEXTO.md (decisiones).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Equipo(Base):
    __tablename__ = "equipos"

    id_api: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    nombre_corto: Mapped[str | None] = mapped_column(String(100))
    tla: Mapped[str | None] = mapped_column(String(8))  # abreviatura de 3 letras (ej. RMA)
    fundacion: Mapped[int | None] = mapped_column(Integer)
    escudo_url: Mapped[str | None] = mapped_column(String(400))


class Jugador(Base):
    __tablename__ = "jugadores"

    id_api: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    fecha_nac: Mapped[date | None] = mapped_column(Date)
    nacionalidad: Mapped[str | None] = mapped_column(String(80))
    posicion: Mapped[str | None] = mapped_column(String(40))
    equipo_id_api: Mapped[int | None] = mapped_column(ForeignKey("equipos.id_api"))


class Partido(Base):
    __tablename__ = "partidos"

    id_api: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    liga: Mapped[str] = mapped_column(String(16), index=True)  # PD/PL/SA/BL1/CL
    temporada: Mapped[int] = mapped_column(Integer, index=True)  # año de inicio (2026-27 → 2026)
    etiqueta_etapa: Mapped[str | None] = mapped_column(String(60))  # stage, ej. fase de liga CL
    utc_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    estado: Mapped[str] = mapped_column(String(20))  # FINISHED/SCHEDULED/TIMED/CANCELLED/...
    jornada: Mapped[int | None] = mapped_column(Integer)
    id_local: Mapped[int] = mapped_column(ForeignKey("equipos.id_api"), index=True)
    id_visitante: Mapped[int] = mapped_column(ForeignKey("equipos.id_api"), index=True)
    goles_local: Mapped[int | None] = mapped_column(Integer)
    goles_visitante: Mapped[int | None] = mapped_column(Integer)
    ganador: Mapped[str | None] = mapped_column(String(12))  # HOME_TEAM/AWAY_TEAM/DRAW
    medio_tiempo_local: Mapped[int | None] = mapped_column(Integer)
    medio_tiempo_visitante: Mapped[int | None] = mapped_column(Integer)


class Clasificacion(Base):
    __tablename__ = "clasificacion"

    liga: Mapped[str] = mapped_column(String(16), primary_key=True)
    temporada: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipo_id_api: Mapped[int] = mapped_column(ForeignKey("equipos.id_api"), primary_key=True)
    posicion: Mapped[int] = mapped_column(Integer)
    jugados: Mapped[int] = mapped_column(Integer)
    ganados: Mapped[int] = mapped_column(Integer)
    empatados: Mapped[int] = mapped_column(Integer)
    perdidos: Mapped[int] = mapped_column(Integer)
    goles_favor: Mapped[int] = mapped_column(Integer)
    goles_contra: Mapped[int] = mapped_column(Integer)
    diferencia_goles: Mapped[int] = mapped_column(Integer)
    puntos: Mapped[int] = mapped_column(Integer)
    forma: Mapped[str | None] = mapped_column(String(100))  # ej. "V,V,E,D,V"


class StatsPartido(Base):
    """Estadísticas a nivel de equipo-partido (JSONB extensibles; se llena en Fases 4+)."""

    __tablename__ = "stats_partido"

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    partido_id_api: Mapped[int] = mapped_column(ForeignKey("partidos.id_api"), index=True)
    equipo_id_api: Mapped[int] = mapped_column(ForeignKey("equipos.id_api"), index=True)
    datos: Mapped[dict] = mapped_column(JSONB, default=dict)


class StatsJugador(Base):
    """Estadísticas a nivel de jugador-partido (JSONB extensibles; se llena en Fases 4+)."""

    __tablename__ = "stats_jugador"

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    jugador_id_api: Mapped[int] = mapped_column(ForeignKey("jugadores.id_api"), index=True)
    partido_id_api: Mapped[int | None] = mapped_column(ForeignKey("partidos.id_api"), index=True)
    datos: Mapped[dict] = mapped_column(JSONB, default=dict)


class Prediccion(Base):
    """Predicción "viva" de un partido (Fases 5, 8, 13). Única por (partido, modelo)."""

    __tablename__ = "prediccion"
    __table_args__ = (UniqueConstraint("partido_id_api", "modelo"),)

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    partido_id_api: Mapped[int] = mapped_column(ForeignKey("partidos.id_api"), index=True)
    modelo: Mapped[str] = mapped_column(String(50))  # p. ej. "poisson_doble", "lightgbm_v1"
    generado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    prob_local: Mapped[float | None] = mapped_column(Numeric(7, 4))
    prob_empate: Mapped[float | None] = mapped_column(Numeric(7, 4))
    prob_visita: Mapped[float | None] = mapped_column(Numeric(7, 4))
    goles_esperados_local: Mapped[float | None] = mapped_column(Numeric(6, 2))
    goles_esperados_visita: Mapped[float | None] = mapped_column(Numeric(6, 2))
    marcador_estimado: Mapped[str | None] = mapped_column(String(10))  # ej. "2-1"
    prob_over25: Mapped[float | None] = mapped_column(Numeric(7, 4))
    prob_under25: Mapped[float | None] = mapped_column(Numeric(7, 4))
    datos: Mapped[dict | None] = mapped_column(JSONB)


class RealesVsPrevisto(Base):
    """Evaluación posterior de una predicción al confirmarse el resultado (Fases 7, 13)."""

    __tablename__ = "reales_vs_previsto"
    __table_args__ = (UniqueConstraint("partido_id_api", "modelo"),)

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    partido_id_api: Mapped[int] = mapped_column(ForeignKey("partidos.id_api"), index=True)
    modelo: Mapped[str] = mapped_column(String(50))
    evaluado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    acierto_1x2: Mapped[bool | None] = mapped_column(Boolean)
    brier_score: Mapped[float | None] = mapped_column(Numeric(8, 6))
    log_loss: Mapped[float | None] = mapped_column(Numeric(8, 6))
    datos: Mapped[dict | None] = mapped_column(JSONB)
