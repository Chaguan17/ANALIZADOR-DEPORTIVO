# pipeline/ — Ingesta de datos

Aquí vive el **pipeline de datos** (Fases 2 y 12 del plano maestro):

- Cliente de football-data.org con límite de **10 req/min**, reintentos y caché
- Descarga: partidos (temporada), clasificación, plantillas, goleadores
- Los **JSON crudos** se guardan en `raw/` (auditable, ignorado por Git) antes de transformar
- Transformaciones → Postgres con cargas idempotentes (upsert)
- Se ejecuta: manual en fase de construcción, y programado con el cron de
  GitHub Actions (`data-refresh.yml`, Fase 12) cada ~6 h
