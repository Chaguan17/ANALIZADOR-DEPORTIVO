# 01 · MEMORIA DEL PROYECTO — Bitácora cronológica

> **Documento vivo.** Cada sesión de trabajo añade su entrada AL FINAL (las más viejas arriba).
> Formato: fecha · qué se hizo · problemas/decisiones · siguientes pasos.
> Última actualización: 2026-10-23

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

---

## Sesión 8 · 2026-10-22 · FASE 5b COMPLETA (Dixon-Coles) + FASE 8 COMPLETA (API FastAPI)

**Qué se hizo (Fase 5b — Dixon-Coles):**
- Refactor DRY de `modelo.py`: el grid de marcadores vive ahora en el helper
  compartido `probabilidades_1x2(pmf_local, pmf_visita, peso=None)` — el baseline
  usa peso=None y DC inyecta el peso τ. La demo baseline repitió los
  λ/1X2 EXACTOS pre-refactor → la matemática no se tocó (solo reorganizada).
- `predecir_y_guardar()` parametrizado (`predecir_fn`, `modelo`) + `rho` en el
  JSONB de `prediccion`; `evaluacion.py` parametrizado igual (predictor + nombre
  de modelo + ρ en `reales_vs_previsto`).
- `backend/app/modelo_dc.py` — τ de Dixon-Coles sobre las 4 celdas bajas
  (0-0: 1−λμρ · 0-1: 1+λρ · 1-0: 1+μρ · 1-1: 1−ρ · resto: 1, clamp ≥0),
  ρ por liga (grid-search −0.300…0.050 paso 0.0125, minimiza log loss),
  re-computación de filas DC desde las filas baseline (MISMAS λ),
  CLI `--liga/--todas/--peores/--guardar/--vivas`.
- **Bugs de camino:** KeyError en `ajustar_rho` (indexaba el grid con el
  resultado en vez de leer la prob del resultado) → corregido.
- **HALLAZGO QUIRÚRGICO CON CONFIRMACIÓN ALGEBRAICA:** P(1|λ)·P(1|μ) = λμ·w00,
  P(0,1) = μ·w00, P(1,0) = λ·w00 ⇒ Δmasa = ρ(−λμw00 + λμw00 + λμw00 − λμw00) = 0
  EXACTO. Las 4 celdas τ viven dentro del bloque under-2.5 y conservan su masa →
  **τ reordena la 1X2 pero NO mueve over/under 2.5** (comprobado al 15º decimal).
  La mejora del O2.5 tendrá que venir por otro camino (más features/LightGBM).

**Resultados honestos (temporada 2026, 323 partidos, mismas λ):**
| Liga | ρ elegida | log loss base→DC | Brier base→DC | accuracy base→DC |
|---|---|---|---|---|
| PD  | −0.2125 | 1.0521→1.0457 ✅ | 0.6336→0.6299 ✅ | 48.3%→48.3% ➖ |
| PL  | −0.0875 | 1.1588→1.1574 ✅ | 0.6972→0.6939 ✅ | 35.3%→35.3% ➖ |
| SA  | +0.0500 | 1.0675→1.0616 ✅ | 0.6448→0.6417 ✅ | 39.7%→36.8% ❌ |
| BL1 | +0.0500 | 1.0524→1.0516 ✅ | 0.6292→0.6298 ❌ | 50.0%→50.0% ➖ |
| CL  | +0.0500 | 0.9630→0.9587 ✅ | 0.5748→0.5729 ✅ | 55.8%→55.8% ➖ |
| TOTAL | — | 1.0635→1.0594 ✅ | 0.6392→0.6367 ✅ | 45.2%→44.6% ❌ |

**Lecturas honestas:**
- DC mejora el LOG LOSS en 5/5 ligas y el Brier en el total — la métrica
  probabilística (la correcta) mejora consistentemente aunque el margen es
  pequeño (−0.004). Accuracy fluctúa ±0.6% (métrica grosera ante cambios
  probabilísticos finos; en SA re-ordena 2 favoritos).
- ρ por liga cuenta historia: PD/PL negativa (les faltaban empates bajos al
  modelo), SA/BL1/CL pegadas al borde +0.05 (sobra confianza en marcadores
  bajos). Con 48-87 partidos por liga, el ruido in-sample manda — la señal
  fuerte llegará con historia multi-temporada.
- Las predicciones vivas DC la muestran a simple vista: Alavés-Málaga pasó de
  61.9%/21.5%/16.6% a 59.7%/25.9%/14.4% (menos seguro del favorito, más empate).
- Honesto total: Dixon-Coles es un PULIDO marginal, no un salto. Su papel real
  en el proyecto: técnica canónica implementada bien + comparación replicable
  contra la que medir LightGBM.

