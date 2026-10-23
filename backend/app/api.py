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
from .stats_filas import filas_de_liga
from .tarjetas import (
    bloques_de,
    calidad_de_filas,
    equipos_tarjetas,
    prediccion_de_filas,
    propensos_equipo,
    propensos_liga,
)
from .torneo import FORMA_POR_DEFECTO, construir_torneo, leer_ledger

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


class TorneoLiga(BaseModel):
    """Recorte por liga de un modelo en el torneo vivo (Fase 13)."""

    liga: str
    evaluados: int
    aciertos: int
    accuracy: float | None


class TorneoO25(BaseModel):
    """Over/under 2.5 del modelo: solo voces que emiten esa probabilidad."""

    evaluados: int
    aciertos: int
    accuracy: float | None


class TorneoForma(BaseModel):
    """Último partido confirmado de una voz (la "forma" del modelo)."""

    partido_id_api: int
    liga: str
    fecha_utc: str
    local: str
    visitante: str
    goles_local: int
    goles_visitante: int
    elegido: str
    resultado: str
    acierto_1x2: bool
    log_loss_prediccion: float | None


class TorneoModelo(BaseModel):
    """El torneo visto como tabla de posiciones (Fase 13)."""

    modelo: str
    evaluados: int
    aciertos: int
    accuracy: float | None
    log_loss: float | None
    brier: float | None
    o25: TorneoO25 | None
    por_liga: list[TorneoLiga]
    forma: list[TorneoForma]


# ───────────── esquemas de tarjetas (Fase 15 — fuente ESPN) ────────────────


class CalidadLinea(BaseModel):
    """Calidad walk-forward para UNA línea over/under."""

    linea: float
    evaluados: int
    aciertos: int
    accuracy: float | None
    mae: float | None


class CoberturaEspn(BaseModel):
    """Cobertura honesta del dominio respecto a los jugados de la liga."""

    jugados: int
    con_datos: int


class JugadorEvento(BaseModel):
    """Un evento de tarjeta real de la ficha del partido."""

    nombre: str
    minuto: int | None
    tipo: str


class TarjetaJugador(BaseModel):
    """Jugador propenso a tarjeta (por APARICIÓN: ESPN no da minutos)."""

    nombre: str
    amarillas: int
    rojas: int
    apariciones: int
    tasa: float | None


class TarjetaLadoReal(BaseModel):
    """Lo real de un lado (reportado; las rojas nunca van a la predicción)."""

    amarillas: int
    rojas: int
    por_jugador: list[JugadorEvento]


class PredTarjetas(BaseModel):
    """La predicción del modelo de tarjetas para un partido."""

    tarjetas_esperadas: float
    prob_over_2_5: float
    prob_over_3_5: float
    por_equipo: dict[str, float | None]


class TarjetasPartido(BaseModel):
    """Todo lo que la web necesita para la sección de tarjetas de un partido."""

    partido_id_api: int
    liga: str
    fecha_utc: datetime
    estado: str
    jornada: int | None
    local: str
    visitante: str
    fuente: str | None
    cobertura: CoberturaEspn
    calidad: list[CalidadLinea]
    reales: dict[str, TarjetaLadoReal] | None
    prediccion: PredTarjetas | None
    propensos: dict[str, list[TarjetaJugador]] | None
    notas: list[str]


class TarjetaEquipoTemporada(BaseModel):
    """Resumen por equipo de la liga (la tabla de /tarjetas?liga)."""

    equipo_id_api: int
    nombre: str
    partidos: int
    tarjetas: int
    tasa: float


class TarjetaJugadorLiga(TarjetaJugador):
    """Propenso con su equipo, para el ranking de liga."""

    equipo: str
    equipo_id_api: int


class TarjetasLiga(BaseModel):
    """La vista de liga completa del modelo de tarjetas."""

    liga: str
    cobertura: CoberturaEspn
    calidad: list[CalidadLinea]
    equipos: list[TarjetaEquipoTemporada]
    propensos: list[TarjetaJugadorLiga]
    notas: list[str]


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


@app.get("/torneo", response_model=list[TorneoModelo], tags=["modelo"])
def torneo(
    session: Sesion,
    forma: Annotated[int, Query(ge=1, le=25, description="Partidos recientes por voz")] = FORMA_POR_DEFECTO,
) -> list[TorneoModelo]:
    """Ranking vivo de los 3 modelos, como una tabla de posiciones (Fase 13).

    Lee el ledger `reales_vs_previsto` que el cron de la Fase 12 refresca con
    la evaluación walk-forward y lo arma por modelo: tasa de acierto 1X2,
    log loss/Brier medios, over/under 2.5 (solo las voces que emiten esa
    probabilidad), el recorte por liga y la forma de los últimos
    confirmados. Orden: mejor accuracy 1X2 primero; empate → más evaluados.
    """
    aggs, formas_de = leer_ledger(session, forma)
    return [TorneoModelo(**t) for t in construir_torneo(aggs, formas_de)]


# ─────────────── tarjetas (Fase 15 — datos ESPN, on-request) ────────────────

NOTAS_TARJETAS = [
    "modelo on-request: shrinkage hacia la media de liga + Poisson",
    "las rojas no se predicen (evento raro); solo se reportan como reales",
    "fuente de stats: ESPN (site.api.espn.com), API no oficial sin contrato",
    "backfill ESPN en curso: la cobertura sube con cada corrida del cron",
    "propensos calculados POR APARICION; ESPN no entrega minutos por jugador",
]


