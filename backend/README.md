# backend/ — API FastAPI + modelos

Aquí vive el **backend** del sistema (Fases 3, 5, 7, 8 del plano maestro):

## Estructura (estado actual)

```
backend/
├── app/
│   ├── config.py    URL de BD desde el .env raíz (single source of truth)
│   ├── consola.py   helper UTF-8 (consolas Windows cp1252)
│   ├── db.py        engine + SessionLocal + Base (SQLAlchemy 2)
│   ├── models.py    esquema: equipos, jugadores, partidos, clasificacion,
│   │                stats_partido, stats_jugador, prediccion, reales_vs_previsto
│   └── load.py      cargador idempotente JSON crudo (pipeline/raw) → Postgres
├── alembic.ini      migraciones (la URL se inyecta desde app/config.py)
├── alembic/         env.py + versions/ (esquema versionado)
└── requirements.txt (sqlalchemy 2.1.6 · alembic 1.20.1 · psycopg 3.3.6)
```

## Comandos (desde la raíz del repo, con el venv del proyecto)

```powershell
# BD en marcha (una vez por sesión de trabajo)
docker compose up -d db

# Carga idempotente de los datos crudos (re-corrible sin duplicar)
.venv\Scripts\python -m backend.app.load

# Migraciones (solo cuando se cambie el esquema en models.py)
.venv\Scripts\alembic.exe -c backend\alembic.ini revision --autogenerate -m "cambio X"
.venv\Scripts\alembic.exe -c backend\alembic.ini upgrade head

# SQL directo dentro del contenedor (práctica libre)
docker exec analizador_db psql -U analizador -d analizador -c "SELECT ..."
```

## Claves de diseño

- **PK = id de la API** en equipos/jugadores/partidos → upsert natural (merge) y
  reproducibilidad total entre corridas (idempotencia demostrada: 2a pasada = 0 nuevos).
- **Datos crudos jamás mutable** en el backend: estados FINISHED/SCHEDULED/CANCELLED
  se guardan tal cual; lo derivado se computa en Fases 4-5.
- **clasificacion** Added como tabla real (fuente: standings TOTAL por liga×tempora×equipo).
- `prediccion`/`reales_vs_previsto`: únicas por (partido, modelo) → el motor de
  aciertos vive ahí (Fases 8 y 13).

Despliegue objetivo: **Render** (Fase 11) con `Dockerfile` y migraciones al arrancar.