**Verificaciones:**
- SQL puro: 1252 + 1252 en `prediccion` (por modelo), 323 + 323 evaluaciones,
  log loss/Brier/accuracy idénticos a lo impreso, ρ por liga guardada en JSONB.
- Idempotencia: re-corrida PD → 87 evaluations (no 174), 646 total, 1252 vivas.

**Estado BD tras Fase 5b:** 1.590 partidos · 2.504 predicciones (2 modelos × 1252)
· 646 evaluaciones (2 modelos × 323) · fixture de ρ: PD −0.2125, PL −0.0875,
SA/BL1/CL +0.05.

**FASE 8 COMPLETA — API FastAPI (misma sesión):**
- `backend/app/api.py`: 7 endpoints con contratos Pydantic y sesión de BD por
  petición (`Depends(get_session)`):
  `/health` (latido + conteos: 1.590 partidos · 2.504 predicciones · 646
  evaluaciones) · `/fixtures?liga&limite` (próximos con TODOS los modelos por
  partido — 2 queries sin N+1) · `/predictions/{id}` (JSONB completo, incluye
  ρ en DC) · `/teams/{id}` (ficha + clasificación + últimos 5 + próximos 3) ·
  `/players/{id}` · `/rankings?liga` (standings) · `/model-accuracy`
  (métricas REALES por modelo y liga, agregadas en SQL).
- CORS `["*"]` para consumir desde Vercel (se estrecha en producción).
- Errores honestos: 400 si la liga no es PD/PL/SA/BL1/CL · 404 si el id no existe.
- Docker: `backend/Dockerfile` (python:3.14-slim → requirements → app/ →
  `uvicorn app.api:app`) + servicio `api` en docker-compose
  (`depends_on: db healthy`, `DATABASE_URL` apuntando al host `db`).
  El build/arranque lo ejecuta el PROPIETARIO manualmente
  (`docker compose up -d db api`) — regla del proyecto (no automatizo sus contenedores).
- Prueba de humo con python urllib (más robusto que PowerShell 5.1): 7
  endpoints HTTP 200, /docs 200, y los comportamientos de error 400/404 verificados.
- requirements del backend + fastapi 0.161.0 · pydantic 2.14.1 · uvicorn 0.54.0.
- README del backend reescrito (estructura completa, comandos, tabla de endpoints).
- Correcciones de camino: en /fixtures se instanciaba el `Fixture` sin el campo
  obligatorio `predicciones` (Pydantic v2 valida al CREAR — la lista se arma
  antes) y un SyntaxWarning de backslashes de Windows en el docstring.

**Estado final tras la sesión doble (Fase 5b + 8):**
- Commits: `03af197` (Fase 5b) + el de Fase 8.
- BD: 1.590 partidos · 2.504 predicciones (baseline + DC × 1.252) ·
  646 evaluaciones (baseline + DC × 323).
- Plano: Fases 5b y 8 marcadas [x]; pendientes: LightGBM (5c), frontend (9),
  CI (10), deploy (11), cron (12), motor (13) y el grueso de 14-15.

**Siguientes pasos:**
1. Fase 9: frontend Next.js consumiendo la API ya viva (fixtures/predicciones
   ya devuelven AMBOS modelos).
2. o Fase 10 CI primero (ruff/pytest/build) para blindar antes de crecer.

## Sesión 9 · 2026-10-22 · FASE 5c COMPLETA (LightGBM con features de Fase 4)

**Qué se hizo:**
- lightgbm 4.7.0 instalado y fijado en `backend/requirements.txt` (llegó con
  numpy 2.5.4 y scipy 1.18.1; se usa la API RAW — `lgb.train`/`booster.predict`
  — para NO depender de scikit-learn; el output multiclase siempre es (n, 3)
  con columnas 0=local, 1=empate, 2=visita).
- `backend/app/modelo_lgbm.py`: el árbol aprende de las 31 features walk-forward
  de la Fase 4 (`features_de_partido` — forma ventana-5, casa/fuera, descanso,
  tabla snapshot, H2H), sin ninguna estructura de fútbol a mano (no hay μ, ni
  atk/dfn, ni τ). LightGBM trata los None del arranque frío como missing nativo.
  Parámetros diminutos para datos diminutos: 60 árboles · lr 0.08 · num_leaves 7
  · max_depth 3 · min_data_in_leaf 6 · feature_fraction 0.8 · seed 42.
- Protocolo walk-forward IDÉNTICO a Fases 7/5b (cada fila entrenante lleva sus
  features computadas a la fecha de CADA uno) + calentamiento reforzado:
  MIN_EVIDENCIA=2 **y** las 3 clases presentes en el pool entrenante (si nunca
  hubo empate, la salida 3-clases no está definida) → saltados 46 vs 14 del
  baseline, contados y presentados tal cual.
