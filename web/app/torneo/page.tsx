import Link from "next/link";
import { Suspense } from "react";
import Aviso, { Cargando } from "@/components/Aviso";
import { obtenerTorneo, type TorneoModelo } from "@/lib/api";
import { LIGAS, fechaDia, nombreModelo, num, pct } from "@/lib/formato";

export const metadata = { title: "Torneo" };

// Escala de las barritas de tasa: la barra arranca en 20% (tasas menores
// apenas merecen marca) y termina en 100%.
const TASA_MIN = 0.2;

// Escala fija de las barritas de log loss (la uniforme 1.0986).
const LL_MIN = 0.95;
const LL_MAX = 1.2;

const ETIQUETA = { local: "1", empate: "X", visita: "2" } as const;

export default function Pagina() {
  return (
    <Suspense fallback={<Cargando />}>
      <Contenido />
    </Suspense>
  );
}

async function Contenido() {
  let torneo: TorneoModelo[];
  try {
    torneo = await obtenerTorneo();
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

  if (!torneo.length) {
    return (
      <div className="contenedor">
        <Aviso
          titulo="Aún no hay torneo: nadie ha confirmado su primer acierto."
          detalle={
            <p>
              La tabla se arma con las evaluaciones que el cron refresca en cada
              corrida. Corre una con <code>python -m backend.app.evaluacion
              --todas --guardar</code> y esta página vivirá.
            </p>
          }
        />
      </div>
    );
  }

  // El campeón de cada liga (mayor tasa 1X2; empate → voz que nació antes).
  const celda = new Map<string, number>(); // modelo|liga → tasa
  for (const t of torneo) {
    for (const l of t.por_liga) {
      if (l.accuracy != null) celda.set(`${t.modelo}|${l.liga}`, l.accuracy);
    }
  }
  const campeonPorLiga = new Map<string, string>();
  for (const l of LIGAS) {
    let mejor = "";
    let mejorTasa = -1;
    for (const t of torneo) {
      const tasa = celda.get(`${t.modelo}|${l.codigo}`);
      if (tasa != null && tasa > mejorTasa) {
        mejorTasa = tasa;
        mejor = t.modelo;
      }
    }
    if (mejor) campeonPorLiga.set(l.codigo, mejor);
  }

  return (
    <div className="contenedor">
      <h1 className="titulo-pagina">Torneo de los modelos</h1>
      <p className="titulo-sub">
        La clasificación de temporada de las tres voces, contada como la
        miraría un hincha: <b>quién va arriba</b> y <b>cómo viene de forma</b>.
        Cuando el cron confirma resultados, esta tabla se recuenta sola — la
        misma evaluación walk-forward que vive en la sección de{" "}
        <Link href="/precision">precisión</Link>, leída aquí como tabla de
        posiciones.
      </p>

      <h2 className="titulo-bloque">Tabla del torneo (1X2)</h2>
      <div className="tabla-scroll">
        <table className="tabla">
          <thead>
            <tr>
              <th>Pos</th>
              <th>Voz</th>
              <th className="num">Aciertos</th>
              <th className="num">Tasa</th>
              <th className="num">Log loss</th>
              <th className="num">Brier</th>
              <th className="num">O2.5</th>
            </tr>
          </thead>
          <tbody>
            {torneo.map((t, i) => (
              <tr key={t.modelo}>
                <td className="num torneo-pos">{i + 1}º</td>
                <td>
                  <span className="punto-voz" style={{ background: colorDe(t.modelo) }} />{" "}
                  <strong>{nombreModelo(t.modelo)}</strong>
                </td>
                <td className="num">
                  <strong>{t.aciertos}</strong>
                  <span className="diag"> / {t.evaluados}</span>
                </td>
                <td className="num">
                  <strong>{pct(t.accuracy)}</strong>
                  <Barra parte={tasaAParte(t.accuracy)} color={colorDe(t.modelo)} />
                </td>
                <td className="num">
                  {t.log_loss != null ? (
                    <>
                      <strong>{num(t.log_loss, 4)}</strong>
                      <BarraLL valor={t.log_loss} color={colorDe(t.modelo)} />
                    </>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="num">{num(t.brier, 4)}</td>
                <td className="num">
                  {t.o25 ? (
                    <>
                      {pct(t.o25.accuracy)}
                      <span className="diag"> · n {t.o25.evaluados}</span>
                    </>
                  ) : (
                    "—"
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="titulo-sub">
        Tasa = el favorito predicho terminó siendo el resultado. O2.5 se cuenta
        SOLO en las filas donde la voz emite esa probabilidad: LightGBM v1 no
        la emite (su salida honesta es 1X2 mezclada con la uniforme); por eso
        su celda dice «—» en vez de inventar un número.
      </p>

      <h2 className="titulo-bloque">¿Quién manda en cada liga?</h2>
      <div className="tabla-scroll">
        <table className="tabla">
          <thead>
            <tr>
              <th>Liga</th>
              {torneo.map((t) => (
                <th key={t.modelo} className="num">
                  {nombreModelo(t.modelo)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {LIGAS.map((l) => (
              <tr key={l.codigo}>
                <td>{l.nombre}</td>
                {torneo.map((t) => {
                  const fila = t.por_liga.find((x) => x.liga === l.codigo);
                  const esCampeon = campeonPorLiga.get(l.codigo) === t.modelo;
                  return (
                    <td
                      key={t.modelo}
                      className="num"
                      style={
                        esCampeon
                          ? { boxShadow: `inset 3px 0 0 ${colorDe(t.modelo)}` }
                          : undefined
                      }
                    >
                      {fila?.accuracy != null ? (
                        <>
                          {pct(fila.accuracy)}
                          <span className="diag"> · n {fila.evaluados}</span>
                        </>
                      ) : (
                        "—"
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 className="titulo-bloque">Forma viva (últimos partidos confirmados)</h2>
      <p className="titulo-sub">
        Como la forma de un equipo en la tabla de posiciones: los últimos
        partidos que cada voz pronosticó mientras estaban por jugarse — ahora
        que el resultado existe, se cuentan los ✓ y ✗.
      </p>
      <div className="torneo-bloque-formas">
        {torneo.map((t) => (
          <section key={t.modelo} className="torneo-forma">
            <h3>
              <span className="punto-voz" style={{ background: colorDe(t.modelo) }} />{" "}
              {nombreModelo(t.modelo)}
            </h3>
            {t.forma.length === 0 ? (
              <p className="diag">Aún sin partidos confirmados para esta voz.</p>
            ) : (
              <div className="forma-celdas" style={{ marginBottom: "0.7rem" }}>
                {t.forma.map((f) => (
                  <span
                    key={`chipo-${f.partido_id_api}`}
                    className={`forma-c ${f.acierto_1x2 ? "f-acierto" : "f-falla"}`}
                    title={`${f.local} ${f.goles_local}-${f.goles_visitante} ${f.visitante}`}
                  >
                    {f.acierto_1x2 ? "✓" : "✗"}
                  </span>
                ))}
              </div>
            )}
            <ul className="torneo-forma-lista">
              {t.forma.map((f) => (
                <li key={f.partido_id_api}>
                  <Link href={`/partido/${f.partido_id_api}`}>
                    <span className="torneo-fecha" style={{ color: "var(--tinta-2)" }}>
                      {fechaDia(f.fecha_utc)}
                    </span>{" "}
                    <span className="resultado-eq">
                      {f.goles_local}-{f.goles_visitante}
                    </span>{" "}
                    {f.local} — {f.visitante}
                  </Link>
                  {" "}· elegí {" "}
                  <strong>{ETIQUETA[f.elegido as keyof typeof ETIQUETA] ?? f.elegido}</strong>
                  {" → "}
                  <strong className={f.acierto_1x2 ? "res-gano" : "res-perdio"}>
                    {f.acierto_1x2 ? "acierto" : "fallo"}
                  </strong>{" "}
                  <span className="diag" style={{ color: "var(--tinta-2)" }}>
                    (ll {num(f.log_loss_prediccion, 2)})
                  </span>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>

      <p className="titulo-sub" style={{ marginTop: "1.6rem" }}>
        Nota honesta: esta tabla y la de <Link href="/precision">precisión</Link>{" "}
        leen el mismo ledger (cada fila es un partido ya jugado, evaluado sin
        trampas walk-forward por el cron), pero LightGBM compite con menos
        partidos por su calentamiento reforzado, y las tasas por liga
        respetan esa diferencia. El torneo crece solo: cada 6 horas el cron
        vuelve a contar.
      </p>
    </div>
  );
}

/** Tasa → parte de barra (0–1) con la escala que arranca en TASA_MIN. */
function tasaAParte(accuracy: number | null): number | null {
  if (accuracy === null) return null;
  return Math.max(0, (accuracy - TASA_MIN) / (1 - TASA_MIN));
}

/** Barrita de tasa ya normalizada. */
function Barra({ parte, color }: { parte: number | null; color: string }) {
  if (parte === null) return null;
  const ancho = Math.max(3, Math.min(100, parte * 100));
  return (
    <>
      <br />
      <span aria-hidden="true" style={{ display: "inline-block", width: "3.2rem", height: "0.35rem", background: `linear-gradient(90deg, ${color} ${ancho}%, var(--linea) ${ancho}%)`, borderRadius: 3 }} />
    </>
  );
}

/** Barrita de log loss: 0.95 (élite) → 1.20 (peor que el azar). */
function BarraLL({ valor, color }: { valor: number; color: string }) {
  const ancho = Math.max(4, Math.min(100, ((valor - LL_MIN) / (LL_MAX - LL_MIN)) * 100));
  return (
    <>
      <br />
      <span aria-hidden="true" style={{ display: "inline-block", width: "3.2rem", height: "0.35rem", background: `linear-gradient(90deg, ${color} ${ancho}%, var(--linea) ${ancho}%)`, borderRadius: 3 }} />
    </>
  );
}

function colorDe(modelo: string): string {
  if (modelo === "poisson_doble") return "var(--voz-poisson-doble)";
  if (modelo === "poisson_dc") return "var(--voz-poisson-dc)";
  return "var(--voz-lightgbm-v1)";
}
