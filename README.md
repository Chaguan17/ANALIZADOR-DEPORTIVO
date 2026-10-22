# ⚽ ANALIZADOR DEPORTIVO

Sistema de predicciones de fútbol basado en el rendimiento de **equipos** y **jugadores**,
con pipeline de datos automatizado, CI/CD y un despliegue 100% gratuito.

**Propósito dual:** predicciones deportivas con medida de precisión honesta (backtesting,
calibración) **y** un proyecto de portafolio Full Stack + DevOps construido con estándares
reales de la industria.

<!-- BADGES CI/CD (se añaden en la Fase 10, cuando existan los workflows de GitHub Actions)
[![CI](https://github.com/USUARIO/REPO/actions/workflows/ci.yml/badge.svg)](...)
[![Data Refresh](https://github.com/USUARIO/REPO/actions/workflows/data-refresh.yml/badge.svg)](...)
-->

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
├── frontend/           UI Next.js (predicciones, perfiles, rankings)
├── backend/            API FastAPI + modelos predictivos
├── pipeline/           Ingesta de datos de football-data.org
├── proyecto/           Gobernanza: contexto, memoria y plano maestro del proyecto
└── .github/workflows/  CI · Deploy · refresco de datos programado
```

## 🚀 Inicio rápido (desarrollo local)

```powershell
# 1. Base de datos Postgres local
docker compose up -d db

# 2. Variables de entorno
copy .env.example .env    # luego rellena FOOTBALL_API_KEY

# 3. Ingesta de datos + API + UI (fases siguientes del plan)
```

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
