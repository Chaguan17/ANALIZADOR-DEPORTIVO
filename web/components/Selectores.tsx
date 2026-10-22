import Link from "next/link";
import { LIGAS, MODELOS } from "@/lib/formato";

/** Chips de liga (links con query); mantiene el modelo elegido. */
export function SelLiga({ activa, modelo }: { activa: string; modelo: string }) {
  return (
    <nav className="chips" aria-label="Liga">
      {LIGAS.map((l) => (
        <Link
          key={l.codigo}
          href={{ pathname: "/", query: { liga: l.codigo, modelo } }}
          className={`chip${l.codigo === activa ? " chip-activa" : ""}`}
          aria-current={l.codigo === activa ? "true" : undefined}
        >
          {l.nombre}
        </Link>
      ))}
    </nav>
  );
}

/** Selector de modelo (las tres voces) — el pomo de la comparación. */
export function SelModelo({ activo, liga }: { activo: string; liga: string }) {
  return (
    <nav className="sel-modelo" aria-label="Modelo">
      {MODELOS.map((m) => (
        <Link
          key={m.id}
          href={{ pathname: "/", query: { liga, modelo: m.id } }}
          className={`voz${m.id === activo ? " voz-activa" : ""} voz-${m.id}`}
          aria-current={m.id === activo ? "true" : undefined}
          title={m.nota}
        >
          <span className="punto-voz" aria-hidden="true" />
          {m.nombre}
        </Link>
      ))}
    </nav>
  );
}
