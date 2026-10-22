# pipeline/ — Ingesta de datos

Aquí vive el **pipeline de datos** (Fases 2 y 12 del plano maestro):

- Cliente de football-data.org con límite de **10 req/min** (pacing interno), reintentos
  con backoff y **caché-first**: cada dato se pide a la API una sola vez y queda en
  `raw/{LIGA}/` (JSON crudo, auditable, ignorado por Git).
- Ligas MVP verificadas con la key real: `PD`, `PL`, `SA`, `BL1`, `CL`
  (Europa League `EL` no existe en free tier → deferida a API-Football).

## Estructura de datos crudos

```
pipeline/raw/
├── PD/  partidos_2026.json · clasificacion_2026.json · equipos_2026.json · goleadores_2026.json
├── PL/  …
├── SA/  …
├── BL1/ …
└── CL/  …
```

## Uso

```powershell
# 1) Entorno virtual (una vez)
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt

# 2) Ingesta desde la raíz del repo
.venv\Scripts\python -m pipeline           # descarga lo que falta (caché-first)
.venv\Scripts\python -m pipeline --refresh # re-descarga todo (~20 req ≈ 2 min)
.venv\Scripts\python -m pipeline.qa        # QA de los JSON crudos (no gasta cuota)

# Menos ruido: --quiet  ·  Exit code: 0 ok / 1 con errores (para CI, Fase 10)
```

La key se lee del `.env` de la raíz (`FOOTBALL_API_KEY`), nunca se commitea.
