import Link from "next/link";
import { Suspense } from "react";
import SkeletonPartidos from "@/components/SkeletonPartidos";
import { SelLiga } from "@/components/Selectores";
import {
  obtenerFixtures,
  type Fixture,
  type PrediccionResumen,
} from "@/lib/api";
import {
  MODELOS,
  esLigaValida,
  fechaDia,
  horaUtc,
  nombreLiga,
  nombreModelo,
  pct,
} from "@/lib/formato";

export const metadata = { title: "Próximos partidos" };

type Letra = "1" | "X" | "2";

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
        {nombreModelo("poisson_doble")}, {nombreModelo("poisson_dc")} y{" "}
        {nombreModelo("lightgbm_v1")} firman su pronóstico sobre cada partido.
        Cuando las tres firmas apuntan al mismo resultado, el sello se enciende
        en oro: una sola voz. Fechas y horas en UTC.
      </p>
    </header>
  );
}

/** Clave de lectura: qué significa cada segmento y qué conquista el oro. */
function Leyenda() {
  return (
    <p className="n-leyenda">
      <span className="n-muestra" aria-hidden="true">
        <b className="n-seg-1" />
        <b className="n-seg-x" />
        <b className="n-seg-2" />
      </span>
      Barras por voz: 1 local, X empate, 2 visita. El sello firma la apuesta de
      cada voz con su probabilidad; oro cuando es unánime.
    </p>
  );
}

/** Un boletín = un partido con las tres voces compitiendo sobre él. */
function Boletin({ fixture }: { fixture: Fixture }) {
  const porModelo = new Map(fixture.predicciones.map((p) => [p.modelo, p]));

  const voces = MODELOS.map((m) => {
    const pr = porModelo.get(m.id);
    return { m, pr, letra: letraDe(pr) };
  });

  const firmas = voces.filter((v) => v.letra !== null);
  const letras = new Set(firmas.map((v) => v.letra));
  const unanime = firmas.length >= 2 && letras.size === 1;
  const dividido = firmas.length >= 2 && letras.size > 1;

  const selloAria =
    firmas.length === 0
      ? "Sello sin firmas: pronóstico pendiente"
      : `Sello de firmas: ${firmas
          .map((v) => `${nombreModelo(v.m.id)} firma ${v.letra}`)
          .join(", ")}${unanime ? " (unánime)" : dividido ? " (dividido)" : ""}`;

  return (
    <Link className="n-boletin" href={`/partido/${fixture.partido_id_api}`}>
      <p className="n-boletin-meta num">
        <span>{fechaDia(fixture.fecha_utc)}</span>
        <span>{horaUtc(fixture.fecha_utc)}</span>
        {fixture.jornada && <span>J{fixture.jornada}</span>}
      </p>
      <h2 className="n-boletin-matchup">
        {fixture.local}
        <span>{fixture.visitante}</span>
      </h2>
      <div className="n-voces">
        {voces.map(({ m, pr }) => (
          <VozFila key={m.id} modeloId={m.id} nombre={m.nombre} nota={m.nota} pr={pr} />
        ))}
      </div>
      <p
        className={`n-sello${unanime ? " n-sello-unanime" : ""}${
          dividido ? " n-sello-dividido" : ""
        }`}
        role="group"
        aria-label={selloAria}
      >
        {firmas.length === 0 ? (
          <span className="n-sello-vacio">pronóstico pendiente</span>
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
    </Link>
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
  pr: PrediccionResumen | undefined;
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

/** La letra que firma una voz (null = aún no puede prometer nada). */
function letraDe(pr: PrediccionResumen | undefined): Letra | null {
  if (!pr) return null;
  if (pr.prob_local === null || pr.prob_empate === null || pr.prob_visita === null) {
    return null;
  }
  const triple: Array<[number, Letra]> = [
    [pr.prob_local, "1"],
    [pr.prob_empate, "X"],
    [pr.prob_visita, "2"],
  ];
  return triple.reduce((a, b) => (b[0] > a[0] ? b : a))[1];
}

/** La probabilidad que respalda la letra firmada. */
function pctDe(pr: PrediccionResumen, letra: Letra): number | null {
  if (letra === "1") return pr.prob_local;
  if (letra === "X") return pr.prob_empate;
  return pr.prob_visita;
}
