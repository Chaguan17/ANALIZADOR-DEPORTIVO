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
