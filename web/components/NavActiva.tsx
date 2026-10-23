"use client";

/**
 * Nav con estado activo — el pathname solo se lee desde un componente
 * cliente (usePathname); Encabezado lo envuelve en <Suspense> para que
 * las páginas con parámetro dinámico sigan prerenderizando su shell.
 */
import Link from "next/link";
import { usePathname } from "next/navigation";

export type Enlace = { href: string; base: string; texto: string };

/** Enlaces del sitio. `base` = el prefijo que activa el enlace. */
export const ENLACES: Enlace[] = [
  { href: "/", base: "/", texto: "Partidos" },
  { href: "/torneo", base: "/torneo", texto: "Torneo" },
  { href: "/ranking/PD", base: "/ranking", texto: "Rankings" },
  { href: "/precision", base: "/precision", texto: "Precisión" },
];

/** Presentación pura — sirve como fallback antes de conocer el pathname. */
export function NavLinks({ activa }: { activa: string | null }) {
  return (
    <nav className="nav-principal" aria-label="Principal">
      {ENLACES.map((e) => (
        <Link
          key={e.href}
          href={e.href}
          className={`nav-enlace${activa === e.base ? " nav-activa" : ""}`}
          aria-current={activa === e.base ? "page" : undefined}
        >
          {e.texto}
        </Link>
      ))}
    </nav>
  );
}

/** Devuelve la base del enlace activo para un pathname (null = no resuelto). */
export function baseDe(pathname: string | null): string | null {
  if (!pathname) return null;
  const golpe = ENLACES.find((e) =>
    e.base === "/" ? pathname === "/" : pathname.startsWith(e.base),
  );
  return golpe ? golpe.base : null;
}

export default function NavActiva() {
  const pathname = usePathname();
  return <NavLinks activa={baseDe(pathname)} />;
}
