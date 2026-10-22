# 01 · MEMORIA DEL PROYECTO — Bitácora cronológica

> **Documento vivo.** Cada sesión de trabajo añade su entrada AL FINAL (las más viejas arriba).
> Formato: fecha · qué se hizo · problemas/decisiones · siguientes pasos.
> Última actualización: 2026-10-22

---

## Sesión 1 · 2026-10-22 · Planificación + Fases 0 y 1

**Qué se hizo:**
- Definidos rumbo y alcance con el propietario: fútbol · datos de football-data.org ·
  predicciones de partidos y jugadores · stack Full Stack (Next.js + FastAPI + Postgres) ·
  repo público · despliegue gratuito (Vercel + Render + Neon) · CI/CD con GitHub Actions.
- Plan de estrategia de 15 fases redactado y aprobado.
  Copia de referencia: `C:\Users\XAWUANG\.opencode\plan\analizador-deportivo-estrategia.md`
- **Fase 0 ejecutada:** creada la gobernanza (`00_CONTEXTO.md`, `01_MEMORIA.md`, `02_PLANO_MAESTRO.md`)
  y adoptado el ritual de memoria.
- **Fase 1 ejecutada:** verificado el entorno local (Git 2.55 · Python 3.14.7 · Node 25.6.1 ·
  npm 11.9 · Docker 29.7.2 · sin GitHub CLI); creado el esqueleto del monorepo con
  `README.md`, `.gitignore`, `.env.example`, `docker-compose.yml` (Postgres local),
  carpetas `backend/`, `frontend/`, `pipeline/`, `.github/workflows/` con READMEs guía;
  `git init` rama `main` + primer commit.

**Decisiones/problemas:**
- La identidad de Git ya estaba configurada (Jesús Chaguan) → commit directo.
- Postgres local arranca solo cuando se necesite (`docker compose up -d db`) — no este día.
- Sin GitHub CLI: el repo remoto se crea desde github.com o instalando gh CLI (pendiente con el propietario).

