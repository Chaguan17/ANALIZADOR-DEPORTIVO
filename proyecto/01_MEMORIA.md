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
- Insumo de predicciones disponible ya: 1.252 partidos por jugar (SCHEDULED/TIMED)
  de 1.590 descargados en total.
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

---

## Sesión 4 · 2026-10-22 · FASE 3 COMPLETA (Postgres + Alembic + carga idempotente)

**Qué se hizo:**
- Propietario ejecutó Docker manualmente (aprendizaje práctico solicitado):
  `docker compose up -d db` → estado **healthy**; entendió imagen/contenedor/volumen/puerto.
- Backend Fase 3 construido:
  - `backend/requirements.txt` — sqlalchemy==2.1.6 · alembic==1.20.1 · psycopg[binary]==3.3.6
  - `backend/app/config.py` — carga el MISMO `.env` raíz (DATABASE_URL)
  - `backend/app/db.py` — engine + SessionLocal + Base declarativa
  - `backend/app/consola.py` — helper UTF-8 compartido (cp1252 de Windows)
  - `backend/app/models.py` — 8 tablas: equipos, jugadores, partidos, clasificacion,
    stats_partido, stats_jugador, prediccion, reales_vs_previsto
  - `backend/app/load.py` — cargador idempotente (merge por id) + QA anti-duplicados
- Alembic: `alembic.ini` + `env.py` (URL injectada desde app/config) + migración autogenerada
  `20261022_0d3eb9476f9a` + `upgrade head` aplicado a Postgres dockerizado.
- **Carga inicial: 96 equipos · 47 jugadores · 1.590 partidos · 114 filas de clasificación.**
- **Idempotencia probada**: 2ª corrida → 0 nuevos en las 4 tablas.
- Demo de SQL del propietario vía `docker exec` + psql: top 8 LaLiga desde la BD propia.

**Decisiones/problemas de esta sesión:**
- Plantilla script.py.mako le faltaba `${imports}` → el JSONB no importaba `postgresql`
  en la migración generada. Primer `upgrade` falló y SCI-rollback limpio gracias al DDL
  transaccional de Postgres (nada quedó a medias). Aprendido: tipos de dialecto requieren
  import en la migración; la plantilla ya lo soporta.
- Esquema refina el plano original: `clasificacion` añadida como tabla real (standings)
  y nombres al singular conforme al resto; decisión registrada en 00_CONTEXTO.
- Conteos con `func.count().select_from(Model)` (idomático SQLAlchemy 2).

**Siguientes pasos:**
1. **FASE 4 — métricas/featurización** (carpeta backend/models o feature_store):
   forma por ventana de N partidos desde `partidos` FINISHED, H2H, fuerza local/visita,
   patron de jornada; rates por 90' de jugadores. Salida: tabla `stats_partido` mencionada.
2. Después — **FASE 5:** Poisson doble baseline sobre esos features (predicción 1X2
   primera generación) → guardar en `prediccion` con modelo "poisson_doble".
3. Ritual de datos: tras semana nueva de partidos → `python -m pipeline` + `python -m backend.app.load`
   (futuro: solo se añade lo nuevo gracias a caché + upsert).

---

## Sesión 5 · 2026-10-22 · FASE 4 COMPLETA (features de equipos + verificación cruzada)

**Qué se hizo:**
- `backend/app/features.py` — motor de features con regla de oro walk-forward:
  - `HistoriaLiga`: partidos FINISHED de una liga-temporada ordenados por fecha (desde Postgres)
  - `forma()` ventana N=5 (puntos/gf/gc), con filtro como local o como visitante
  - `snapshot_tabla()` clasificación RECOMPUTADA punto-en-tiempo (la tabla de la API es
    del presente y podría filtrar futuro en backtesting — por eso no se sirve de ella)
  - `h2h()` últimos N=6 entre ambos equipos
  - `ultimo_antes()` → descanso en días
  - `features_de_partido()` → dict con las 31 claves del catálogo
- CLI demo: `python -m backend.app.features --liga PD --prox 2` → primer próximo partido
  Alavés vs Málaga (jornada 10) con sus 31 features impresos.
