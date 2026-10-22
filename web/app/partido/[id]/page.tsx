import Link from "next/link";
import { Suspense } from "react";
import Aviso, { Cargando } from "@/components/Aviso";
import Barra1x2 from "@/components/Barra1x2";
import {
  numDe,
  obtenerPredicciones,
  type DatosExtra,
  type PrediccionesPartido,
} from "@/lib/api";
import { fechaDia, horaUtc, nombreModelo, num, pct } from "@/lib/formato";

export const metadata = { title: "Detalle de partido" };

export default function Pagina(props: PageProps<"/partido/[id]">) {
  return (
    <Suspense fallback={<Cargando />}>
      <Contenido {...props} />
    </Suspense>
  );
}

async function Contenido(props: PageProps<"/partido/[id]">) {
  const { id } = await props.params;
  const idNum = Number(id);

  let data: PrediccionesPartido;
  try {
    data = await obtenerPredicciones(idNum);
  } catch {
    return (
      <div className="contenedor">
        <Aviso
          titulo={`No hay predicciones guardadas para el partido ${id}.`}
          detalle={
            <p>
              O el id no existe, o es un partido ya jugado sin pronóstico
              guardado. La lista de partidos vivos está en{" "}
              <Link href="/">Partidos</Link>.
            </p>
          }
        />
      </div>
    );
  }

  const primera = data.predicciones[0]?.datos ?? null;
  const idLocal = numDe(primera, "id_local");
  const idVisita = numDe(primera, "id_visitante");

  return (
    <div className="contenedor">
      <p className="titulo-sub">
        <Link href="/">Todos los partidos</Link> · {fechaDia(data.fecha_utc)}{" "}
        {horaUtc(data.fecha_utc)}
        {data.jornada != null && <> · Jornada {data.jornada}</>}
      </p>
      <h1 className="titulo-pagina">
        {data.local}
        <span className="rival-vs">—</span>
        {data.visitante}
      </h1>
      {idLocal && idVisita && (
        <p className="titulo-sub">
          <Link href={{ pathname: `/equipo/${idLocal}` }}>Ficha del local</Link>{" "}
          ·{" "}
          <Link href={{ pathname: `/equipo/${idVisita}` }}>
            Ficha del visitante
          </Link>
        </p>
      )}

      <h2 className="titulo-bloque">Las tres voces, lado a lado</h2>
      <div className="tabla-scroll">
        <table className="tabla">
          <thead>
            <tr>
              <th>Modelo</th>
              <th className="num">1 local</th>
              <th className="num">X empate</th>
              <th className="num">2 visita</th>
              <th className="num">λ local</th>
              <th className="num">λ visita</th>
              <th className="num">Over 2.5</th>
              <th className="num">Marcador</th>
            </tr>
          </thead>
          <tbody>
            {data.predicciones.map((pr) => (
              <FilaModelo
                key={pr.modelo}
                modelo={pr.modelo}
                datos={pr.datos}
                pl={pr.prob_local}
                px={pr.prob_empate}
                pv={pr.prob_visita}
                lamL={pr.lam_local}
                lamV={pr.lam_visita}
                o25={pr.prob_over25}
                marcador={pr.marcador_estimado}
              />
            ))}
          </tbody>
        </table>
      </div>

      <p className="titulo-sub" style={{ marginTop: "1.2rem" }}>
        λ = goles esperados de cada equipo. Los campos «—» significan que ese
        modelo no emite esa salida (LightGBM v1 es solo 1X2) — en vez de
        inventarnos números, los dejamos honestamente vacíos.
      </p>
    </div>
  );
}

function FilaModelo({
  modelo,
  datos,
  pl,
  px,
  pv,
  lamL,
  lamV,
  o25,
  marcador,
}: {
  modelo: string;
  datos: DatosExtra | null;
  pl: number | null;
  px: number | null;
  pv: number | null;
  lamL: number | null;
  lamV: number | null;
  o25: number | null;
  marcador: string | null;
}) {
  return (
    <>
      <tr className="fila-modelo">
        <td>
          <span
            aria-hidden="true"
            style={{ background: setColor(modelo) }}
            className="punto-voz"
          />{" "}
          {nombreModelo(modelo)}
        </td>
        <td className="num">{pct(pl)}</td>
        <td className="num">{pct(px)}</td>
        <td className="num">{pct(pv)}</td>
        <td className="num">{num(lamL)}</td>
        <td className="num">{num(lamV)}</td>
        <td className="num">{pct(o25)}</td>
        <td className="num">{marcador ?? "—"}</td>
      </tr>
      <tr className="diag">
        <td colSpan={8}>
          <Barra1x2 pl={pl} px={px} pv={pv} />
        </td>
      </tr>
      <tr className="diag">
        <td colSpan={8}>{diagnostico(modelo, datos)}</td>
      </tr>
    </>
  );
}

/** Extrae la línea de diagnóstico del JSONB, con vocabulario del proyecto. */
function diagnostico(modelo: string, d: DatosExtra | null): string {
  const w = numDe(d, "mezcla_uniforme");
  const rho = numDe(d, "rho");
  const evid = numDe(d, "partidos_evidencia");
  const masa = numDe(d, "masa_grid");

  const historia =
    evid !== null
      ? modelo === "lightgbm_v1"
        ? `entrenado con ${evid} partidos terminados`
        : `parámetros estimados con ${evid} partidos previos`
      : null;

  switch (modelo) {
    case "poisson_doble":
      return [
        "estructura de μ·atk·dfn",
        historia,
        masa !== null ? `masa del grid renormalizada: ${num(masa, 3)}` : null,
      ]
        .filter(Boolean)
        .join(" · ");
    case "poisson_dc":
      return [
        "igual que Poisson, con τ en marcadores bajos",
        rho !== null ? `ρ = ${rho.toFixed(4)} (elegida por log loss)` : null,
        historia,
      ]
        .filter(Boolean)
        .join(" · ");
    case "lightgbm_v1":
      return [
        "31 features walk-forward",
        w !== null
          ? `mezcla con la uniforme w = ${w.toFixed(2)} (${
              w > 0.5 ? "el árbol aporta bastante" : "el árbol aporta poco"
            })`
          : null,
        historia,
      ]
        .filter(Boolean)
        .join(" · ");
    default:
      return historia ?? "sin diagnóstico";
  }
}

function setColor(modelo: string): string {
  if (modelo === "poisson_doble") return "var(--voz-poisson-doble)";
  if (modelo === "poisson_dc") return "var(--voz-poisson-dc)";
  return "var(--voz-lightgbm-v1)";
}
