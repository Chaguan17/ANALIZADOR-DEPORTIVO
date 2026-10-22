# 02 · PLANO MAESTRO — ANALIZADOR DEPORTIVO

> **Documento vivo de seguimiento.** Marca `- [x]` cada fase/hito completado y añade la fecha.
> Referencia completa del diseño: `proyecto/00_CONTEXTO.md` · bitácora: `proyecto/01_MEMORIA.md`
> Última actualización: 2026-10-22 (Sesión 3)

---

## FASE 0 — GOBERNANZA: CONTEXTO Y MEMORIA
- [x] Carpeta `proyecto/` con los 3 documentos vivos (2026-10-22)
- [x] `00_CONTEXTO.md` — visión, alcance, decisiones con fecha, stack, glosario
- [x] `01_MEMORIA.md` — bitácora cronológica (ritual: empezar leyendo, terminar actualizando)
- [x] `02_PLANO_MAESTRO.md` — este documento con checkboxes

## FASE 1 — ESTRUCTURA MONOREPO + GIT + GITHUB
- [x] Verificar entorno local: Git · Python · Node · Docker (2026-10-22)
- [x] Esqueleto de carpetas: `backend/`, `frontend/`, `pipeline/`, `.github/workflows/`, `proyecto/`
- [x] `README.md` (cara del portafolio) + `.gitignore` + `.env.example`
- [x] `docker-compose.yml` (Postgres local para desarrollo)
- [x] `git init` (rama `main`) + primer commit (2026-10-22)
- [x] Conectar remoto GitHub y push — `github.com/Chaguan17/ANALIZADOR-DEPORTIVO` (2026-10-22)
- [ ] Badges de CI/CD en README (cuando existan los workflows)

## FASE 2 — INGESTA DE DATOS (football-data.org)
- [x] Cuenta + API key de football-data.org — **creada y verificada contra la API real** (2026-10-22); guardada en `.env` local ✅ · *pendiente: GitHub Secrets cuando exista el repo remoto → repo creado 2026-10-22; secrets se añaden al crear workflows (Fase 10-12)*
- [x] Cliente de API con rate-limit (10 req/min), reintentos y JSON crudo en `pipeline/raw/` (2026-10-22: `pipeline/client.py` con pacing + backoff + caché-first)
- [x] Endpoints: partidos (season fija 2026), clasificación, equipos, goleadores (2026-10-22: 5 ligas × 4 fuentes = 20 requests OK; **goleadores limitados a top-10 por el free tier**; PD tiene 1 partido CANCELLED a headlights)
- [x] Ligas objetivo: **PD ✅ · PL ✅ · SA ✅ · BL1 ✅ · CL ✅** (2026-10-22) · EL ❌ fuera del free tier → deferida a API-Football
- [x] QA de datos crudos sin gasto de cuota (2026-10-22: `pipeline/qa.py`, 24 archivos válidos, 0 problemas)

## FASE 3 — BASE DE DATOS POSTGRES
- [ ] Esquema: `equipos`, `jugadores`, `partidos`, `stats_partido`, `stats_jugador`, `predicciones`, `reales_vs_previsto`
- [ ] Migraciones con Alembic (primera migración inicial)
- [ ] Cargas idempotentes (upsert) + chequeos de calidad (duplicados/nulos/fechas)

## FASE 4 — MÉTRICAS DE RENDIMIENTO (features)
- [ ] Features de equipo: forma, goles fav/contra, local/visita, H2H, tabla, descanso
- [ ] Features de jugador: minutos, goles/90, asistencias/90, tiros, forma
- [ ] Cada feature documentado en `00_CONTEXTO.md`

## FASE 5 — MODELO DE EQUIPO
- [ ] Baseline: Poisson doble (marcadores esperados local/visita)
- [ ] Dixon-Coles (ajuste de empates)
- [ ] LightGBM con features de Fase 4 (1X2)
- [ ] Salidas: P(1/X/2) · marcadores · over/under 2.5

## FASE 6 — MODELO DE JUGADOR *(tras MVP, en paralelo)*
- [ ] Goles esperados/90 ajustados por posición, rival y minutos esperados + contracción
- [ ] Prob. de marcar · props over/under · respaldo FBref/Understat si faltan datos

## FASE 7 — EVALUACIÓN Y VALIDACIÓN
- [ ] Backtesting walk-forward (nunca entrenar con el futuro)
- [ ] Métricas: log loss, Brier, calibración, accuracy 1X2, benchmark vs cuotas
- [ ] Registro de cada evaluación en `01_MEMORIA.md`

## FASE 8 — API REST FASTAPI
- [ ] Endpoints: `/health` `/fixtures` `/predictions/{id}` `/teams/{id}` `/players/{id}` `/rankings` `/model-accuracy`
- [ ] Pydantic + Swagger (`/docs`) + Dockerfile del backend
- [ ] `docker-compose` con `db` + `api` + `web` funcionando en local

## FASE 9 — FRONTEND NEXT.JS
- [ ] Scaffold con TypeScript + Tailwind + App Router
- [ ] Páginas: Próximos partidos · Detalle de partido · Perfil equipo · Perfil jugador · Ranking · Precisión
- [ ] Integración con la API (`NEXT_PUBLIC_API_URL`)

## FASE 10 — CI CONTINUO (.github/workflows/ci.yml)
- [ ] Job backend: ruff → pytest → docker build
- [ ] Job frontend: npm lint → npm build
- [ ] Badges de estado en README (+ CodeQL y Dependabot opcionales)

## FASE 11 — DEPLOY CONTINUO
- [ ] Neon: proyecto creado → `DATABASE_URL` en GitHub Secrets y Render
- [ ] Render: auto-deploy backend `on push` + migraciones Alembic al arrancar
- [ ] Vercel: importar repo → preview por PR + producción en main
- [ ] Verificado: commit a main → despliegue automático de front y back

## FASE 12 — PIPELINE DE DATOS PROGRAMADO (data-refresh.yml)
- [ ] Workflow cron (cada ~6 h): API → transformar → Postgres (Neon) → features → predicciones
- [ ] Logs auditables en la pestaña Actions · timeout · protección anti-solapamiento

## FASE 13 — MOTOR DE PREDICCIONES
- [ ] Pipeline: fixture futuro → features → modelos → tabla `predicciones` con fecha
- [ ] Medición de aciertos al confirmarse resultados (ranking vivo del modelo)

## FASE 14 — CIERRE Y PORTAFOLIO (opcional/elevar)
- [ ] README final: badges, diagrama de arquitectura, link al dashboard vivo
- [ ] Playwright e2e (opcional) · Dependabot · dependencias al día
- [ ] Ideas futuras: valor esperado vs cuotas, más ligas, LSTM

---

## MVP DESPLEGABLE
Fases 0-5 + 8 + 10 + 11 → sistema corriendo en la nube con CI/CD y predicciones 1X2 funcionales.
