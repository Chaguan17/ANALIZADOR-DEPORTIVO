# 00 · CONTEXTO DEL PROYECTO — ANALIZADOR DEPORTIVO

> **Documento vivo.** Toda decisión de diseño se registra aquí con fecha. Si un conocimiento
> no está en este archivo (ni en `01_MEMORIA.md`), el proyecto lo ha olvidado.
> Última actualización: 2026-10-22

---

## 1. VISIÓN

Sistema de predicciones de fútbol basado en el rendimiento de **equipos** y **jugadores**,
alimentado por APIs gratuitas, con pipeline de datos automatizado (CI/CD en GitHub Actions)
y despliegue 100% gratuito. Doble propósito:

1. **Funcional:** predecir	partidos (1X2, marcador, over/under) y rendimiento individual
   de jugadores, medir la precisión del modelo contra la realidad y contra cuotas de casas de apuestas.
2. **Formativo / portafolio:** servir de vehículo para practicar Full Stack y DevOps moderno
   (React/Next.js, FastAPI, Docker, Postgres, GitHub Actions, deployment en la nube).

## 2. ALCANCE

| Incluido en el MVP | Diferido (Fase 14+) |
|---|---|
| Predicción 1X2 de partidos | Valor esperado vs cuotas de bookmakers |
| Marcadores más probables y over/under 2.5 | Más ligas adicionales |
| Métricas y rankings de jugadores | Ensambles / redes LSTM |
| Dashboard Next.js con perfiles y precisión | Aplicación móvil |
| Pipeline de datos con cron de Actions | Notificaciones (email/Telegram) |

## 3. DECISIONES DE DISEÑO (registro con fecha)

| Fecha | Decisión | Razón |
|---|---|---|
| 2026-10-22 | Deporte: **fútbol (soccer)** | Preferencia del propietario |
| 2026-10-22 | Datos: **football-data.org** (free, 10 req/min) | Fuente principal gratuita; cubre grandes ligas europeas |
| 2026-10-22 | Predicciones de **partidos + jugadores** | El modelo de equipo realimenta al de jugador |
| 2026-10-22 | Arquitectura **Full Stack**: Next.js + FastAPI + Postgres | Practicar habilidades Full Stack reales (Streamlit descartado) |
| 2026-10-22 | Repositorio **público** en GitHub | Minutos de Actions ilimitados + valor de portafolio |
| 2026-10-22 | Base de datos **Postgres** (no SQLite) | Requisito del despliegue en la nube (Neon) |
| 2026-10-22 | Hosting: **Vercel** (front) + **Render** (backend) + **Neon** (DB) | Free tiers; Docker permite migrar si un free tier cambia |
| 2026-10-22 | Nivel DevOps del propietario: **práctica desde cero** | El plan enseña cada paso de CI/CD; no se asume conocimiento previo |
| 2026-10-22 | Ligas MVP: **LaLiga (PD) · Premier (PL) · Serie A (SA) · Bundesliga (BL1) · Champions (CL) · Europa League (EL)** | Decisión del propietario; se ampliará a futuro. ⚠️ EL puede NO estar incluida en el free tier de football-data.org (tier gratuito cubre PD, PL, SA, BL1, FL1, CL): la Fase 2 lo verificará con la API key y si falla, se documenta y se agrega después vía API-Football |

## 4. STACK TÉCNICO

- **Frontend:** Next.js (App Router) + TypeScript + Tailwind + Recharts
- **Backend:** Python 3.14 + FastAPI + Pydantic + SQLAlchemy + Alembic
- **Datos/modelado:** pandas + LightGBM + modelos Poisson (baseline → Dixon-Coles)
- **Base de datos:** PostgreSQL 16 (local: docker-compose / nube: Neon)
- **Infra:** Docker, docker-compose, GitHub Actions, GHCR
- **Entorno de este equipo (verificado 2026-10-22):** Git 2.55 · Python 3.14.7 · Node 25.6.1 · npm 11.9.0 · Docker 29.7.2 · sin GitHub CLI

## 5. ESTRUCTURA DEL MONOREPO

```
ANALIZADOR DEPORTIVO/
├── frontend/                 Next.js + TS (Fase 9)
├── backend/                  FastAPI: rutas, modelos, alembic/, Dockerfile (Fases 2-3, 8)
├── pipeline/                 Jobs de ingesta de datos (Fase 2); reutiliza código del backend
├── proyecto/                 ← GOBERNANZA: contexto, memoria, plano maestro (determina todo)
├── .github/workflows/        ci.yml (Fase 10) · data-refresh.yml (Fase 12) · deploy (Fase 11)
├── docker-compose.yml        Dev local: postgres (ya) + api + web (futuras fases)
├── .env.example              Plantilla de secretos — los .env reales NUNCA se commitean
└── README.md                 Cara del portafolio
```

## 6. RITUAL DE MEMORIA (regla del proyecto)

1. Toda sesión de trabajo **EMPIEZA** leyendo `00_CONTEXTO.md`, `01_MEMORIA.md` y `02_PLANO_MAESTRO.md`.
2. Toda sesión **TERMINA** añadiendo su entrada a `01_MEMORIA.md` y marcando fase/s en `02_PLANO_MAESTRO.md`.
3. Cada decisión importante se registra en la tabla de la sección 3 de este archivo.
4. Cualquier agente asistente debe hacer este ritual sin excepción.

## 7. GLOSARIO

| Término | Significado |
|---|---|
| 1X2 | Probabilidades de victoria local (1), empate (X) o visita (2) |
| xG | Goles esperados (expected goals): calidad de las oportunidades generadas |
| Feature | Variable calculada de rendimiento que alimenta a los modelos |
| Walk-forward | Validación avanzando en el tiempo, entrenando solo con el pasado |
| Brier score | Métrica de calidad de probabilidades (0 = perfecto, 0.25 = adivinar al azar en 1X2 binario) | 
| Calibración | Que un "70%" ocurra aproximadamente el 70% de las veces |
| Cold start | Primer arranque lento después de que un servicio gratuito duerme |
| Free tier | Nivel gratuito de un servicio de nube, con límites |

## 8. FUENTES DE DATOS

- **Principal:** football-data.org → competiciones/partidos/clasificación/plantillas/goleadores
- **Ligas del MVP (código en football-data.org):** LaLiga `PD` · Premier `PL` · Serie A `SA` ·
  Bundesliga `BL1` · Champions `CL` · Europa League `EL` (⚠️ verificar acceso con la API key del free tier)
- **Respaldo para jugadores (Fase 6):** FBref / Understat (CSV o scraping puntual)
- **Límites:** 10 peticiones/minuto en el tier gratuito → todos los datos se persisten en Postgres;
  nunca se pide a la API lo que ya está guardado.

## 9. PENDIENTE POR DECIDIR

- [x] ~~Liga(s) objetivo del MVP~~ → decidido 2026-10-22: PD, PL, SA, BL1, CL, EL (ver acceso free tier en Fase 2)
- [ ] Nombre final del repo en GitHub (remoto conectado más adelante, decisión del propietario)
- [ ] Licencia (MIT recomendado si es público)
