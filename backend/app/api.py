"""API FastAPI del ANALIZADOR DEPORTIVO — FASE 8.

Sirve lo que el proyecto ya produce (ingesta Fase 2, features/modelo Fases 4-5b,
evaluación honesta Fase 7) con endpoints simples y documentados:

- GET /health                       → estado del servicio + conteos básicos de BD
- GET /fixtures?liga=PD&limite=20   → próximos partidos con las predicciones de TODOS los modelos
- GET /predictions/{partido_id_api} → detalle: partido + predicción por modelo (+ ρ si es DC)
- GET /teams/{equipo_id_api}        → ficha del equipo + clasificación + últimos 5 + próximos 3
- GET /players/{jugador_id_api}     → ficha del jugador (los stats a nivel partido llegan en Fase 6)
- GET /rankings?liga=PD             → tabla de la liga ordenada por posición
- GET /model-accuracy               → accuracy/log loss/Brier REALES por modelo y liga (Fase 7)

Convenciones:
- Los ids son los de football-data.org (PK de todas las tablas desde Fase 3).
- Pydantic valida y documenta todo (Swagger interactivo en /docs).
- CORS configurable por `CORS_ORIGINS` (env: dominios separados por comas).
  Fase 8 abría "*" para no bloquear el desarrollo; Fase 11 lo estrecha:
  solo localhost:3000 por defecto, y los dominios reales via Render (render.yaml).
- Local: .venv/Scripts/python -m backend.app.api  → http://127.0.0.1:8000/docs
  Docker (Fase 8): uvicorn app.api:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, aliased

from .config import CORS_ORIGINS
from .db import SessionLocal
from .models import (
    Clasificacion,
    Equipo,
    Jugador,
    Partido,
    Prediccion,
    RealesVsPrevisto,
)

LIGAS_VALIDAS = ("PD", "PL", "SA", "BL1", "CL")
ESTADOS_POR_JUGAR = ("SCHEDULED", "TIMED")

app = FastAPI(
    title="ANALIZADOR DEPORTIVO API",
    description=(
        "Predicciones de fútbol (Poisson doble + Dixon-Coles) con datos gratis de "
        "football-data.org. Modelos walk-forward, evaluación honesta walk-forward."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,     # Fase 11: el "*" de la Fase 8 se estrecha (env CORS_ORIGINS)
    allow_credentials=False,
    allow_methods=["GET", "HEAD"],  # API pública y de solo lectura
    allow_headers=["*"],
)


def get_session():
    """Una sesión de BD por petición (el patrón canónico de FastAPI + SQLAlchemy)."""
    with SessionLocal() as session:
        yield session


Sesion = Annotated[Session, Depends(get_session)]


# ─────────────────────────────── esquemas Pydantic ───────────────────────────


class Salud(BaseModel):
    estado: str
    db: str
    partidos: int
    predicciones: int
    evaluaciones: int


class PrediccionResumen(BaseModel):
    modelo: str
    prob_local: float | None
    prob_empate: float | None
    prob_visita: float | None
    lam_local: float | None
    lam_visita: float | None
    marcador_estimado: str | None
    prob_over25: float | None
    prob_under25: float | None


class PrediccionDetalle(PrediccionResumen):
    datos: dict | None  # JSONB completo: incluye rho si el modelo es poisson_dc


class PartidosInfo(BaseModel):
    partido_id_api: int
    liga: str
    temporada: int
    fecha_utc: datetime
    estado: str
    jornada: int | None
    local: str
    visitante: str


class Fixture(PartidosInfo):
    predicciones: list[PrediccionResumen]


class PrediccionesPartido(PartidosInfo):
    predicciones: list[PrediccionDetalle]


class ResultadoReciente(PartidosInfo):
    goles_local: int | None
    goles_visitante: int | None


class ClasificacionFila(BaseModel):
    liga: str
    temporada: int
    posicion: int
    equipo_id_api: int
    equipo: str
    jugados: int
    ganados: int
    empatados: int
    perdidos: int
    goles_favor: int
    goles_contra: int
    diferencia_goles: int
    puntos: int
    forma: str | None


class EquipoDetalle(BaseModel):
    equipo_id_api: int
    nombre: str
    nombre_corto: str | None
    tla: str | None
    fundacion: int | None
    escudo_url: str | None
    clasificacion: ClasificacionFila | None
    ultimos5: list[ResultadoReciente]
    proximos3: list[Fixture]


class JugadorDetalle(BaseModel):
    jugador_id_api: int
    nombre: str
    fecha_nac: str | None
    nacionalidad: str | None
    posicion: str | None
    equipo_id_api: int | None
    equipo: str | None
    nota: str


class MetricasModelo(BaseModel):
    modelo: str
    liga: str | None
    evaluados: int
    accuracy: float | None
    log_loss: float | None
    brier: float | None


# ───────────────────────────────── endpoints ────────────────────────────────


def _apodo_map(session: Session, ids: set[int]) -> dict[int, str]:
    """Nombre de equipo por id (evita N+1 queries con un solo SELECT)."""
    if not ids:
        return {}
    filas = session.execute(
        select(Equipo.id_api, Equipo.nombre).where(Equipo.id_api.in_(ids))
    ).all()
    return {fid: nombre for fid, nombre in filas}


def _fila_prediccion(p: Prediccion) -> PrediccionDetalle:
    return PrediccionDetalle(
        modelo=p.modelo,
        prob_local=p.prob_local,
        prob_empate=p.prob_empate,
        prob_visita=p.prob_visita,
        lam_local=p.goles_esperados_local,
        lam_visita=p.goles_esperados_visita,
        marcador_estimado=p.marcador_estimado,
        prob_over25=p.prob_over25,
        prob_under25=p.prob_under25,
        datos=p.datos,
    )


@app.get("/health", response_model=Salud, tags=["infra"])
def health(session: Sesion) -> Salud:
    """Latido del servicio: 200 + conteos si la BD respira."""
    session.execute(select(1))  # ping a Postgres; si muere, la API responde 500
    return Salud(
        estado="ok",
        db="ok",
        partidos=session.scalar(select(func.count()).select_from(Partido)) or 0,
        predicciones=session.scalar(select(func.count()).select_from(Prediccion)) or 0,
        evaluaciones=session.scalar(select(func.count()).select_from(RealesVsPrevisto)) or 0,
    )


@app.get("/fixtures", response_model=list[Fixture], tags=["partidos"])
def fixtures(
    session: Sesion,
    liga: Annotated[str, Query(description="PD/PL/SA/BL1/CL")] = "PD",
    limite: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[Fixture]:
    """Próximos partidos por jugar con las predicciones de TODOS los modelos vivos."""
    if liga not in LIGAS_VALIDAS:
        raise HTTPException(400, f"liga debe ser una de {LIGAS_VALIDAS}")

    local = aliased(Equipo)
    visita = aliased(Equipo)
    filas = (
        session.execute(
            select(Partido, local, visita)
            .join(local, local.id_api == Partido.id_local)
            .join(visita, visita.id_api == Partido.id_visitante)
            .where(Partido.liga == liga, Partido.estado.in_(ESTADOS_POR_JUGAR))
            .order_by(Partido.utc_date)
            .limit(limite)
        )
        .all()
    )
    if not filas:
        return []

    ids = [p.id_api for p, _, _ in filas]
    por_partido: dict[int, list[Prediccion]] = {}
    for pred in session.execute(
        select(Prediccion).where(Prediccion.partido_id_api.in_(ids))
    ).scalars():
        por_partido.setdefault(pred.partido_id_api, []).append(pred)

    salida: list[Fixture] = []
    for p, eq_local, eq_visita in filas:
        preds_fila = [_fila_prediccion(pr) for pr in por_partido.get(p.id_api, [])]
        salida.append(
            Fixture(
                partido_id_api=p.id_api,
                liga=p.liga,
                temporada=p.temporada,
                fecha_utc=p.utc_date,
                estado=p.estado,
                jornada=p.jornada,
                local=eq_local.nombre,
                visitante=eq_visita.nombre,
                predicciones=preds_fila,
            )
        )

    return salida


@app.get("/predictions/{partido_id_api}", response_model=PrediccionesPartido, tags=["modelo"])
def predictions(partido_id_api: int, session: Sesion) -> PrediccionesPartido:
    """Predicción completa de un partido: una fila por modelo guardado (baseline y DC)."""
    local = aliased(Equipo)
    visita = aliased(Equipo)
    p = session.execute(
        select(Partido, local, visita)
        .join(local, local.id_api == Partido.id_local)
        .join(visita, visita.id_api == Partido.id_visitante)
        .where(Partido.id_api == partido_id_api)
    ).first()
    if p is None:
        raise HTTPException(404, "partido no encontrado en la BD")

    partido, eq_local, eq_visita = p
    preds = (
        session.execute(
            select(Prediccion).where(Prediccion.partido_id_api == partido_id_api)
        )
        .scalars()
        .all()
    )
    if not preds:
        raise HTTPException(404, "sin predicciones guardadas para ese partido")

    return PrediccionesPartido(
        partido_id_api=partido.id_api,
        liga=partido.liga,
        temporada=partido.temporada,
        fecha_utc=partido.utc_date,
        estado=partido.estado,
        jornada=partido.jornada,
        local=eq_local.nombre,
        visitante=eq_visita.nombre,
        predicciones=[_fila_prediccion(pr) for pr in sorted(preds, key=lambda x: x.modelo)],
    )


@app.get("/teams/{equipo_id_api}", response_model=EquipoDetalle, tags=["equipos"])
def teams(equipo_id_api: int, session: Sesion) -> EquipoDetalle:
    """Ficha del equipo: clasificación del snapshot + últimos 5 jugados + próximos 3."""
    eq = session.get(Equipo, equipo_id_api)
    if eq is None:
        raise HTTPException(404, "equipo no encontrado en la BD")

    clasi = (
        session.execute(
            select(Clasificacion).where(Clasificacion.equipo_id_api == equipo_id_api)
            .order_by(Clasificacion.temporada.desc())
        )
        .scalars()
        .first()
    )

    def _partido_a_resumen(p: Partido, nombres: dict[int, str], con_goles: bool):
        base = {
            "partido_id_api": p.id_api,
            "liga": p.liga,
            "temporada": p.temporada,
            "fecha_utc": p.utc_date,
            "estado": p.estado,
            "jornada": p.jornada,
            "local": nombres.get(p.id_local, str(p.id_local)),
            "visitante": nombres.get(p.id_visitante, str(p.id_visitante)),
        }
        if con_goles:
            base["goles_local"] = p.goles_local
            base["goles_visitante"] = p.goles_visitante
            return ResultadoReciente(**base)
        return PartidosInfo(**base)

    pares = session.execute(
        select(Partido).where(
            (Partido.id_local == equipo_id_api) | (Partido.id_visitante == equipo_id_api)
        )
    ).scalars().all()

    nombres = _apodo_map(session, {a.id_local for a in pares} | {b.id_visitante for b in pares})

    jugados = sorted(
        (a for a in pares if a.estado == "FINISHED"),
        key=lambda a: a.utc_date, reverse=True,
    )[:5]
    por_jugar = sorted(
        (a for a in pares if a.estado in ESTADOS_POR_JUGAR),
        key=lambda a: a.utc_date,
    )[:3]

    clasif_fila = None
    if clasi is not None:
        clasif_fila = ClasificacionFila(
            liga=clasi.liga,
            temporada=clasi.temporada,
            posicion=clasi.posicion,
            equipo_id_api=clasi.equipo_id_api,
            equipo=eq.nombre,
            jugados=clasi.jugados,
            ganados=clasi.ganados,
            empatados=clasi.empatados,
            perdidos=clasi.perdidos,
            goles_favor=clasi.goles_favor,
            goles_contra=clasi.goles_contra,
            diferencia_goles=clasi.diferencia_goles,
            puntos=clasi.puntos,
            forma=clasi.forma,
        )

    return EquipoDetalle(
        equipo_id_api=eq.id_api,
        nombre=eq.nombre,
        nombre_corto=eq.nombre_corto,
        tla=eq.tla,
        fundacion=eq.fundacion,
        escudo_url=eq.escudo_url,
        clasificacion=clasif_fila,
        ultimos5=[_partido_a_resumen(a, nombres, True) for a in jugados],
        proximos3=[
            Fixture(
                **_partido_a_resumen(a, nombres, False).model_dump(),
                predicciones=[],
            )
            for a in por_jugar
        ],
    )


@app.get("/players/{jugador_id_api}", response_model=JugadorDetalle, tags=["jugadores"])
def players(jugador_id_api: int, session: Sesion) -> JugadorDetalle:
    """Ficha del jugador. Los stats por partido llegarán con el modelo de Fase 6."""
    jug = session.get(Jugador, jugador_id_api)
    if jug is None:
        raise HTTPException(404, "jugador no encontrado en la BD")

    equipo = session.get(Equipo, jug.equipo_id_api) if jug.equipo_id_api else None
    return JugadorDetalle(
        jugador_id_api=jug.id_api,
        nombre=jug.nombre,
        fecha_nac=jug.fecha_nac.isoformat() if jug.fecha_nac else None,
        nacionalidad=jug.nacionalidad,
        posicion=jug.posicion,
        equipo_id_api=jug.equipo_id_api,
        equipo=equipo.nombre if equipo else None,
        nota="stats por partido se llenan en la Fase 6 (modelo de jugador)",
    )


@app.get("/rankings", response_model=list[ClasificacionFila], tags=["ligas"])
def rankings(
    session: Sesion,
    liga: Annotated[str | None, Query(description="PD/PL/SA/BL1/CL; vacío = todas")] = None,
    temporada: int | None = None,
) -> list[ClasificacionFila]:
    """Tabla de posiciones del snapshot de la Fase 3, ordenada por posición."""
    stmt = (
        select(Clasificacion, Equipo.nombre)
        .join(Equipo, Equipo.id_api == Clasificacion.equipo_id_api)
        .order_by(Clasificacion.liga, Clasificacion.posicion)
    )
    if liga is not None:
        if liga not in LIGAS_VALIDAS:
            raise HTTPException(400, f"liga debe ser una de {LIGAS_VALIDAS}")
        stmt = stmt.where(Clasificacion.liga == liga)
    if temporada is not None:
        stmt = stmt.where(Clasificacion.temporada == temporada)

    return [
        ClasificacionFila(
            liga=c.liga,
            temporada=c.temporada,
            posicion=c.posicion,
            equipo_id_api=c.equipo_id_api,
            equipo=nombre,
            jugados=c.jugados,
            ganados=c.ganados,
            empatados=c.empatados,
            perdidos=c.perdidos,
            goles_favor=c.goles_favor,
            goles_contra=c.goles_contra,
            diferencia_goles=c.diferencia_goles,
            puntos=c.puntos,
            forma=c.forma,
        )
        for c, nombre in session.execute(stmt).all()
    ]


@app.get("/model-accuracy", response_model=list[MetricasModelo], tags=["modelo"])
def model_accuracy(
    session: Sesion,
    liga: Annotated[str | None, Query(description="PD/PL/SA/BL1/CL; vacío = todas")] = None,
) -> list[MetricasModelo]:
    """Accuracy/log loss/Brier REALES por modelo y liga (backtesting walk-forward de la Fase 7).

    Aquí está la comparación honesta: poisson_doble vs poisson_dc, cada uno
    evaluado sobre los mismos partidos terminados (UNIQUE por (partido, modelo)).
    """
    if liga is not None and liga not in LIGAS_VALIDAS:
        raise HTTPException(400, f"liga debe ser una de {LIGAS_VALIDAS}")

    stmt = (
        select(
            RealesVsPrevisto.modelo,
            Partido.liga,
            func.count().label("evaluados"),
            func.avg(case((RealesVsPrevisto.acierto_1x2.is_(True), 1), else_=0)).label("accuracy"),
            func.avg(RealesVsPrevisto.log_loss).label("log_loss"),
            func.avg(RealesVsPrevisto.brier_score).label("brier"),
        )
        .join(Partido, Partido.id_api == RealesVsPrevisto.partido_id_api)
        .group_by(RealesVsPrevisto.modelo, Partido.liga)
        .order_by(RealesVsPrevisto.modelo, Partido.liga)
    )
    if liga is not None:
        stmt = stmt.where(Partido.liga == liga)

    return [
        MetricasModelo(
            modelo=modelo,
            liga=liga_fila,
            evaluados=evaluados,
            accuracy=accuracy,
            log_loss=log_loss,
            brier=brier,
        )
        for modelo, liga_fila, evaluados, accuracy, log_loss, brier in session.execute(stmt).all()
    ]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