- **Verificación cruzada doble-camino:** misma métrica calculada por SQL puro dentro
  del contenedor (psql ventana LIMIT 5) y por features.py → coincidencia exacta
  (Alavés: pts5=1, gf5=3, gc5=7, j=5). QA de features PASADO.

**Decisiones/problemas de esta sesión:**
- Bug captado en autorrevisión: en snapshot_tabla, los puntos del visitante se
  derivaban con `3 - p_local` (empate daría 2 en vez de 1) → corregido con
  `_puntos_de(r, id_visitante)`.
- Descubrimiento honesto: `h2h_jugados=0` en jornadas 10 porque `HistoriaLiga` solo
  carga la temporada actual (Málaga ascendió; sin choques previos en la temporada)
  → limitación documentada en la sección 10 del CONTEXTO con plan de resolución.
- Catálogo de features oficiales en 00_CONTEXTO.md sección 10 (grupos + claves
  exactas + justificación) — requisito del ritual de la Fase 4.
- Features de JUGADOR deferidos a Fase 6 (dato top-10 agregado, sin minutos);
  decisión marcada en el plano maestro.

**Siguientes pasos:**
1. **FASE 5 — modelo de equipo (baseline Poisson doble):**
   - estimar fuerza de ataque/defensa por equipo a partir de goles históricos
     (features ya calculadas: gf_prom_casa/fuera, gc_prom...),
   - distribuir marcadores (0-0 … 6-6) con Poisson ajustando la ventaja de jugar en casa,
   - salida: prob_local/empate/visita + prob_over25 + marcador más probable
     → primera fila en la tabla `prediccion` (modelo "poisson_doble").
2. Después — Fase 5b LightGBM cómo alternativa; luego Fase 7 evaluation walk-forward.

---

## Sesión 6 · 2026-10-22 · FASE 5 — BASELINE POISSON DOBLE ✓ (1.252 predicciones sanas)

**Qué se hizo:**
- `backend/app/modelo.py` — modelo baseline Poisson doble, 100% walk-forward:
  - `ParametrosLiga.calcular(hasta)`: μ_casa/μ_visita de liga + fuerzas atk/dfn por
    equipo (como local / como visitante), calculadas SOLO con partidos < fecha
  - `predecir()`: λ = μ × atk × dfn → grid Poisson 0..8 × 0..8 → P(1/X/2),
    over/under 2.5 y marcador más probable
  - `predecir_y_guardar()`: persistencia idempotente (delete+insert por
    (partido, modelo) — aprovecha la UNIQUE de la tabla `prediccion`)
- CLI: `python -m backend.app.modelo [--liga X] [--todas] [--prox N] [--guardar]`
- Primeras predicciones vivas: Alavés 61.9% vs Málaga · Barcelona 63.2% vs Real
  Madrid · Villarreal favorito en Mestalla (46.9%) — cifras plausibles.

**Problema detectado y resuelto (lo interesante de esta fase):**
- El Poisson crudo explotaba: λ hasta 11.27 (RB Leipzig), P(local) 99.97% y
  marcadores 0-7 — el producto μ×atk×dfn estalla cuando ambos factores son
  extremos y las muestras crecen poco (Champions con solo 3 fechas jugadas).
- Protecciones aplicadas (decisiones en CONTEXTO §3):
  1. K_SHRINK=8 — contracción de fuerzas hacia 1.0: fuerza = 1 + (cruda-1)·j/(j+K)
  2. MIN/MAX_FUERZA 0.4/2.5 — recorte post-contracción
  3. LAMBDA_MIN/MAX 0.2/4.5 — cúpula de goles esperados por partido
  4. Grid 0..8 trunca las colas de Poisson → renormalización de la masa
     (el guardián interno `assert 1X2≈1` detectó el truncamiento en la 1ª corrida)
- Antes → después en la BD: max λ 11.27 → 3.76 · max P(local) 99.97% → 88.07% ·
  total 1252 filas mantenido (las locas fueron reemplazadas in-situ).

**Verificaciones psql:**
- Por liga: SA 310 · PL 310 · PD 290 · BL1 252 · CL 90 = 1.252 ✓
- Re-corrida completa `--todas --guardar` → mismas 1252 filas (idempotencia ✓)
- Muestra con join equipos/partidos legible y plausible