- **HALLAZGO CENTRAL (la corrida cruda didáctica):** LightGBM puro fue
  SOBRECONFIADO CATASTRÓFICO en datos pequeños. PD: accuracy 32.5% (¡peor que
  el azar!), log loss 1.6013 (peor que la uniforme 1.0986), Brier 0.8655, con
  fallos caros tipo "local 99%" (Celta 0-2 Athletic, log loss 6.09). Con 54-89
  filas por liga, los árboles memorizan hojas puras en vez de generalizar —
  la regularización ESTRUCTURAL del Poisson (K_SHRINK) es lo que el árbol no
  puede darse a sí mismo.
- **La cura v1: mezcla con la uniforme** `p = w·p_árbol + (1−w)/3`, w por liga
  grid-search 0.00…1.00 paso 0.05 minimizando el log loss walk-forward — el
  análogo EXACTO del K_SHRINK, mismo matiz in-sample de 1 parámetro que la ρ
  de DC (documentado). El w elegido MIDE honestamente cuánta señal tiene el
  árbol en cada liga.
- Formato HONESTO: LightGBM v1 emite SOLO P(1X2) → goles_esperados,
  prob_over25/under25 y marcador quedan NULL en las 1.252 vivas (comprobado en
  BD: 1252/1252 nulos). Fabricar un Poisson encima del árbol sería doble
  modelo disfrazado.
- `mezcla_uniforme` añadida al JSONB de `prediccion` (en
  `modelo.py::predecir_y_guardar`) y de `reales_vs_previsto` (en
  `evaluacion.py::_persistir`); `partidos_evidencia` = nº de FINISHED con que
  se entrenó el árbol. `_agregar` de `evaluacion.py` hecha None-tolerante (los
  agregados promedian solo lo que el modelo emite).

**Resultados honestos (temporada 2026, walk-forward):**
| Liga | w elegido | log loss base → LGBM | Brier base → LGBM | accuracy base → LGBM |
|---|---|---|---|---|
| PD  | 0.10 | 1.0521→1.0968 ❌ | 0.6336→0.6656 ❌ | 48.3%→32.5% ❌ |
| PL  | 0.15 | 1.1588→1.0870 ✅ | 0.6972→0.6585 ✅ | 35.3%→41.0% ✅ |
| SA  | 0.35 | 1.0675→1.0596 ✅ | 0.6448→0.6424 ✅ | 39.7%→43.3% ✅ |
| BL1 | 0.00 | 1.0524→1.0986 ❌ (=uniforme pura) | 0.6292→0.6667 ❌ | 50.0%→45.2% ❌ |
| CL  | 0.40 | 0.9630→1.0449 ❌ | 0.5748→0.6296 ❌ | 55.8%→46.3% ❌ |
| TOTAL | — | 1.0635→1.0791 ❌ (n 323 vs 291) | 0.6392→0.6539 ❌ | 45.2%→40.5% ❌ |

**Lecturas honestas:**
- Con 1 temporada, el baseline estructural GANA el torneo: total 1.0635 vs
  1.0791. Pero el cuadro NO es vergüenza, es diagnóstico: el árbol gana en
  Premier y Serie A — justamente las 2 ligas donde el Poisson era MÁS DÉBIL
  (PL tenía el peor log loss del baseline, 1.1588) — y declara su propia
  nulidad en BL1 (w=0.00 → probabilidades 33.3/33.3/33.3 honestas).
- La jerarquía de w (0.40 CL, 0.35 SA, 0.15 PL, 0.10 PD, 0.00 BL1) es la
  señal de cuánta regularización necesita cada liga.
- La señal fuerte llegaría con historia multi-temporada (más filas, menos
  memorización) — límite de free tier ya documentado, no ya hoy.
- La mezcla contiene el daño: peor fallo de PD bajó de log loss 6.09 (crudo)
  a 1.20 (mezclado) — el techo del sobreconfiado desapareció.

**Verificaciones:**
- SQL puro: `prediccion` 1252×3 modelos (3756 filas) · `reales_vs_previsto`
  323+323+291 · tabla por modelo: poisson_dc 1.0594 < poisson_doble 1.0635 <
  lightgbm_v1 1.0791 (campeón siempre el estructural, con sets de n distintos).
- NULLs honestos: goles_esperados/prob_over25/marcador = 1252/1252 nulos en
  lightgbm_v1; w y partidos_evidencia presentes en el JSONB (PD: evid 89, w 0.1).
- Idempotencia: re-corrida PD (`--vivas`) → lightgbm_v1 sigue 1252 (upsert, sin
  duplicados); total evaluaciones sigue 937 filas totales.
- Baseline intacto: `evaluar_liga` recomputada por modelo_lgbm.main dio EXACTOS
  los números de Fase 7 (PD 48.3%/1.0521/0.6336 · total 1.0635/0.6392).
