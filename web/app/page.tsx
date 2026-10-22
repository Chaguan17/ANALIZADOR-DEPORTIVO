import Link from "next/link";
import { Suspense } from "react";
import Aviso, { Cargando } from "@/components/Aviso";
import Barra1x2, { Leyenda1x2 } from "@/components/Barra1x2";
import { SelLiga, SelModelo } from "@/components/Selectores";
import { obtenerFixtures, type Fixture } from "@/lib/api";
import {
  esLigaValida,
  esModeloValido,
  fechaDia,
  horaUtc,
  nombreLiga,
  nombreModelo,
  pct,
} from "@/lib/formato";

export const metadata = { title: "Próximos partidos" };

export default function Pagina(props: PageProps<"/">) {
  return (
    <Suspense fallback={<Cargando />}>
      <Contenido {...props} />
    </Suspense>
  );
}

async function Contenido({ searchParams }: PageProps<"/">) {
  const { liga: pLiga, modelo: pModelo } = await searchParams;
  const liga = esLigaValida(pLiga) ? pLiga : "PD";
  const modelo = esModeloValido(pModelo) ? pModelo : "poisson_dc";

  let partidos: Fixture[];
  try {
    partidos = await obtenerFixtures(liga);
  } catch (e) {
    return (
      <div className="contenedor">
        <Aviso
          titulo="La web no pudo hablar con la API."
          detalle={
            <>
              <p>
                Revísale el error en la consola de Next ({String(e)})… y si la
                API está apagada, levántala:
              </p>
              <p>
                <code>.venv\Scripts\python -m backend.app.api</code>
              </p>
            </>
          }
        />
      </div>
    );
  }

  return (
    <div className="contenedor">
      <h1 className="titulo-pagina">Próximos partidos</h1>
      <p className="titulo-sub">
        {nombreLiga(liga)} · elige la liga de arriba y cambia la voz del modelo —
        fecha y hora siempre en UTC.
      </p>

      <SelLiga activa={liga} modelo={modelo} />
      <SelModelo activo={modelo} liga={liga} />

      {partidos.length === 0 ? (
        <Aviso
          titulo="Nada por jugar de momento en esta liga."
          detalle={<p>Prueba otra liga o vuelve luego a la próxima jornada.</p>}
        />
      ) : (
        <>
          <p className="titulo-sub">
            <Leyenda1x2 />
            <span style={{ marginLeft: "0.9rem" }}>
              Mostrando la voz de {nombreModelo(modelo)} — cambia de voz arriba.
            </span>
          </p>
          <div className="lista-partidos">
            {partidos.map((f) => (
              <Fila
                key={f.partido_id_api}
                fixture={f}
                modelo={modelo}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function Fila({ fixture, modelo }: { fixture: Fixture; modelo: string }) {
  const pr = fixture.predicciones.find((p) => p.modelo === modelo);

  const favorito = pr
    ? mayorDe(
        pr.prob_local,
        pr.prob_empate,
        pr.prob_visita,
        fixture.local,
        fixture.visitante,
      )
    : null;

  return (
    <Link
      className="fila-partido"
      href={{ pathname: `/partido/${fixture.partido_id_api}` }}
    >
      <span className="cuando">
        <span className="num">{fechaDia(fixture.fecha_utc)}</span>
        <span className="num">{horaUtc(fixture.fecha_utc)}</span>
        {fixture.jornada && <span> · J{fixture.jornada}</span>}
      </span>
      <span className="quienes">
        <span className="rivalidad">
          {fixture.local}
          <span className="rival-vs">—</span>
          {fixture.visitante}
        </span>
        <Barra1x2
          pl={pr?.prob_local ?? null}
          px={pr?.prob_empate ?? null}
          pv={pr?.prob_visita ?? null}
        />
      </span>
      <span className="favorito num">
        {pr && favorito ? (
          <>
            <strong>{favorito.pct}</strong> {favorito.nombre}
          </>
        ) : (
          <span className="sin-prediccion">sin predicción aún</span>
        )}
      </span>
    </Link>
  );
}

function mayorDe(
  pl: number | null,
  px: number | null,
  pv: number | null,
  local: string,
  visitante: string,
): { pct: string; nombre: string } | null {
  if (pl === null || px === null || pv === null) return null;
  const triple: Array<[number, string]> = [
    [pl, local],
    [px, "empate"],
    [pv, visitante],
  ];
  const [v, nombre] = triple.reduce((a, b) => (b[0] > a[0] ? b : a));
  return { pct: pct(v), nombre };
}
