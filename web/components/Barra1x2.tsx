import { pct } from "@/lib/formato";

/**
 * Barra apilada 1X2: un solo lenguaje visual en toda la web.
 * El color codifica el RESULTADO (1 local azul · X empate gris · 2 visita rojo),
 * nunca el modelo — la voz del modelo va en puntos y acentos aparte.
 */
export default function Barra1x2({
  pl,
  px,
  pv,
}: {
  pl: number | null;
  px: number | null;
  pv: number | null;
}) {
  const sumas = [pl, px, pv].reduce<number>((a, b) => a + (b ?? 0), 0);
  if (sumas <= 0) return null;

  return (
    <span className="barra1x2" role="img" aria-label={`Local ${pct(pl)}, empate ${pct(px)}, visita ${pct(pv)}`}>
      <span style={{ width: `${100 * (pl ?? 0) / sumas}%` }} className="seg-1" />
      <span style={{ width: `${100 * (px ?? 0) / sumas}%` }} className="seg-x" />
      <span style={{ width: `${100 * (pv ?? 0) / sumas}%` }} className="seg-2" />
    </span>
  );
}

/** Leyenda compartida — se muestra una vez por página, no por fila. */
export function Leyenda1x2() {
  return (
    <span className="leyenda1x2">
      <span className="ley-1">1 local</span>
      <span className="ley-x">X empate</span>
      <span className="ley-2">2 visita</span>
    </span>
  );
}