- Fallos de camino corregidos durante la sesión: línea fantasma en el primer
  borrador; f-string con ``f "..."`` (espacio inválido); `_agregar` sin
  tolerancia a None (crasheaba con acierto_o25 None); subtotal de TOTAL
  imprimiendo los saltados del LGBM en el baseline.

**Estado BD tras Fase 5c:** 1.590 partidos · 3.756 predicciones (3 modelos ×
1252) · 937 evaluaciones (323+323+291) · fixture de w: PD 0.10, PL 0.15,
SA 0.35, BL1 0.00, CL 0.40.

**Siguientes pasos:**
1. Fase 9: frontend Next.js — la API ya sirve el 3er modelo por la clasificación
   UNIQUE (partido, modelo); probar /fixtures devolverá los 3.
2. o Fase 10: CI (ruff/pytest/build) para blindar antes de crecer.

## Sesión 10 · 2026-10-22 · FASE 9 COMPLETA (Frontend Next.js)

**Qué se hizo:**
- Scaffold `web/` con create-next-app: Next **16.4.2** + React 19.3 + Tailwind
  v4 + ESLint 9. La plantilla de 2026 activa por defecto `cacheComponents` y
  `partialPrefetching` y genera tipos de rutas (`PageProps<'/ruta'>` global,
  params/searchParams como Promise awaits) → leímos los docs internos
  (`node_modules/next/dist/docs/`) antes de escribir código.
- Arquitectura: páginas 100% server-side; cada una envuelve su contenido en
  `<Suspense>` → Next genera el shell estático en build y **sirve los datos
  por streaming en cada petición** con `fetch` `no-store`. La web NUNCA toca
  la BD: contratos TS espejo 1:1 de los esquemas Pydantic en `web/lib/api.ts`.
- Dos URL de API para no mentir a nadie: `NEXT_PUBLIC_API_URL` (navegador) y
  `API_URL_SERVIDOR` (SSR; en docker `http://api:8000`); default local
  `http://127.0.0.1:8000` en `.env.example` (y copia a `.env.local`, que no se
  commitea).
- Contrato visual propio (no plantilla): **pizarra táctica** verde profundo
  para marca/nav/pie sobre **papel frío** de estadístico; Archivo variable con
  eje wdth (la marca se expande a cartel deportivo) + Spline Sans Mono para
  TODOS los números de datos (tabular-nums); el color de las **barras codifica
  el resultado** (1 azul / X gris / 2 rojo) y las **voces por modelo** llevan
  su identidad en puntos y acentos (Poisson azul, Dixon-Coles oro, LightGBM
  violeta) — misma leyenda en toda la web.
- Las 6 páginas + 404: `/` (fixtures con selector de liga con nombre completo
  y selector de voz; barra 1X2 por fila; favorito%), `/partido/[id]` (las 3
  voces lado a lado: λ local/visita, Over 2.5, marcador estimado, más las
  líneas de diagnóstico sacadas del JSONB: ρ de DC con su semántica, w de
  LightGBM con su lectura honesta, partidos de evidencia; los "—" del LGBM se
  explican en la página), `/equipo/[id]` (tablero pos/puntos/portería en la
  pizarra, forma G/E/P, últimos 5 con veredicto, próximos 3 enlazados),
  `/ranking/[liga]` (tabla completa con forma en chips de colores),
  `/precision` (tabla log loss por modelo×liga con campeón por liga marcado
  con su voz + total ponderado por n; segunda tabla de acierto; nota honesta
  sobre los n distintos de LGBM y la referencia uniforme 1.0986),
  `/jugador/[id]` (ficha mínima + aviso "en pañales" → Fase 6).
- Estados vacíos y errores NARRADOS: si la API está apagada, la página lo dice
  y enseña el comando para levantarla; ligas inválidas y ids inexistentes
  tienen sus avisos dedicados, con enlaces de escape.
- Docker del `web` deferido a Fase 11 (producción = Vercel): comentario del
  compose actualizado — desviación menor documentada.
- `web/README.md` con páginas, comandos y variables de entorno.

**Bugs de camino corregidos:**
- `searchParams` en Next tipo `string | string[] | undefined` → predicados de
  tipo (`esLigaValida`/`esModeloValido` ahora son type guards).
- `ResultadoReciente` del backend NO trae ids de equipos (solo nombres) → la
  ficha determina casa/fuera comparando el nombre, no el id.
- Copy en español pulido (verbos de usuario, sin florituras).

**Verificación de punta a punta:**
- `npm run build` limpio: 8 rutas, shell estático + contenido dynamic (◐).
- Humo con urllib contra el dev server (Next en :3000, mi uvicorn en :8000):
  14 casos — 13×200 con muestras de contenido correcto (home PD default,
  home CL/PL/BL1 con 3 voces distintas, detalle real con "Las tres voces",
  ficha equipo con Balance/Posición/Puntos, jugador, ranking PD, ranking
  inválido con aviso y enlaces, precision con los 3 modelos, 404 propia) +
  `/esta/ruta/rrara` → HTTP 404 COMO SE DEBERÍA (mi script pedía 200: el 404
  con página bonita es el resultado CORRECTO).
