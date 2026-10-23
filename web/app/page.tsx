import Link from "next/link";
import { Suspense } from "react";
import SkeletonPartidos from "@/components/SkeletonPartidos";
import { SelLiga } from "@/components/Selectores";
import { obtenerFixtures, type Fixture } from "@/lib/api";
import {
  escenario,
  letraDe,
  pctDe,
  type Escenario,
} from "@/lib/escenario";
import {
  MODELOS,
  esLigaValida,
  fechaDia,
  horaUtc,
  nombreLiga,
  nombreModelo,
  num,
  pct,
} from "@/lib/formato";

export const metadata = { title: "Próximos partidos" };

const SIGLAS: Record<string, string> = {
  poisson_doble: "pd",
  poisson_dc: "dc",
  lightgbm_v1: "lgbm",
};

export default function Pagina(props: PageProps<"/">) {
  return (
    <Suspense fallback={<SkeletonPartidos />}>
      <Contenido {...props} />
    </Suspense>
  );
}

async function Contenido({ searchParams }: PageProps<"/">) {
  const { liga: pLiga } = await searchParams;
  const liga = esLigaValida(pLiga) ? pLiga : "PD";

  let partidos: Fixture[];
  try {
    partidos = await obtenerFixtures(liga);
  } catch (e) {
    return (
      <div className="noche">
        <div className="contenedor">
          <Hero liga={liga} />
          <div className="n-estado n-estado-error" role="alert">
            <strong>Sin cartel: la web no pudo hablar con la API.</strong>
            <p className="n-estado-detalle">
              Si la API está dormida, despiértala con{" "}
              <code>.venv\Scripts\python -m backend.app.api</code>
              <span className="num"> ({String(e)})</span>
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="noche">
      <div className="contenedor">
        <Hero liga={liga} />
        <SelLiga activa={liga} />
        <Leyenda />
        {partidos.length === 0 ? (
          <div className="n-estado">
            <strong>La pizarra está en blanco.</strong>
            <p className="n-estado-detalle">
              Ningún partido de {nombreLiga(liga)} está programado para jugarse
              todavía. El cron repuebla la pizarra cada 6 horas: vuelve luego o
              elige otra liga.
            </p>
          </div>
        ) : (
          <div className="n-parrilla">
            {partidos.map((f) => (
              <Boletin key={f.partido_id_api} fixture={f} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/** Cartel: la liga como kicker sobre el titular. */
function Hero({ liga }: { liga: string }) {
  return (
    <header className="n-hero">
      <p className="n-kicker num">{nombreLiga(liga)}</p>
      <h1 className="n-cartel">Próximos partidos</h1>
      <p className="n-hero-sub">
        El partido manda: cada boletín abre con su escenario — una frase y una
        cifra — y una barra de consenso 1/X/2. Las tres voces firmantes quedan
        plegadas en «Las tres voces», a un clic de quien quiera el detalle.
        Fechas y horas en UTC.
      </p>
    </header>
  );
}

/** Clave de lectura: qué es la barra única y dónde viven las voces. */
function Leyenda() {
  return (
    <p className="n-leyenda">
      <span className="n-muestra" aria-hidden="true">
        <b className="n-seg-1" />
        <b className="n-seg-x" />
        <b className="n-seg-2" />
      </span>
      La barra es el consenso (promedio de las voces): 1 local, X empate, 2
      visita. Dentro de «Las tres voces» están las barras y firmas de cada
      modelo; el oro se reserva a la cifra del escenario.
    </p>
  );
}

/** Un boletín = un partido: escenario héroe, consenso y voces plegadas. */
function Boletin({ fixture }: { fixture: Fixture }) {
  const esc = escenario(fixture);

  const porModelo = new Map(fixture.predicciones.map((p) => [p.modelo, p]));
  const voces = MODELOS.map((m) => {
    const pr = porModelo.get(m.id);
    return { m, pr, letra: letraDe(pr) };
  });
  const firmas = voces.filter((v) => v.letra !== null);
  const unanime = firmas.length >= 2 && new Set(firmas.map((v) => v.letra)).size === 1;

  const selloAria =
    firmas.length === 0
      ? "Sello sin firmas: pronóstico pendiente"
      : `Sello de firmas: ${firmas
          .map((v) => `${nombreModelo(v.m.id)} firma ${v.letra}`)
          .join(", ")}${unanime ? " (unánime)" : esc.dividido ? " (dividido)" : ""}`;

  return (
    <article className="n-boletin">
      <Link
        className="n-boletin-cuerpo"
        href={`/partido/${fixture.partido_id_api}`}
      >
        <p className="n-boletin-meta num">
          <span>{fechaDia(fixture.fecha_utc)}</span>
          <span>{horaUtc(fixture.fecha_utc)}</span>
          {fixture.jornada && <span>J{fixture.jornada}</span>}
        </p>
        <h2 className="n-boletin-matchup">
          {fixture.local}
          <span>{fixture.visitante}</span>
        </h2>
        <p className={`n-rec${esc.tono === "pendiente" ? " n-rec-pendiente" : ""}`}>
          {esc.frase}
          {esc.clave && <b className="num n-rec-clave">{esc.clave}</b>}
        </p>
        <Consenso consenso={esc.consenso} />
        <Chips esc={esc} />
      </Link>

      <details className="n-voces-detalle">
        <summary>
          <span className="n-voces-rotulo">Las tres voces</span>
          {unanime && <b className="num n-voces-unanime">unánime</b>}
          {esc.dividido && (
            <span
              className="n-voces-divergencia"
              title="Las voces no coinciden en el resultado"
              aria-label="Con divergencia: las voces no coinciden en el resultado"
            />
          )}
        </summary>
        <div className="n-voces">
          {voces.map(({ m, pr }) => (
            <VozFila key={m.id} modeloId={m.id} nombre={m.nombre} nota={m.nota} pr={pr} />
          ))}
        </div>
        <p className="n-sello" role="group" aria-label={selloAria}>
          {firmas.length === 0 ? (
            <span className="n-sello-vacio">sin firmas todavía</span>
          ) : (
            voces.map(({ m, pr, letra }) => (
              <span
                key={m.id}
                className={`n-firma voz-${m.id}${letra === null ? " n-firma-vacia" : ""}`}
                title={m.nota}
              >
                <span className="punto-voz" aria-hidden="true" />
                <span className="n-firma-sigla">{SIGLAS[m.id] ?? m.id}</span>
                <b className="num">{letra ?? "—"}</b>
                {letra !== null && pr ? (
                  <span className="num n-firma-pct">{pct(pctDe(pr, letra))}</span>
                ) : null}
              </span>
            ))
          )}
        </p>
      </details>
    </article>
  );
}

/** El número del escenario en el chasis de la tarjeta. */
function Chips({ esc }: { esc: Escenario }) {
  if (esc.lambdaGoles === null && !esc.marcador) return null;
  return (
    <p className="n-chips num">
      {esc.lambdaGoles !== null && (
        <span className="n-chip-mini">λ {num(esc.lambdaGoles, 1)} goles</span>
      )}
      {esc.marcador && <span className="n-chip-mini">marcador {esc.marcador}</span>}
    </p>
  );
}

/** UNA barra de consenso: promedio simple de las voces que emiten. */
function Consenso({ consenso }: { consenso: Escenario["consenso"] }) {
  if (!consenso) return null;
  return (
    <div className="n-consenso">
      <span className="n-consenso-label num">consenso</span>
      <span
        className="n-barra"
        role="img"
        aria-label={`Consenso de las voces: local ${pct(consenso.p1, 0)}, empate ${pct(consenso.px, 0)}, visita ${pct(consenso.p2, 0)}`}
      >
        <b className="n-seg-1" style={{ width: `${100 * consenso.p1}%` }} />
        <b className="n-seg-x" style={{ width: `${100 * consenso.px}%` }} />
        <b className="n-seg-2" style={{ width: `${100 * consenso.p2}%` }} />
      </span>
    </div>
  );
}

/** Una fila-voz: sigla + barra apilada 1|X|2 (tonos de tiza, no color). */
function VozFila({
  modeloId,
  nombre,
  nota,
  pr,
}: {
  modeloId: string;
  nombre: string;
  nota: string;
  pr: Fixture["predicciones"][number] | undefined;
}) {
  const pl = pr?.prob_local ?? null;
  const px = pr?.prob_empate ?? null;
  const pv = pr?.prob_visita ?? null;
  const suma = (pl ?? 0) + (px ?? 0) + (pv ?? 0);
  const completa = suma > 0 && pl !== null && px !== null && pv !== null;

  return (
    <div className={`n-voz voz-${modeloId}`}>
      <span className="n-voz-sigla" title={nota}>
        <span className="punto-voz" aria-hidden="true" />
        {SIGLAS[modeloId] ?? modeloId}
      </span>
      {completa ? (
        <span
          className="n-barra"
          role="img"
          aria-label={`${nombre}: local ${pct(pl)}, empate ${pct(px)}, visita ${pct(pv)}`}
        >
          <b className="n-seg-1" style={{ width: `${100 * (pl / suma)}%` }} />
          <b className="n-seg-x" style={{ width: `${100 * (px / suma)}%` }} />
          <b className="n-seg-2" style={{ width: `${100 * (pv / suma)}%` }} />
        </span>
      ) : (
        <span
          className="n-barra n-barra-vacia"
          role="img"
          aria-label={`${nombre}: aún sin probabilidades`}
        />
      )}
    </div>
  );
}
