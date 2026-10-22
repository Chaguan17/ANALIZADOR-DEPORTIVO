import type { ReactNode } from "react";

/** Estado vacío u error, con dirección de qué hacer — nunca vago. */
export default function Aviso({
  titulo,
  detalle,
}: {
  titulo: string;
  detalle?: ReactNode;
}) {
  return (
    <div className="aviso">
      <strong>{titulo}</strong>
      {detalle && <div className="aviso-detalle">{detalle}</div>}
    </div>
  );
}

export function Cargando({ etiqueta = "Cargando datos…" }: { etiqueta?: string }) {
  return (
    <p className="cargando" role="status">
      {etiqueta}
    </p>
  );
}
