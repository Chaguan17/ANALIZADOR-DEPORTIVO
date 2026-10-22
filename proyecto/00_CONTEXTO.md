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
| 2026-10-22 | Ligas MVP: **LaLiga (PD) · Premier (PL) · Serie A (SA) · Bundesliga (BL1) · Champions (CL)** | Decisión del propietario; se ampliará a futuro. |
| 2026-10-22 | **Europa League (EL) fuera del MVP inicial** | Confirmado con la API key real: el free tier de football-data.org solo da acceso a 13 competiciones (BSA, ELC, PL, CL, EC, FL1, BL1, SA, DED, PPL, CLI, PD, WC) y **EL no está entre ellas** (HTTP 403). Se integrará después vía API-Football (100 req/día gratis). |
| 2026-10-22 | **Esquema Fase 3**: PKs = id de la API · tabla `clasificacion` añadida (fuente: standings) · `stats_*` usan JSONB extensible y se llenan en Fases 4-8 | El upsert por id de la API hace la carga naturalmente idempotente; los stats del free tier son flexibles; desviación bienintencionada del nombre del plano documentada |
| 2026-10-22 | **Modelo baseline Fase 5: Poisson doble** (λ = μ·atk·dfn → grid de marcadores 0..8) | Transparente y sin dependencias; sirve de referencia contra la que medir Dixon-Coles y LightGBM; 100% walk-forward (parámetros SOLO con partidos previos al partido a predecir) |
| 2026-10-22 | **Protecciones del Poisson**: K_SHRINK=8 (contracción de fuerzas hacia la media), fuerzas recortadas a [0.4, 2.5], cúpula λ ∈ [0.2, 4.5], masa del grid renormalizada | El producto multiplicativo explotaba con muestras pequeñas (λ 11.27 en la Champions con solo 3 fechas; P(local) 99.97%). Con protecciones: max λ 3.76, max P1 88.07% — intensidades plausibles de fútbol real |
| 2026-10-22 | **Evaluación Fase 7 (métricas y benchmark)**: log loss + Brier 1X2, accuracy 1X2 y O2.5, calibración en cubetas de 10%, MAE de goles | El free tier NO expone cuotas de apuestas → el benchmark del plano se sustituye por baselines universales sin datos: 'siempre local' (accuracy = % de locales ganadores del propio set), 'uniforme' (log loss ln3 ≈ 1.0986, Brier 2/3 ≈ 0.6667) y 'siempre over 2.5' |
| 2026-10-22 | **Calentamiento en evaluación**: se salta el arranque frío (< MIN_EVIDENCIA=2 partidos previos) y se avanza con **piso defensivo MU_MINIMO=0.1** en las medias de liga | El primer partido de temporada hacía μ→0 (división/0) y equipos nunca vistos disparaban KeyError → fallback fuerza neutral 1.0; con la contracción activa el piso no genera λ explosivos |
| 2026-10-22 | **Dixon-Coles (Fase 5b)**: τ sobre las 4 celdas bajas (0-0: 1−λμρ · 1-0: 1+μρ · 0-1: 1+λρ · 1-1: 1−ρ, clamp ≥0), ρ por liga grid-search −0.300…0.050 paso 0.0125 minimizando log loss; las λ NO cambian (solo re-ponderación del grid) | Corrige el peso empírico de los marcadores bajos que la Poisson independiente pesa mal; el matiz in-sample de 1 parámetro se documenta y acepta (riesgo mínimo); además el hallazgo: masa total invariante ⇒ τ no altera O2.5 |
| 2026-10-22 | **API Fase 8**: FastAPI con sesión por petición (`Depends(get_session)`), Pydantic para contratos, Swagger auto (/docs), CORS `["*"]` | El contrato sirve los ids de football-data.org tal cual; los múltiples modelos coexisten por la UNIQUE (partido, modelo) → /fixtures y /predictions devuelven TODOS los modelos de cada partido; el CORS abierto permite el consumo desde Vercel (se estrechará en producción) |
| 2026-10-22 | **Docker del api**: `backend/Dockerfile` (python:3.14-slim, instalar → copiar `app/` → `uvicorn app.api:app`) + servicio `api` en compose con `depends_on: db healthy` y `DATABASE_URL` al host `db` | Ejecución 100% manual del propietario (`docker compose up -d db api`): la API dockerizada comparte red interna con Postgres; build retirado del flujo automatizado por regla del proyecto (dueño manda sus contenedores) |
| 2026-10-22 | **LightGBM v1 (Fase 5c) = árbol + mezcla con la uniforme** `p = w·p_árbol + (1−w)/3`, w por liga grid-search 0.00…1.00 paso 0.05 minimizando log loss walk-forward | La primera corrida del árbol puro fue SOBRECONFIADA (PD log loss 1.6013, accuracy 32.5%, prometió 99% en favoritos): con 54-89 filas FINISHED por liga, los árboles memorizan en vez de generalizar. La mezcla es el análogo del K_SHRINK; el w elegido MIDE honestamente la señal del árbol (BL1 w=0.00 = uniforme pura). Formato de salida: SOLO 1X2; λ/O2.5/marcador NULL en BD (el árbol no emite intensidades; fabricarlas encima sería doble modelo disfrazado). API raw de lightgbm (sin scikit-learn) y guard de clases (3 presentes) en el calentamiento |
| 2026-10-22 | **Frontend Fase 9**: Next.js 16 (App Router + TypeScript + Tailwind v4) en `web/`, TODO server-side: fetch a la API `no-store` dentro de `<Suspense>` (modo `cacheComponents` → shell estático + datos frescos por streaming); contratos TS espejo de Pydantic en `web/lib/api.ts`; `NEXT_PUBLIC_API_URL` para el navegador y `API_URL_SERVIDOR` para el SSR (docker usa `http://api:8000`) | La web jamás toca la BD: TODA la verdad baja por la API (un solo contrato, el mismo id de football-data.org). Docker del web deferido a Fase 11 (producción es Vercel; desviación menor documentada respecto al comentario original del compose) |
| 2026-10-22 | **CI Fase 10**: DOS workflows separados (`.github/workflows/ci-backend.yml` + `ci-web.yml` → un badge por cada uno). Backend: setup-python 3.14 → `pip install -r backend/requirements.txt` (ruff y pytest pinneados dentro) → `ruff check backend pipeline` → `pytest -q` → `docker build ./backend`. Web: setup-node 22 + cache npm → `npm ci` → `npm run lint` → `npm run build` | Las pruebas son pytest PURAS (sin BD): los imports del backend son perezosos (el engine se construye sin conectar) y `HistoriaLiga` se fabrica en la prueba vía `__new__` porque sus métodos de consulta son puros → CI veloz, sin servicio Postgres, sin secretos en el runner. Ruff con `select` EXPLÍCITO (E4/E7/E9/F/I/RUF100): sin reglas cosméticas para que CI no rompa por modas del linter; el B008 alertado era el patrón INTENCIONAL de capturar variables del loop en defaults del `def` (anti late-binding) — ni se toca |

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

