# ⚽ ANALIZADOR DEPORTIVO

Sistema de predicciones de fútbol basado en el rendimiento de **equipos** y **jugadores**,
con pipeline de datos automatizado, CI/CD y un despliegue 100% gratuito.

**Propósito dual:** predicciones deportivas con medida de precisión honesta (backtesting,
calibración) **y** un proyecto de portafolio Full Stack + DevOps construido con estándares
reales de la industria.

[![CI backend](https://github.com/Chaguan17/ANALIZADOR-DEPORTIVO/actions/workflows/ci-backend.yml/badge.svg)](https://github.com/Chaguan17/ANALIZADOR-DEPORTIVO/actions/workflows/ci-backend.yml)
[![CI web](https://github.com/Chaguan17/ANALIZADOR-DEPORTIVO/actions/workflows/ci-web.yml/badge.svg)](https://github.com/Chaguan17/ANALIZADOR-DEPORTIVO/actions/workflows/ci-web.yml)
<!-- Data Refresh (cron) llegará con la Fase 12 -->

## 🧱 Stack

| Capa | Tecnología |
|---|---|
| Frontend | Next.js + TypeScript + Tailwind (desplegado en Vercel) |
| Backend API | Python + FastAPI + Pydantic (desplegado en Render) |
| Modelado | pandas · Poisson doble / Dixon-Coles · LightGBM |
| Base de datos | PostgreSQL (local: Docker · nube: Neon) |
| Pipeline de datos | Python + GitHub Actions (cron) |
| CI/CD | GitHub Actions + Docker |

## 📁 Estructura

```
├── web/                 UI Next.js (predicciones, perfiles, rankings)
├── backend/             API FastAPI + modelos predictivos + pruebas pytest
├── pipeline/            Ingesta de datos de football-data.org
├── proyecto/            Gobernanza: contexto, memoria y plano maestro del proyecto
└── .github/workflows/   CI backend · CI web · (deploy y cron: fases 11-12)
```

## 🚀 Inicio rápido (desarrollo local)

```powershell
# 1. Base de datos Postgres local
docker compose up -d db

# 2. Variables de entorno
copy .env.example .env    # luego rellena FOOTBALL_API_KEY

# 3. Ingesta de datos + API + UI (fases siguientes del plan)
```

## ☁️ Despliegue (Fase 11 — 3 servicios gratuitos)

| Servicio | Plataforma | Cómo se actualiza |
|---|---|---|
| UI (Next.js, `web/`) | [Vercel](https://vercel.com) | push a `main` (producción) · pull requests (previews) |
| API (FastAPI) | [Render](https://render.com) | Blueprint [`render.yaml`](render.yaml): cada push reconstruye la imagen y aplica las migraciones al arrancar |
| Base de datos | [Neon](https://neon.tech) | migraciones Alembic · schema Postgres 16 |

Variables de entorno (ninguna vive en el repo):

| Variable | Dónde | Valor |
|---|---|---|
| `DATABASE_URL` | Render (secreto) | DSN de Neon en formato SQLAlchemy: `postgresql+psycopg://usuario:password@host/neondb?sslmode=require` |
| `NEXT_PUBLIC_API_URL` | Vercel | URL pública de la API (`https://analizador-api-iule.onrender.com`) — la lee el navegador |
| `API_URL_SERVIDOR` | Vercel | La misma URL de la API — la usa el SSR de Next (ver [`web/.env.example`](web/.env.example)) |
| `CORS_ORIGINS` | Render (env, en [`render.yaml`](render.yaml)) | Dominios que llaman a la API desde el navegador: el dominio Vercel + `http://localhost:3000` en desarrollo |
| `FOOTBALL_API_KEY` | `.env` local (y GitHub Secrets desde la Fase 12) | clave de football-data.org |

El free tier de Render duerme tras 15 min sin tráfico (~1 min de arranque en frío);
el health check del servicio es `GET /health`.

## 📡 Fuentes de datos

- [football-data.org](https://www.football-data.org) (tier gratuito, 10 req/min) —
  partidos, clasificación, plantillas y goleadores de las grandes ligas europeas.
- Respaldo puntual para estadísticas de jugador: FBref / Understat.

## 🧭 Hoja de ruta

El plan completo (15 fases: gobernanza → ingesta → base de datos → modelos →
API → UI → CI/CD → despliegue → cron) vive en [`proyecto/02_PLANO_MAESTRO.md`](proyecto/02_PLANO_MAESTRO.md),
con el diseño en [`proyecto/00_CONTEXTO.md`](proyecto/00_CONTEXTO.md) y la bitácora de
trabajo en [`proyecto/01_MEMORIA.md`](proyecto/01_MEMORIA.md).

## 📄 Licencia

Por decidir (MIT recomendado al ser repositorio público de portafolio).
