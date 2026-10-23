import Link from "next/link";
import { Suspense } from "react";
import NavActiva, { NavLinks } from "./NavActiva";

export default function Encabezado() {
  return (
    <header className="pizarra-barra">
      <div className="barra-interior">
        <Link href="/" className="marca">
          <span className="marca-texto">Analizador Deportivo</span>
          <span className="marca-lema">
            Tres modelos compiten, una sola verdad: el resultado.
          </span>
        </Link>
        {/* El estado activo exige el pathname (hook de cliente); con
            cacheComponents, el <Suspense> mantiene el shell prerenderizado
            en las rutas dinámicas y hidrata la marca activa en el cliente. */}
        <Suspense fallback={<NavLinks activa={null} />}>
          <NavActiva />
        </Suspense>
      </div>
    </header>
  );
}

export function Pie() {
  return (
    <footer className="pizarra-pie">
      <p>
        Datos de football-data.org (free tier) · Predicciones walk-forward ·
        Cada pronóstico se evalúa contra el resultado real.
      </p>
    </footer>
  );
}