- Trazo del log de la API verificó cada llamada HTTP detrás (fixtures×4,
  predictions 200+404, teams 200+404, players 200+404, rankings,
  model-accuracy).
- Higiene de procesos: matados mi uvicorn temporal (PID 2212) y mi node dev
  (PID 8324); el listener de docker-proxy en 8000 es el contenedor `api` del
  PROPIETARIO corriendo desde la Fase 8 — no se tocó (regla del proyecto).

**Estado tras Fase 9:** capas completas — datos (API ingestas) → BD
Postgres → features → 3 modelos que compiten → API FastAPI → **web que los
enseña**. Pendientes: CI (Fase 10), deploy (11), cron (12), motor (13).

**Siguientes pasos:**
1. Fase 10: CI con GitHub Actions (ruff → pytest → docker build; npm lint →
   build) — blindar ANTES de seguir creciendo.
2. Fase 11: deploy (Neon + Render + Vercel) con las variables ya diseñadas.

## Sesión 11 · 2026-10-22 · FASE 10 COMPLETA (CI continuo)

**Qué se hizo:**
- **33 pruebas pytest puras** (sin BD; 2.1 s en correr) en `backend/tests/`:
  - `test_modelo.py` — la PMF de Poisson es distribución (~1 dentro del grid,
    rabo >8 documentado), contracción bayesiana (`_encoger`: j=0 → 1.0,
    j→∞ → casi la cruda, clamps MIN/MAX_FUERZA), cúpula de λ, el 1X2
    renormalizado SIEMPRE suma 1 con over/under complementarios, simetría
    con λ iguales, marcador estimado = argmax (λ 2.3/1.2 → "2-1") y la puerta
    de DC con peso τ≡1 deja TODO igual.
  - `test_modelo_dc.py` — τ solo toca las 4 celdas bajas y clampa a 0 cuando
    λ·μ·ρ ≥ 1; RHO_GRID = 29 pasos de 0.0125; **LA JOYA: la invarianza over/
    under 2.5 EXACTA (1e-12) para λ moderadas con ρ en todo el grid** — el
    bono de marcadores bajos NO contamina el mercado de goles; y el rincón
    del clamp (λ=4.5 con ρ=+0.05) documentado como comportamiento esperado.
  - `test_evaluacion.py` — `_resultado_de` (local/empate/visita), `_agregar`
    tolerante a None (promedia solo lo que existe; lista vacía → None, jamás
    inventar 0) y MIN_EVIDENCIA=2 como guardián del calentamiento.
  - `test_features.py` — `HistoriaLiga` fabricada vía `__new__` + `Registro`
    (el constructor real pega a la BD; los métodos de consulta son puros):
    ventana y corte temporal (fecha == hasta NO cuenta), snapshot_tabla con
    desempate por diferencia de goles (B 2 pts dg−1 por ENCIMA de C 2 pts
    dg−3), h2h en ambos roles, y los 31 features exactos para un caso
    conocido (ppg casa 2.0, descanso 7 días, tabla 1.ª/2.ª) + equipo sin
    historial → None/0 honestos.
  - `test_lgbm.py` — etiqueta 0/1/2, mezcla honesta (w=0 → uniforme pura,
    w=1 → árbol puro, suma 1 en TODO W_GRID), 21 valores paso 0.05, y
    None → NaN (LightGBM los entiende; jamás ceros mentirosos).
- **`pyproject.toml`** en la raíz: `[tool.pytest.ini_options]` con
  `pythonpath=["."]+testpaths` → `pytest -q` desde la raíz va al paquete real;
  `[tool.ruff]` line-length 100 con **select EXPLÍCITO**
  E4/E7/E9/F/I/RUF100.
- **ruff limpio sobre backend + pipeline**: 23 hallazgos → 11 auto-fixes
  mecánicos (orden de imports, `# noqa` muertos, 1 import sin usar) +
  1 variable muerta eliminada a mano en `pipeline/client.py` ("remaining");
  la postura deliberada de NO incluir reglas cosméticas (UP/B/FURB/RUF007)
  mantuvo fuera el B008 que sonaba — era el patrón INTENCIONAL de capturar
  variables del loop en defaults del `def` (anti late-binding) en
  `modelo_lgbm._predecir_con_lgbm` — ni se tocó.
- **requirements.txt**: `ruff==0.17.2` y `pytest==9.1.1` pinneados bajo
  comentario "solo CI" → lo que instala el workflow es EXACTAMENTE lo que
  corrió local.