**Siguientes pasos:**
1. Propietario: conectar el repo a GitHub (nombre pendiente) y crear la cuenta/API key
   gratuita de football-data.org (https://www.football-data.org/client/register).
2. Sesión siguiente — **Fase 2 (Ingesta):** cliente de API con límite de 10 req/min,
   endpoints de partidos/clasificación/goleadores, JSON crudo en `pipeline/raw/`.
3. Después — **Fase 3:** esquema de tablas Postgres + migraciones con Alembic.

---

## Sesión 2 · 2026-10-22 · API key verificada + gobernanza actualizada

**Qué se hizo:**
- Propietario registrándose en football-data.org y compartió su API token.
- Creado `.env` local con `FOOTBALL_API_KEY` (protegido por `.gitignore`; el `.env.example`
  sirve como plantilla). El `.env` NUNCA se commitea — verificado al hacer `git status`.
- Petición de prueba contra `https://api.football-data.org/v4/competitions`: **token válido ✅**.
- Ligas del propietario verificadas una a una contra la lista de acceso real:
  - ✅ Confirmadas con acceso: `PD` LaLiga, `PL` Premier, `SA` Serie A, `BL1` Bundesliga, `CL` Champions
  - ❌ `EL` Europa League **no incluida** en el free tier (solo hay 13 competiciones accesibles:
    BSA, ELC, PL, CL, EC, FL1, BL1, SA, DED, PPL, CLI, PD, WC)
- `00_CONTEXTO.md` actualizado: decisión original ajustada → EL fuera del MVP, se integrará
  vía API-Football (100 req/día gratis). Extras disponibles gratis: FL1, BSA, ELC, PPL, DED, CLI, EC, WC.
- Commits: `dfe9a1e` (Fases 0-1) · `c87201d` (decisiones de ligas) · docs de esta sesión.

**Decisiones/problemas:**
- PowerShell 5.1 no soporta `-ResponseHeadersVariable` (fue un error de herramienta, no de la API):
  los primeros dos intentos de prueba fallaron por eso. Aprendido para scripts locales de Windows.
- En el free tier el número de competiciones marcó 13; ligas extra (FL1, BSA...) quedan
  documentadas como posibles ampliaciones de bajo costo (el propietario quiere sumar más ligas a futuro).

**Siguientes pasos:**
1. Propietario: instalar GitHub CLI (o crear el repo en github.com) para conectar el remoto —
   el bloqueo NO impide la Fase 2, pero sí la Fase 10 (CI).
2. Sesión siguiente — **Fase 2 (Ingesta):** cliente `pipeline/` de football-data.org con rate-limit
   (10 req/min), endpoints de partidos/clasificación/plantillas/goleadores para PD, PL, SA, BL1, CL,
   JSON crudo en `pipeline/raw/`.
3. Después — **Fase 3:** esquema Postgres + Alembic.

---

## Sesión 3 · 2026-10-22 · Remoto conectado + FASE 2 COMPLETA (ingesta + QA)

**Qué se hizo:**
- Verificado el repo GitHub creado por el propietario: `github.com/Chaguan17/ANALIZADOR-DEPORTIVO`
  → `git fetch` muestra `origin/main` == `main` local (sin divergencia).
- Verificado NO-EXPOSICIÓN de secretos: `git ls-files` = 12 archivos seguros; el `.env` jamás
  entró al historial.
- **FASE 2 construida y ejecutada:**
  - `requirements.txt` en raíz con `httpx==0.28.1` y `python-dotenv==1.2.4` (venv `.venv/`)
  - `pipeline/config.py` — liga/s/temporada/secrets/pacing en un solo lugar
  - `pipeline/client.py` — cliente HTTP con pacing (mín 6.2 s entre requests), reintentos
    con backoff (solo 429/5xx) y `get_cached` (caché-first: si el JSON crudo existe, 0 cuota)
  - `pipeline/ingest.py` — 5 ligas × 4 fuentes (partidos con `season=2026` fijo,
    clasificación, equipos, goleadores) con manejo de error por fuente y fallback sin `season`
  - `pipeline/__main__.py` — CLI: `python -m pipeline [--refresh] [--quiet]`, exit code CI-ready
  - `pipeline/qa.py` — QA de JSON crudos SIN gastar cuota (exit code CI-ready)
- **Primera ingesta real: 20/20 requests 200-OK en ~2 min.** Segunda ejecución usó 0 cuota (caché).
- **QA final: 0 problemas, 24/24 archivos válidos.**

**Hallazgos de datos reales (temp 2026-27):**
- Ligas domésticas 20/20/20 equipos 380 partidos · BL1 18/306 · CL 36/144 (fase de liga)
- Jornadas jugadas: PD 9 (89 FINISHED + 1 CANCELLED), PL 7, SA 7, BL1 6, CL 3 de fase de liga
- Insumo de predicciones disponible ya: ~1.242 partidos por jugar (SCHEDULED/TIMED)
- QA captó los empates de posiciones de la tabla de Champions (puntos iguales → posiciones
  repetidas 20/20, 29/29, comportamiento real de la API) → regla de tablas ajustada a
  no-decreciente + equipos únicos.

**Decisiones/problemas de esta sesión:**
- Consola Windows cp1252 no imprime ✓/✗ → helper `_consola_utf8()` en ambos CLI.
- Aprendizaje clave para el propietario: `check` QA con exit code es el patrón que
  la CI (Fase 10) reutilizará tal cual.
- El 1 partido CANCELLED de LaLiga se documentó como hecho de datos (aplazamiento),
  no como error del sistema.

**Siguientes pasos:**
1. **FASE 3 — base de datos:** `docker compose up -d db` (Postgres local), esquema SQLAlchemy
   (equipos/jugadores/partidos/stats/predicciones) + primera migración Alembic + cargador
   idempotente JSON crudo → Postgres + chequeos de unicidad/duplicados.
2. Las claves: el cargador debe mapear `status` (FINISHED/SCHEDULED/...) y no duplicar
   partidos ya guardados (upsert por id de la API).
3. Fase 10 según su momento: crear repo Secrets cuando existan workflows.


