# Backend FastAPI — ANALIZADOR DEPORTIVO (Fase 8)
#
# Uso (desde la raíz del repo, el compose se encarga de build y red):
#   docker compose build api
#   docker compose up -d api
#   # Swagger: http://localhost:8000/docs
#
# La imagen solo necesita requirements.txt + app/ (todo lo demás — venv,
# .venv, datos crudos — vive fuera del contenedor).

FROM python:3.14-slim

WORKDIR /srv

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]
