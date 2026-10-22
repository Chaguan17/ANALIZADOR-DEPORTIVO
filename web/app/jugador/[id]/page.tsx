import Link from "next/link";
import { Suspense } from "react";
import Aviso, { Cargando } from "@/components/Aviso";
import { obtenerJugador } from "@/lib/api";

export const metadata = { title: "Jugador" };

export default function Pagina(props: PageProps<"/jugador/[id]">) {
  return (
    <Suspense fallback={<Cargando />}>
      <Contenido {...props} />
    </Suspense>
  );
}

async function Contenido(props: PageProps<"/jugador/[id]">) {
  const { id } = await props.params;
  const idNum = Number(id);

  let jug;
  try {
    jug = await obtenerJugador(idNum);
  } catch {
    return (
      <div className="contenedor">
        <Aviso
          titulo={`No encuentro al jugador ${id}.`}
          detalle={
            <p>
              Con el free tier solo tenemos fichas básicas de los jugadores que
              expone football-data.org; el catálogo navegable llega en la Fase 6.
            </p>
          }
        />
      </div>
    );
  }

  return (
    <div className="contenedor">
      <p className="titulo-sub">
        {jug.equipo_id_api ? (
          <Link href={{ pathname: `/equipo/${jug.equipo_id_api}` }}>
            {jug.equipo}
          </Link>
        ) : (
          "sin club registrado"
        )}
      </p>
      <h1 className="titulo-pagina">{jug.nombre}</h1>

      <dl className="ficha-cabecera" style={{ display: "grid", gap: "0.2rem" }}>
        <div>
          <dt className="diag">Posición</dt>
          <dd>{jug.posicion ?? "—"}</dd>
        </div>
        <div>
          <dt className="diag">Nacionalidad</dt>
          <dd>{jug.nacionalidad ?? "—"}</dd>
        </div>
        <div>
          <dt className="diag">Nacimiento</dt>
          <dd>{jug.fecha_nac ?? "—"}</dd>
        </div>
      </dl>

      <Aviso
        titulo="Este perfil todavía está en pañales."
        detalle={<p>{jug.nota} Mientras tanto, lo que ves es la ficha real de la BD.</p>}
      />
    </div>
  );
}
