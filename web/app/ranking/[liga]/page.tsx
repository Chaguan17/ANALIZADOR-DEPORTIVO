import Link from "next/link";
import { Suspense } from "react";
import Aviso, { Cargando } from "@/components/Aviso";
import { obtenerRankings, type ClasificacionFila } from "@/lib/api";
import { esLigaValida, LIGAS, nombreLiga } from "@/lib/formato";

export const metadata = { title: "Rankings" };

export default function Pagina(props: PageProps<"/ranking/[liga]">) {
  return (
    <Suspense fallback={<Cargando />}>
      <Contenido {...props} />
    </Suspense>
  );
}

async function Contenido(props: PageProps<"/ranking/[liga]">) {
  const { liga } = await props.params;

  if (!esLigaValida(liga)) {
    return (
      <div className="contenedor">
        <h1 className="titulo-pagina">Ranking</h1>
        <Aviso
          titulo={`"${liga}" no es una liga del MVP.`}
          detalle={
            <p>
              Elige una:{" "}
              {LIGAS.map((l, i) => (
                <span key={l.codigo}>
                  {i > 0 && " · "}
                  <Link href={{ pathname: `/ranking/${l.codigo}` }}>
                    {l.nombre}
                  </Link>
                </span>
              ))}
            </p>
          }
        />
      </div>
    );
  }

  let filas: ClasificacionFila[];
  try {
    filas = await obtenerRankings(liga);
  } catch {
    return (
      <div className="contenedor">
        <Aviso
          titulo="La web no pudo hablar con la API."
          detalle={<p>Levántala con <code>.venv\Scripts\python -m backend.app.api</code></p>}
        />
      </div>
    );
  }

  return (
    <div className="contenedor">
      <h1 className="titulo-pagina">Ranking · {nombreLiga(liga)}</h1>
      <p className="titulo-sub">
        <nav className="chips" aria-label="Liga del ranking">
          {LIGAS.map((l) => (
            <Link
              key={l.codigo}
              href={{ pathname: `/ranking/${l.codigo}` }}
              className={`chip${l.codigo === liga ? " chip-activa" : ""}`}
            >
              {l.nombre}
            </Link>
          ))}
        </nav>
        Formas: <b style={{ color: "#1b6b3a" }}>G</b> ganó ·{" "}
        <b style={{ color: "var(--tinta-2)" }}>E</b> empató ·{" "}
        <b style={{ color: "var(--c-2)" }}>P</b> perdió (últimos 5).
      </p>

      {filas.length === 0 ? (
        <Aviso titulo="Sin filas de clasificación para esta liga todavía." />
      ) : (
        <div className="tabla-scroll">
          <table className="tabla">
            <thead>
              <tr>
                <th className="num">Pos</th>
                <th>Equipo</th>
                <th className="num">J</th>
                <th className="num">G</th>
                <th className="num">E</th>
                <th className="num">P</th>
                <th className="num">GF</th>
                <th className="num">GC</th>
                <th className="num">DG</th>
                <th className="num">Pts</th>
                <th>Forma</th>
              </tr>
            </thead>
            <tbody>
              {filas.map((f) => (
                <tr key={f.equipo_id_api}>
                  <td className="num">{f.posicion}</td>
                  <td>
                    <Link href={{ pathname: `/equipo/${f.equipo_id_api}` }}>
                      {f.equipo}
                    </Link>
                  </td>
                  <td className="num">{f.jugados}</td>
                  <td className="num">{f.ganados}</td>
                  <td className="num">{f.empatados}</td>
                  <td className="num">{f.perdidos}</td>
                  <td className="num">{f.goles_favor}</td>
                  <td className="num">{f.goles_contra}</td>
                  <td className="num">{f.diferencia_goles}</td>
                  <td className="num">
                    <strong>{f.puntos}</strong>
                  </td>
                  <td>
                    <span className="forma-celdas">
                      {f.forma?.split("").map((letra, i) => (
                        <ChipForma key={i} letra={letra} />
                      ))}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function ChipForma({ letra }: { letra: string }) {
  if (letra === "W")
    return (
      <span className="forma-c f-gana" title="ganó">
        G
      </span>
    );
  if (letra === "D")
    return (
      <span className="forma-c f-empata" title="empató">
        E
      </span>
    );
  return (
    <span className="forma-c f-pierde" title="perdió">
      P
    </span>
  );
}
