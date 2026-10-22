# backend/ — API FastAPI + modelos

Aquí vive el **backend** del sistema (Fases 2-3 y 8 del plano maestro):

- `app/` — aplicación FastAPI: rutas (`/fixtures`, `/predictions/{id}`, `/teams/{id}`,
  `/players/{id}`, `/rankings`, `/model-accuracy`, `/health`), esquemas Pydantic,
  conexión SQLAlchemy a Postgres.
- `models/` — código predictivo: Poisson doble (baseline), Dixon-Coles, LightGBM,
  features de equipos y jugadores, backtesting walk-forward.
- `alembic/` — migraciones del esquema Postgres.
- `requirements.txt` + `Dockerfile` + `tests/`.

Despliegue objetivo: **Render** (Fase 11) con auto-deploy desde `main`.