def _cobertura_de(session: Session, liga: str, con_datos: int) -> CoberturaEspn:
    """(jugados, con datos) de la liga para la nota de cobertura honesta."""
    jugados = session.scalar(
        select(func.count(Partido.id_api)).where(
            Partido.liga == liga, Partido.estado == "FINISHED"
        )
    )
    return CoberturaEspn(jugados=jugados or 0, con_datos=con_datos)


def _calidad_a_lineas(calidad: dict) -> list[CalidadLinea]:
    return [
        CalidadLinea(
            linea=float(linea),
            evaluados=r["evaluados"],
            aciertos=r["aciertos"],
            accuracy=r["accuracy"],
            mae=r["mae"],
        )
        for linea, r in calidad["lineas"].items()
    ]


def _filas_completas(filas: list[dict]) -> int:
    """Partidos con AMBOS lados de tarjetas completos (la cobertura cierta del dominio)."""
    return sum(1 for f in filas if all(b is not None for b in bloques_de(f)))


@app.get("/tarjetas", response_model=TarjetasLiga, tags=["stats"])
def tarjetas_liga(
    session: Sesion,
    liga: Annotated[str, Query(min_length=2, max_length=3)],
) -> TarjetasLiga:
    """Tarjetas de la liga: tasas por equipo encogidas + propensos por aparicion.

    Datos de la ingesta ESPN (stats_partido); el modelo corre en el request.
    """
    if liga not in LIGAS_VALIDAS:
        raise HTTPException(400, f"liga debe ser una de {LIGAS_VALIDAS}")

    filas = filas_de_liga(session, liga)
    crews = equipos_tarjetas(filas)
    nombres = _apodo_map(session, set(crews))
    equipos = [
        TarjetaEquipoTemporada(
            equipo_id_api=eid,
            nombre=nombres.get(eid, str(eid)),
            partidos=c["partidos"],
            tarjetas=c["tarjetas"],
            tasa=c["tasa"],
        )
        for eid, c in sorted(crews.items(), key=lambda kv: (-kv[1]["tarjetas"], kv[0]))
    ]
    propensos = [
        TarjetaJugadorLiga(
            nombre=f["nombre"],
            amarillas=f["amarillas"],
            rojas=f["rojas"],
            apariciones=f["apariciones"],
            tasa=f["tasa"],
            equipo=nombres.get(f["equipo_id_api"], str(f["equipo_id_api"])),
            equipo_id_api=f["equipo_id_api"],
        )
        for f in propensos_liga(filas)
    ]
    return TarjetasLiga(
        liga=liga,
        cobertura=_cobertura_de(session, liga, _filas_completas(filas)),
        calidad=_calidad_a_lineas(calidad_de_filas(filas)),
        equipos=equipos,
        propensos=propensos,
        notas=NOTAS_TARJETAS,
    )


@app.get("/partido/{partido_id_api}/tarjetas", response_model=TarjetasPartido, tags=["stats"])
def tarjetas_partido(partido_id_api: int, session: Sesion) -> TarjetasPartido:
    """Tarjetas de UN partido: reales (si jugado) + prediccion walk-forward + propensos."""
    local = aliased(Equipo)
    visita = aliased(Equipo)
    fila_p = session.execute(
        select(Partido, local, visita)
        .join(local, local.id_api == Partido.id_local)
        .join(visita, visita.id_api == Partido.id_visitante)
        .where(Partido.id_api == partido_id_api)
    ).first()
    if fila_p is None:
        raise HTTPException(404, "partido no encontrado en la BD")
    partido, eq_local, eq_visita = fila_p
    liga = partido.liga
    filas = filas_de_liga(session, liga)

    propia = next((f for f in filas if f["partido"] == partido.id_api), None)
    reales: dict[str, TarjetaLadoReal] | None = None
    if propia is not None:
        bl, bv = bloques_de(propia)
        if bl is not None and bv is not None:
            reales = {
                "local": TarjetaLadoReal(
                    amarillas=bl.get("amarillas") or 0,
                    rojas=bl.get("rojas") or 0,
                    por_jugador=[
                        JugadorEvento(nombre=j["nombre"], minuto=j.get("minuto"), tipo=j["tipo"])
                        for j in bl.get("por_jugador") or []
                    ],
                ),
                "visitante": TarjetaLadoReal(
                    amarillas=bv.get("amarillas") or 0,
                    rojas=bv.get("rojas") or 0,
                    por_jugador=[
                        JugadorEvento(nombre=j["nombre"], minuto=j.get("minuto"), tipo=j["tipo"])
                        for j in bv.get("por_jugador") or []
                    ],
                ),
            }

    prediccion = prediccion_de_filas(filas, partido.id_local, partido.id_visitante, partido.utc_date)
    propensos = {
        "local": [TarjetaJugador(**f) for f in propensos_equipo(filas, partido.id_local)],
        "visitante": [TarjetaJugador(**f) for f in propensos_equipo(filas, partido.id_visitante)],
    }

    notas = list(NOTAS_TARJETAS)
    if partido.estado in ESTADOS_POR_JUGAR:
        notas.insert(0, "partido por jugar: solo prediccion")
    elif reales is None:
        notas.insert(0, "este partido aun no tiene datos ESPN (backfill en curso)")

    return TarjetasPartido(
        partido_id_api=partido.id_api,
        liga=liga,
        fecha_utc=partido.utc_date,
        estado=partido.estado,
        jornada=partido.jornada,
        local=eq_local.nombre,
        visitante=eq_visita.nombre,
        fuente="espn" if propia is not None else None,
        cobertura=_cobertura_de(session, liga, _filas_completas(filas)),
        calidad=_calidad_a_lineas(calidad_de_filas(filas)),
        reales=reales,
        prediccion=prediccion,
        propensos=propensos,
        notas=notas,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
