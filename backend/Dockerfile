# Backend FastAPI — ANALIZADOR DEPORTIVO (Fases 8 y 11)
#
# Uso local (docker compose construye y levanta ambos servicios):
#   docker compose build api
#   docker compose up -d api
#   # Swagger: http://localhost:8000/docs
#
# Fase 11 (deploy): Render construye esta MISMA imagen desde el repo
# (runtime docker; dockerfilePath: ./backend/Dockerfile en render.yaml).
#
# Estructura del contenedor — espeja el repo para que alembic y la app
# compartan una sola fuente de verdad (los modelos únicos de app/models.py):
#   /srv/backend/app/         paquete "app"      → lo sirve uvicorn
#   /srv/backend/alembic/     migraciones        → las aplica el arranque
#
# Al arrancar el contenedor:
#   1. `alembic upgrade head` aplica (o confirma) el esquema — idempotente:
#      en el free tier de Render el servicio duerme y despierta, y cada
#      arranque deja el esquema de la BD sincronizado con el código.
#   2. `exec uvicorn ...` reemplaza el shell (señales SIGTERM limpias →
#      zero-downtime deploys).
#   3. Puerto: $PORT si el runtime lo define (Render usa 10000 por defecto),
#      con fallback 8000 para desarrollo local (compose mapea 8000:8000).

FROM python:3.14-slim

WORKDIR /srv/backend

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.api:app --app-dir /srv/backend --host 0.0.0.0 --port ${PORT:-8000}"]
