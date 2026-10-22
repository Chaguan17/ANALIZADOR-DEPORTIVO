# Web — Analizador Deportivo (Next.js)

Frontend de la **Fase 9**: consume la API FastAPI del backend (`../backend/app/api.py`)
y muestra las predicciones de los 3 modelos (poisson_doble, poisson_dc, lightgbm_v1).

## Páginas

| Ruta             | Qué muestra                                                        |
|------------------|--------------------------------------------------------------------|
| `/`              | Próximos partidos de una liga, con la voz de UN modelo elegible     |
| `/partido/[id]`  | Detalle: las 3 voces lado a lado + diagnóstico JSONB (ρ, w, evidencia) |
| `/equipo/[id]`   | Ficha: posición/puntos, forma, últimos 5, próximos 3                |
| `/jugador/[id]`  | Ficha básica (los stats por partido llegan en la Fase 6)            |
| `/ranking/[liga]`| Tabla de posiciones con formas G/E/P                                |
| `/precision`     | La batalla honesta: log loss / acierto por modelo y liga            |

## Cómo correr

```powershell
# 1) La API (en otra terminal):
.venv\Scripts\python -m backend.app.api     # → http://127.0.0.1:8000

# 2) La web:
cd web
npm install              # solo la primera vez
npm run dev              # → http://localhost:3000
```

## Variables de entorno

- `NEXT_PUBLIC_API_URL` — la que ve el **navegador** (default `http://127.0.0.1:8000`).
- `API_URL_SERVIDOR` — opcional: la que usa el **servidor de Next** para el SSR
  (en docker sería `http://api:8000`). Sin ella usa `NEXT_PUBLIC_API_URL`.

Copia `.env.example` → `.env.local` para armar el tuyo (`.env.local` no se
commitea nunca).

## Arquitectura honesta

- **Todo server-side**: las páginas son componentes de servidor que hacen
  `fetch` a la API con `cache: "no-store"` — datos frescos en cada petición,
  envueltos en `<Suspense>` (modo `cacheComponents` de Next 16).
- Los contratos TypeScript están en `web/lib/api.ts`: espejo 1:1 de los
  esquemas Pydantic del backend. Si cambia la API, cambian ahí.
- El color de las barras codifica el **resultado** (1 azul / X gris / 2 rojo);
  el color de las voces identifica al **modelo** (Poisson azul, DC oro,
  LightGBM violeta) en toda la interfaz.