- **Principal:** football-data.org → competiciones/partidos/clasificación/plantillas y goleadores
- **Ligas del MVP (verificado con la API key real, 2026-10-22):** LaLiga `PD` ✅ · Premier `PL` ✅ ·
  Serie A `SA` ✅ · Bundesliga `BL1` ✅ · Champions `CL` ✅ · **Europa League `EL` ❌ fuera del free tier**
  → se agregará después vía API-Football
- Free tier disponible además para: Brasileirão `BSA`, Championship `ELC`, Eurocopa `EC`, Ligue 1 `FL1`,
  Eredivisie `DED`, Primeira Liga `PPL`, Libertadores `CLI`, Mundial `WC`
- **Limitación conocida del free tier:** goleadores solo con los **10 mejores por liga**
  (listas completas: FBref/Understat en la Fase 6)
- **Respaldo para jugadores (Fase 6):** FBref / Understat (CSV o scraping puntual)
- **Límites:** 10 peticiones/minuto en el tier gratuito → todos los datos se persisten en disco crudo
  y luego en Postgres; nunca se pide a la API lo que ya está guardado (caché-first).

## 9. PENDIENTE POR DECIDIR

- [x] ~~Liga(s) objetivo del MVP~~ → decidido y **verificado contra la API real** 2026-10-22: PD, PL, SA, BL1, CL · EL queda fuera del free tier (se integrará vía API-Football)
- [x] API key de football-data.org funcionando (guardada en `.env` local, fuera de Git)
- [x] Repositorio GitHub conectado: `github.com/Chaguan17/ANALIZADOR-DEPORTIVO` (2026-10-22)
- [ ] Licencia (MIT recomendado si es público)

---

## 10. CATÁLOGO DE FEATURES — EQUIPOS (Fase 4)

Fuente de código: `backend/app/features.py` · Regla de oro: **walk-forward**
(un feature para el partido X usa SOLO partidos con fecha < X; sin filtración de futuro).

| Grupo | Features (claves exactas) | Justificación |
|---|---|---|
| Forma (ventana 5) | `forma_pts5_local/visita`, `forma_gf5_local/visita`, `forma_gc5_local/visita`, `forma_j5_local/visita` | Puntos, goles a favor y en contra de los últimos 5 partidos: mide momentum reciente (la tabla acumula, la forma pesa hoy) |
| Condición casa/fuera | `ppg_casa_local`, `gf_prom_casa_local`, `gc_prom_casa_local`, `j_casa_local`, `ppg_fuera_visita`, `gf_prom_fuera_visita`, `gc_prom_fuera_visita`, `j_fuera_visita` | Media de PPG/goles como local del equipo local y como visitante del visitante: la ventaja de campo es una de las anomalías más robustas del fútbol |
| Descanso | `descanso_local`, `descanso_visita` | Días desde su último partido: calendario congestionado y daño(sentencia resistencia). |
| Tabla snapshot | `pos_local`, `pos_visita`, `tabla_pts_local/visita`, `tabla_dg_local/visita`, `tabla_j_local/visita` | Clasificación RECOMPUTADA punto-en-tiempo (solo partidos previos; la `Clasificacion` de la API es un snapshot del presente y NO sirve para backtesting) |
| historial directo (H2H) | `h2h_jugados`, `h2h_ganados_local`, `h2h_empates`, `h2h_ganados_visita`, `h2h_gf_prom` | Enfrentamientos previos entre ambos (últimos 6): rivalidad/patrón de estilo |

Total: **31 features por partido** (8 forma + 8 condición + 2 descanso + 8 tabla + 5 H2H).

### Limitaciones documentadas (con plan de resolución)
- **H2H limitado a la temporada corriente** (la historia se carga por temporada) →
  si se quiere profundidad histórica, extender `HistoriaLiga` para cargar temporadas
  previas (más requests en Fase 2 o CSV de FBref). Registrado para mejora futura.
- **Sin xG** en el free tier de football-data.org → el substituto tangente son los
  goles medios (rolling); xG real via scraping Understat si se desea (Fase 14+).
- **Features de JUGADOR diferidos a la Fase 6** (el free tier solo da top-10 goleadores
  agregados, sin minutos ni por partido; al llegar se documentarán en esta misma sección).