- **web verde también**: eslint marcó como ERROR `react/no-unescaped-entities`
  (comillas dobles en texto JSX del detalle → cambiadas a «—») y 1 import
  muerto en `precision`; `npm run lint` y `npm run build` OK.
- **Dos workflows separados** (un badge cada uno): `ci-backend.yml`
  (checkout → setup-python 3.14 → pip -r → ruff check backend pipeline →
  pytest -q → docker build ./backend) y `ci-web.yml` (checkout → setup-node
  22 + cache npm por `web/package-lock.json` → `npm ci` → lint → build con
  `working-directory: web`). Repositorio público → Actions gratis.
- README: badges reales de los 2 workflows (+ nota: badge Data Refresh con
  la Fase 12) y estructura corregida `frontend/` → `web/`.
- Des-riskeo del paso Docker: `docker build -t analizador-api:ci ./backend`
  verde localmente ANTES del push (pip de linux 3.14-slim instaló todo,
  incluidos los pins nuevos).

**Lecciones de sesión:**
- Las pruebas sin BD eran posibles porque TODOS los imports del backend son
  perezosos: `db.py` construye el engine sin conectar y `config.py` tiene
  fallback local → CI sin servicio postgres, sin secretos, verde en ~2 min.
- Curiosidad al escribir pruebas con expectativa conocida: el marcador
  argmax con λ=2.0 exacto EMPATA (P(1)=P(2)) → se eligieron λe que ganen
  estricto; y el helper `dt(dia)` de fechas mordió (se le añadió `mes=8`
  porque `dt(5, 9)` era agosto, no septiembre).
- `pythonpath=["."]` de pytest≥7 es la forma limpia de importar `backend.app.*`
  sin instalar el paquete ni tocar conftests.

**Estado tras Fase 10:** el repo queda blindado — todo push a main (y cada
PR) corre ruff + 33 pruebas + docker build + lint/build web automaticamente;
2 badges en el README cuentan la historia. Pendientes: deploy (11), cron de
refresco (12), motor de jugadores (13), extras (14), cierre (15).

**Siguientes pasos:**
1. Confirmar los 2 workflows EN GitHub (poll vía API pública hasta verde).
2. Fase 11: deploy a la nube (Neon + Render + Vercel) cuando el dueño dé
   luz verde — las variables de entorno ya están diseñadas.

## Sesión 12 · 2026-10-22 · FASE 11 COMPLETA (deploy continuo: Neon + Render + Vercel)

**Qué se hizo:**
- **Preparativos del repo antes de que el dueño tocara un dashboard:**
  - `render.yaml` blueprint raíz: runtime docker (`./backend/Dockerfile`,
    contexto `./backend`), plan free, region frankfurt, health check
    `/health`, autoDeploy commit, y `DATABASE_URL` como `sync: false`
    (secreto pedido en el dashboard al crear el Blueprint).
  - `backend/Dockerfile` rediseñado: el contenedor espeja el repo
    (`WORKDIR /srv/backend`; COPY `app` + `alembic` + `alembic.ini`) y el
    CMD arranca con `alembic upgrade head && exec uvicorn … --port
    ${PORT:-8000}` — migraciones al arrancar (imposible un pre-deploy
    separado: el free tier no da jobs one-off ni SSH) y puerto tal cual
    lo inyecta el runtime (Render usa $PORT=10000; local mantiene 8000).
  - Humo local completo ANTES de pushear: `docker build -t
    analizador-api:fase11` verde en 2 modos (8000 y PORT=10000) contra la
    BD real vía `host.docker.internal` → `/health` 200 con
    1.590/3.756/937.
  - Nota clave descubierta en la documentación oficial: Render detecta el
    puerto "usualmente" (no garantizado) si no es $PORT → se eliminó la
    apuesta vinculando uvicorn a `${PORT:-8000}` desde el inicio.

**Cuatro bloques con el dueño en los dashboards (clic a clic guiado por el agente):**
- **Neon**: proyecto `analizador` en eu-central-1 (Frankfurt) con endpoint
  DIRECTO (sin -pooler) → DSN con `sslmode=require&channel_binding=require`.
- **Migración de datos** con las herramientas que ya viven dentro de
  `analizador_db` (psql/pg_dump del postgres:16-alpine, nada instalado en
  Windows): `pg_dump -Fc` → `pg_restore --clean --if-exists --no-owner
  --no-privileges` contra Neon + COUNT de validación exacto
  (1.590/3.756/937) + chequeo `alembic_version` = head de migraciones
  (0d3eb9476f9a, única revisión en la cadena) para que el primer arranque
  en Render sea no-op.
- **Render**: Sign up con GitHub → New → Blueprint → el yaml pre-cargó
  todo (el dueño SOLO pegó el DSN transformado a
  `postgresql+psycopg://…`). Render sufijó el nombre → URL REAL
  **https://analizador-api-iule.onrender.com**. Verificación remota
  200/200: `/health` (conteos exactos), `/fixtures?liga=PD` (3 modelos),
  `/docs`, `/openapi.json`.
