import Link from "next/link";
import { Suspense } from "react";
import Aviso, { Cargando } from "@/components/Aviso";
import { obtenerEquipo, type ResultadoReciente } from "@/lib/api";
import { fechaDia, horaUtc, nombreLiga, num } from "@/lib/formato";

export const metadata = { title: "Equipo" };

export default function Pagina(props: PageProps<"/equipo/[id]">) {
  return (
    <Suspense fallback={<Cargando />}>
      <Contenido {...props} />
    </Suspense>
  );
}

async function Contenido(props: PageProps<"/equipo/[id]">) {
  const { id } = await props.params;
  const idNum = Number(id);

  let eq;
  try {
    eq = await obtenerEquipo(idNum);
  } catch {
    return (
      <div className="contenedor">
        <Aviso
          titulo={`No encuentro el equipo ${id}.`}
          detalle={<p>El id debe existir en la BD (los ids son de football-data.org).</p>}
        />
      </div>
    );
  }

  const c = eq.clasificacion;

  return (
    <div className="contenedor">
      <p className="titulo-sub">
        <Link href="/">Partidos</Link> ·{" "}
        {c && <Link href={{ pathname: `/ranking/${c.liga}` }}>{nombreLiga(c.liga)}</Link>}
      </p>

      <div className="ficha-cabecera">
        {eq.escudo_url && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={eq.escudo_url}
            alt={`Escudo de ${eq.nombre}`}
            className="escudo"
            loading="lazy"
          />
        )}
        <div>
          <h1 className="titulo-pagina">{eq.nombre}</h1>
          <p>
            {eq.tla && <span className="tla num">{eq.tla}</span>}
            {eq.fundacion && <span> · fundado en {eq.fundacion}</span>}
          </p>
        </div>
      </div>

      {c && (
        <>
          <div className="tablero-pos">
            <div>
              <small>Posición</small>
              <span className="grande">{c.posicion}</span>
            </div>
            <div>
              <small>Puntos</small>
              <span className="grande">{c.puntos}</span>
            </div>
            <div>
              <small>Portería</small>
              <span className="grande">
                {c.goles_favor}–{c.goles_contra}
              </span>
            </div>
            <div>
              <small>Balance</small>
              <span className="grande">
                {c.ganados}-{c.empatados}-{c.perdidos}
              </span>
            </div>
          </div>
          <div className="forma-celdas" aria-label="Forma reciente">
            {c.forma?.split("").map((letra, i) => (
              <ChipForma key={i} letra={letra} />
            ))}
          </div>
        </>
      )}

      <h2 className="titulo-bloque">Últimos 5 jugados</h2>
      {eq.ultimos5.length === 0 ? (
        <p className="titulo-sub">Aún no tiene partidos terminados en esta temporada.</p>
      ) : (
        <ul className="lista-fichas">
          {eq.ultimos5.map((p) => (
            <FilaResultado key={p.partido_id_api} p={p} nombreEquipo={eq.nombre} />
          ))}
        </ul>
      )}

      <h2 className="titulo-bloque">Próximos 3</h2>
      {eq.proximos3.length === 0 ? (
        <p className="titulo-sub">No hay partidos por jugar en la agenda.</p>
      ) : (
        <ul className="lista-fichas">
          {eq.proximos3.map((f) => (
            <li key={f.partido_id_api} className="fila-ficha">
              <span className="cuando">
                <span className="num">{fechaDia(f.fecha_utc)}</span>
                <span className="num">{horaUtc(f.fecha_utc)}</span>
              </span>
              <span>
                {f.local}
                <span className="rival-vs">—</span>
                {f.visitante}
              </span>
              <span className="num" style={{ textAlign: "right" }}>
                <Link href={{ pathname: `/partido/${f.partido_id_api}` }}>
                  ver pronóstico
                </Link>
              </span>
            </li>
          ))}
        </ul>
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

function FilaResultado({
  p,
  nombreEquipo,
}: {
  p: ResultadoReciente;
  nombreEquipo: string;
}) {
  // El schema de fases 7/8 no trae ids en resultados: casa/fuera sale por nombre.
  const local = p.local === nombreEquipo;
  const propios = local ? p.goles_local : p.goles_visitante;
  const rivales = local ? p.goles_visitante : p.goles_local;

  let veredicto = ["res-empato", "empate"];
  if (propios !== null && rivales !== null) {
    if (propios > rivales) veredicto = ["res-gano", "ganó"];
    else if (propios < rivales) veredicto = ["res-perdio", "perdió"];
  }

  return (
    <li className="fila-ficha">
      <span className="cuando">
        <span className="num">{fechaDia(p.fecha_utc)}</span>
        {local ? "casa" : "fuera"}
      </span>
      <span>
        {p.local} <span className="rival-vs">—</span> {p.visitante}
      </span>
      <span className="resultado-eq">
        <span className={veredicto[0]}>{num(propios, 0)}–{num(rivales, 0)}</span>
        <span className="diag" style={{ marginLeft: "0.5rem" }}>
          {veredicto[1]}
        </span>
      </span>
    </li>
  );
}
