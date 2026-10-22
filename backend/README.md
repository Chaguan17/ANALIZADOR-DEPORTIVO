# backend/ — API FastAPI + modelos de predicción

Aquí vive el **backend** del sistema (Fases 3, 5, 5b, 7 y 8 del plano maestro).

## Estructura (estado actual)

```
backend/
├── app/
│   ├── config.py       URL de BD desde el .env raíz (single source of truth)
│   ├── consola.py      helper UTF-8 (consolas Windows cp1252)
│   ├── db.py           engine + SessionLocal + Base (SQLAlchemy 2)
│   ├── models.py       esquema: equipos, jugadores, partidos, clasificacion,
│   │                   stats_partido, stats_jugador, prediccion, reales_vs_previsto
│   ├── load.py         cargador idempotente JSON crudo (pipeline/raw) → Postgres
│   ├── features.py     features walk-forward de equipos (Fase 4)
│   ├── modelo.py       baseline Poisson doble + persistencia de predicciones (Fase 5)
│   ├── modelo_dc.py    Dixon-Coles: τ de marcadores bajos + ρ por liga (Fase 5b)
│   ├── evaluacion.py   backtesting walk-forward: log loss/Brier/calibración (Fase 7)
│   └── api.py          API FastAPI: /health /fixtures /predictions /teams
│                       /players /rankings /model-accuracy + Swagger /docs (Fase 8)
├── alembic.ini         migraciones (la URL se inyecta desde app/config.py)
├── alembic/            env.py + versions/ (esquema versionado)
├── Dockerfile          imagen uvicorn (Fase 8; servicio "api" del docker-compose)
└── requirements.txt    sqlalchemy · alembic · psycopg · fastapi · pydantic · uvicorn
```

## Comandos (desde la raíz del repo, con el venv del proyecto)

```powershell
# BD + API en marcha (una vez por sesión de trabajo)
docker compose up -d db                     # Postgres
docker compose up -d db api                 # Postgres + API dockerizada (Fase 8)
# → Swagger interactivo: http://localhost:8000/docs

# API en modo desarrollo (sin Docker, hot-reload del venv)
.venv\Scripts\python -m backend.app.api     # http://127.0.0.1:8000/docs

# Carga idempotente de los datos crudos (re-corrible sin duplicar)
.venv\Scripts\python -m backend.app.load

# Modelos
.venv\Scripts\python -m backend.app.modelo            # demo baseline Poisson doble
.venv\Scripts\python -m backend.app.modelo --todas --guardar   # predicciones vivas → BD
.venv\Scripts\python -m backend.app.modelo_dc --todas --guardar --vivas  # Dixon-Coles
.venv\Scripts\python -m backend.app.evaluacion --todas --guardar         # backtesting → BD

# Migraciones (solo cuando se cambie el esquema en models.py)
.venv\Scripts\alembic.exe -c backend\alembic.ini revision --autogenerate -m "cambio X"
.venv\Scripts\alembic.exe -c backend\alembic.ini upgrade head

# SQL directo dentro del contenedor (práctica libre)
docker exec analizador_db psql -U analizador -d analizador -c "SELECT ..."
```

## Endpoints (Fase 8)

| Endpoint | Qué da |
|---|---|
| `GET /health` | latido + conteos (partidos, predicciones, evaluaciones) |
| `GET /fixtures?liga=PD&limite=20` | próximos partidos con las predicciones de **todos** los modelos |
| `GET /predictions/{partido_id_api}` | detalle por modelo (JSONB completo, incluye ρ en DC) |
| `GET /teams/{equipo_id_api}` | ficha + clasificación + últimos 5 + próximos 3 |
| `GET /players/{jugador_id_api}` | ficha del jugador (stats a nivel partido llegan en Fase 6) |
| `GET /rankings?liga=PD` | tabla de posiciones del snapshot |
| `GET /model-accuracy` | accuracy/log loss/Brier REALES por modelo y liga (Fase 7) |

Los ids son los de football-data.org. CORS abierto `["*"]` (se estrechará al
dominio de Vercel en producción). Errores honestos: 400 liga inválida, 404 id inexistente.

## Claves de diseño

- **PK = id de la API** en equipos/jugadores/partidos → upsert natural (merge) y
  reproducibilidad total entre corridas (idempotencia demostrada: segunda pasada = 0 nuevos).
- **Datos crudos inmutables** en el backend: estados FINISHED/SCHEDULED/CANCELLED
  se guardan tal cual; lo derivado se computa en Fases 4-5.
- **clasificación** añadida como tabla real (fuente del endpoint /rankings).
- `prediccion`/`reales_vs_previsto`: únicas por (partido, modelo) → el motor de
  aciertos vive ahí; varios modelos coexisten (hoy: `poisson_doble` y `poisson_dc`).
- **API sin estado**: cada petición abre su sesión de BD (`Depends(get_session)`).

Despliegue objetivo: **Render** (Fase 11) con este `Dockerfile` y migraciones al arrancar.
