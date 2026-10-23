/**
 * Esqueleto de la home: imita la parrilla de boletines mientras la API
 * responde. Puro CSS (pulso con prefers-reduced-motion apagado).
 */
export default function SkeletonPartidos() {
  return (
    <div className="noche">
      <div className="contenedor">
        <p className="n-sr" role="status">
          Cargando los próximos partidos…
        </p>
        <div className="n-skel n-skel-titulo" />
        <div className="n-skel n-skel-kicker" />
        <div className="n-chips-skel" aria-hidden="true">
          {Array.from({ length: 5 }, (_, i) => (
            <div key={i} className="n-skel n-skel-chip" />
          ))}
        </div>
        <div className="n-parrilla">
          {Array.from({ length: 6 }, (_, i) => (
            <article key={i} className="n-boletin" aria-hidden="true">
              <div className="n-skel n-skel-meta" />
              <div className="n-skel n-skel-equipo" style={{ width: "82%" }} />
              <div className="n-skel n-skel-equipo" style={{ width: "58%" }} />
              <div className="n-skel n-skel-barra" style={{ width: "88%" }} />
              <div className="n-skel n-skel-barra" style={{ width: "74%" }} />
              <div className="n-skel n-skel-barra" style={{ width: "80%" }} />
              <div className="n-firmas-skel">
                <div className="n-skel n-skel-firma" />
                <div className="n-skel n-skel-firma" />
                <div className="n-skel n-skel-firma" />
              </div>
            </article>
          ))}
        </div>
      </div>
    </div>
  );
}