- **Vercel**: repo importado → Root Directory `web` → 2 env vars con la
  URL real de Render (`NEXT_PUBLIC_API_URL` + `API_URL_SERVIDOR`) →
  **https://analizador-deportivo-rouge.vercel.app**. Verificado en
  remoto: home SSR con fixtures de PD y los 3 modelos mencionados;
  `/precision` con walk-forward y log losses reales (1.0449–1.0986);
  rutas `/ranking/PD` y tabs `?liga=&modelo=`; el único match de
  "Error" era la palabra `fallback` (JS interno).

**CORS — deuda de la Fase 8 saldada** (commit `258a622`):
- `CORS_ORIGINS` env (lista separada por comas) en `config.py`; default
  seguro de desarrollo `http://localhost:3000`; producción alimenta
  `https://analizador-deportivo-rouge.vercel.app` vía render.yaml (el
  dominio pinneado vive en el repo, no en el código).
- Middleware: `allow_methods=["GET","HEAD"]` (API pública de lectura),
  `allow_credentials=False`; el SSR de la web NO pasa por CORS (sale del
  servidor de Vercel).

**Lecciones de sesión:**
- El DSN que entrega Neon (con `channel_binding=require`) entra NATIVO en
  psycopg3: la única transformación fue `postgresql://` →
  `postgresql+psycopg://` (el `postgresql://` sin driver busca psycopg2,
  que no está).
- `pg_dump`/`pg_restore` a través de `docker exec` evita instalar el
  cliente de postgres en Windows y hace `--clean` idempotente.
- El sufijo de nombre de Render NO es predecible → copiar la URL del
  dashboard y propagarla manualmente a Vercel (regla práctica).
- Local Windows PowerShell 5.1 (cp1252): los mensajes pip/uvicorn dentro de
  `docker logs` llegan con mojibake en consola cp1252 — inofensivo (los
  archivos y la CI están bien); para humo HTTP usar python (urllib) o el
  Code Mode en lugar de Invoke-WebRequest.

**Estado tras Fase 11:** deploy continuo REAL de extremo a extremo —
commit a main → CI (2 badges) → Render reconstruye la imagen Docker con
migraciones al arrancar → Vercel reconstruye la web con las env vars.
BD en la nube con TODO el histórico; la web pública ya consume la API
pública. Dashboard README actualizado con la sección "☁️ Despliegue".

**Siguientes pasos:**
1. HIGIENE pendiente del dueño (menor): Reset password de Neon (el DSN
   circuló en una captura de pantalla durante la Fase 11) + pegar el nuevo
   DSN en Render → Environments → EDIT `DATABASE_URL` (el cambio re-deployea).
2. Fase 12: cron `data-refresh.yml` con `DATABASE_URL` de Neon y
   `FOOTBALL_API_KEY` como GitHub Secrets (el primer uso real del repo
   securizado contra la BD en producción) + puertas anti-solapamiento y
   auditables en Actions.

---

## Sesión 13 · 2026-10-23 · FASE 12 COMPLETA (pipeline de datos programado — cron cada 6 h)

**Qué se hizo:**
- `.github/workflows/data-refresh.yml` — workflow "Data Refresh", el corazón
  operativo del proyecto: cron `17 */6 * * *` (minuto 17 para esquivar la
  congestión de runners en ":00"; UTC → 00:17/06:17/12:17/18:17) + botón
  manual `workflow_dispatch` · `permissions: contents: read` · `concurrency`
  anti-solapamiento (encola el siguiente, no pelea por la BD) · job
  `timeout-minutes: 35` · secrets FOOTBALL_API_KEY + DATABASE_URL inyectados
  a nivel de job.
- Cadena 0/7…7/7: **0/7 sanidad de secrets** (comprueba que ambos llegan
  no-vacíos; imprime LONGITUD y esquema del DSN sin exponerlos jamás) →
  **1/7** `python -m pipeline --refresh` (20 requests, pacing 6.2 s, ~2 min)
  → **2/7** `python -m backend.app.load` (upserts idempotentes) → **3/7**
  baseline `modelo --todas --guardar` → **4/7** `modelo_dc --todas --guardar
  --vivas` → **5/7** `modelo_lgbm --todas --guardar --vivas` → **6/7**
  `evaluacion --todas --guardar` → **7/7 auditoría final** (python heredoc:
  conteos de `partidos`/`prediccion`/`reales_vs_previsto` + `assert` de las
  3 tablas no vacías; el log queda en Actions como evidencia auditable).
