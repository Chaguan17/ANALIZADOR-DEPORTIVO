# .github/workflows/ — CI/CD

Aquí viven los workflows de GitHub Actions (Fases 10-12 del plano maestro):

- `ci.yml` — **Fase 10**: en cada PR/push, job backend (ruff → pytest → docker build)
  y job frontend (npm lint → build) en paralelo. La regla: CI verde o no se fusiona.
- `data-refresh.yml` — **Fase 12**: cron (~6 h) que ejecuta el pipeline → Postgres (Neon).
- Deploy: Render (backend) y Vercel (frontend) despliegan solos desde `main` — **Fase 11**.

La API key y la cadena de conexiones van en **GitHub Secrets** (`FOOTBALL_API_KEY`,
`DATABASE_URL`), nunca en el código.