**Quedan abiertas de la Fase 5:** Dixon-Coles (ajusta empates/marcadores bajos
con ρ) y LightGBM con los 31 features de Fase 4. Variantes vs baseline.

**Siguientes pasos:**
1. Fase 5b: Dixon-Coles → comparar mejora vs baseline (log loss aún sin medir)
2. o Fase 7: evaluación walk-forward del baseline ya registrada (log loss/Brier
   contra los partidos FINISHED recientes) → números de precisión reales
3. Después: Fase 8 (API) ya tiene datos que servir en `prediccion`.

---

## Sesión 7 · 2026-10-22 · FASE 7 COMPLETA (evaluación walk-forward del baseline)

**Qué se hizo:**
- `backend/app/evaluacion.py` — evaluador walk-forward:
  - evalúa TODOS los partidos FINISHED de cada liga con el MISMO `predecir()`
    de la Fase 5 → lo que medimos es exactamente lo que se vende en vivo
  - métricas: log loss, Brier 1X2, accuracy 1X2, accuracy/Brier de over-2.5,
    MAE de goles (|λ − real|), calibración por cubetas de 10%
  - `--peores N`: lista los fallos más caros (donde más log loss se quemó)
  - persistencia idempotente en `reales_vs_previsto` por (partido, modelo):
    323 filas → eliminadas + reinsertadas → 323 pares únicos ✓
- **Verificación cruzada SQL puro vs Python:** accuracy/log loss/Brier por liga
  computados también en psql → coincidencia exacta al 4° decimal en las 5 ligas.

**Bugs reales que la evaluación sacó a la luz (y correcciones):**
1. ZeroDivisionError: el primer partido de la temporada → μ_visita=0
   (único previo con visita en cero). Corregido: piso MU_MINIMO=0.1 en `calcular()`.
2. KeyError: equipo que debuta y no existe en los diccionarios de fuerzas →
   corregido con fallback `get(equipo, 1.0)` (fuerza neutral, ya documentado).
3. Calentamiento: los partidos con <2 evidencias previas se saltan (14 de 337).
   Las 1.252 predicciones vivas NO cambian (todas tienen ≥90 partidos de
   evidencia — muy lejos del piso).

**Resultados honestos (temporada 2026, 323 partidos):**
| Liga | Accuracy | Log loss | Brier | vs siempre-local |
|---|---|---|---|---|
| PD  | 48.3% | 1.0521 | 0.6336 | GANA (42.5%) |
| PL  | 35.3% | 1.1588 | 0.6972 | PIERDE accuracy Y log loss > uniforme 1.0986 |
| SA  | 39.7% | 1.0675 | 0.6448 | PIERDE accuracy (47.1%) |
| BL1 | 50.0% | 1.0524 | 0.6292 | Empata (50.0%) |
| CL  | 55.8% | **0.9630** | 0.5748 | PIERDE accuracy (59.6%) |
| TOTAL | 45.2% | 1.0635 | 0.6392 | -1.2 pts vs siempre-local (46.4%) |

**Lecturas (lo que enseña el número):**
- El modelo SIEMPRE supera al azar uniforme en probabilidad total (log loss/Brier),
  pero en accuracy compite de igual a igual con "siempre local" → el margen
  del baseline es ajustado: la señal está en la forma, no solo en la ventaja local.
- La Premier es el punto débil: log loss PEOR que el azar (1.1588) → sobreconfianza
  en locales (cubeta 50-60: prometía 54%, acertaba 22%). Más evidencia + DC.
- La Champions es donde mejor calibra (log loss 0.9630) — sorprende con 3 fechas.
- Los fallos caros del log loss son casi siempre "favorito local derrotado":
  la sobreconfianza en favoritos fuertes es EL detonante a atacar con Dixon-Coles.
- O2.5 débil en SA/PL (modelo tiende a under en ligas donde el 2026 va a goles).

**Siguientes pasos:**
1. Fase 5b Dixon-Coles con los hallazgos a cuestas: bajar la sobreconfianza en
   favoritos y ajustar empates (el modelo predice 1-1 todo el rato).
2. o Fase 8: API FastAPI para congelar los humildes números del baseline V1 y
   exponerlos al frontend (la historia "Baseline1 → mejoras en la versión 2").




