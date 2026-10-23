/**
 * Esqueleto de la home: imita la parrilla de boletines (Fase 14,
 * partido-protagonista) mientras la API responde. Puro CSS (pulso con
 * prefers-reduced-motion apagado).
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
              <div className="n-boletin-cuerpo">
                <div className="n-skel n-skel-meta" />
                <div className="n-skel n-skel-equipo" style={{ width: "82%" }} />
                <div className="n-skel n-skel-equipo" style={{ width: "58%" }} />
                <div className="n-skel n-skel-rec" style={{ width: "88%" }} />
                <div className="n-consenso">
                  <div className="n-skel n-skel-cons-label" />
                  <div className="n-skel n-skel-cons" />
                </div>
                <div className="n-chips-mini-skel">
                  <div className="n-skel n-skel-chip-mini" />
                  <div className="n-skel n-skel-chip-mini" style={{ width: "6.2rem" }} />
                </div>
              </div>
              <div className="n-voces-detalle">
                <div className="n-skel n-skel-detalle" />
              </div>
            </article>
          ))}
        </div>
      </div>
    </div>
  );
}
