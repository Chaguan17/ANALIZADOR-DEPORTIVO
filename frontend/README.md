# frontend/ — UI Next.js

Aquí vive el **frontend** del sistema (Fase 9 del plano maestro):

- Next.js con **App Router** + **TypeScript** estricto + Tailwind CSS
- Páginas: Próximos partidos · Detalle de partido (probabilidades 1X2, marcadores,
  over/under) · Perfil de equipo · Perfil de jugador con buscador · Ranking ·
  Precisión histórica del modelo
- Gráficas con Recharts · `fetch` al backend vía `NEXT_PUBLIC_API_URL`
- Despliegue objetivo: **Vercel** (Fase 11) con URL de **preview por cada PR**

Se crea con `create-next-app` cuando llegue su fase para no bloquear adelantos.