- **Dry-run end-to-end contra Neon ANTES de pushear** (mismo DSN que Render,
  `.venv` del repo — Docker Desktop apagado, regla del dueño): ingesta 20
  requests ~2 min; carga 0 duplicados (las PKs de la API ya estaban en BD);
  DC 323 evaluaciones + 1.252 vivas; LGBM 291 evaluaciones + 1.252 vivas
  (w re-tuneadas idénticas a Fase 5c: PD .10, PL .15, SA .35, BL1 .00,
  CL .40); evaluación 323; **BD final idéntica** a la previa
  (1.590/3.756/937 vía `/health` remoto) → idempotencia probada contra
  producción antes de programar nada.
- README: badge **Data Refresh** colocado en el asiento reservado desde la
  Fase 10.
- Blindaje de producción: `pipeline/config.py` añade `API_TOKEN.strip()`
  (desactiva espacios/saltos pegados por accidente en el secret) y el
  mensaje de error documenta la ruta GitHub Secrets además del .env local.

**El debugging del run #2 (lo interesante de esta fase):**
- La 1.ª corrida (dispatch manual sobre `5f399e8`) murió en **17 s**: el paso
  de la ingesta ni siquiera pudo completar 1 request con el pacing → la API
  pública de steps (checkout/setup-python/pip ✓, ingesta ❌, resto skipped)
  + las líneas rojas del dueño lo dijeron todo: **`ModuleNotFoundError: No
  module named 'httpx'`** en `pipeline/ingest.py:21` al importar.
- Causa raíz: `httpx` NO estaba en `backend/requirements.txt` — el `.venv`
  la tenía huérfana (`pip show` → `Required-by:` vacío: quedó instalada en
  su día sin rastro en el requirements). El dry-run pasó solo porque corría
  CON el venv completo y la CI nunca importa el pipeline (hueco ciego por
  diseño). El runner es limpio: SOLO existe lo pineado.
- Correcciones en serie: pins `httpx==0.28.1` + `numpy==2.5.4` (numpy la
  importa `modelo_lgbm` directo y solo llegaba transitiva de lightgbm) ·
  `.strip()` en la key · paso 0/7 de sanidad (diagnóstico futuro sin pedir
  logs a nadie).

**Evidencia del cierre — corrida #3 (commit `4609a62`, dispatch manual):**
los 9 pasos técnicos del job VERDE, **8 min 4 s** (17:53:59 → 18:02:03 UTC),
badge del README `passing`. CI verde en los 4 commits de la fase (`5f399e8`,
`ca0de49`, `4609a62`, `098c1d0` — el último con pulido del workflow:
numeración 7/7 del paso final, typo del comentario y assert reforzado).

**Lecciones de sesión:**
1. **La dependencia transitiva de regalo**: un venv acumula paquetes que un
   `requirements.txt` limpio jamás instalaría; el único entorno honesto es
   uno despiezado de cero (el runner). Regla nueva: toda dep IMPORTADA
   directamente se pinea aunque hoy llegue transitiva.
2. La CI no ejecuta el pipeline → ningún test la habría pillado. El guardián
   real es la cadena completa del propio workflow: dry-run local contra la
   BD REAL (los mismos comandos que el cron) antes de pushear + run manual
   de estreno.
3. Quirk de PowerShell 5.1: `$env:X=''` ELIMINA la variable en vez de
   asignarla vacía — un repro local de "secret ausente" requiere trucos
   propios y no simula al runner de forma fiable.
4. Los logs de Actions NO se leen anónimamente (403), pero `/runs` y
   `/jobs/{id}` SÍ publican el estado paso a paso → diseñar los
   autodiagnósticos del workflow para bastarse con eso (el 0/7 imprime
   longitudes, jamás valores).
5. Secrets: un espacio o salto de más al pegar produce la misma firma que
   una "key inválida" — `.strip()` neutraliza la clase entera de fallos.

**Estado tras Fase 12:** el sistema se alimenta SOLO — cada ~6 h (y a botón
siempre disponible): API football-data.org → Neon → 3 modelos walk-forward →
evaluación acumulada, y la web pública refleja el estado fresco sin que
nadie toque nada. BD en el cierre: **1.590 partidos · 3.756 predicciones ·
937 evaluaciones** (verificado vía `/health` tras el run #3).

**Siguientes pasos:**
1. Higiene del dueño (menor, sin prisa): ① Reset password de Neon → pegar el
   nuevo DSN en Render → Environments y en el secret `DATABASE_URL` de
   Actions ② borrar el secret sobrante `NEOM_API_KEY` ③ opcional:
   modernizar `checkout@v4→v5` y `setup-python@v5→v6` (avisos de Node 20 —
   cosméticos; GitHub ya los ejecuta en Node 24).
2. Fase 13 — MOTOR DE PREDICCIONES: siguientes palancas de precisión según
   el plano (fixtures con predicción con fecha, medición de aciertos al
   confirmarse resultados — el cron ya alimenta los datos que el motor
   necesita).





