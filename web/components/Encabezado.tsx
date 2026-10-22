import Link from "next/link";

const ENLACES: Array<{ href: string; texto: string }> = [
  { href: "/", texto: "Partidos" },
  { href: "/ranking/PD", texto: "Rankings" },
  { href: "/precision", texto: "Precisión" },
];

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
        <nav className="nav-principal" aria-label="Principal">
          {ENLACES.map((e) => (
            <Link key={e.href} href={e.href} className="nav-enlace">
              {e.texto}
            </Link>
          ))}
        </nav>
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
