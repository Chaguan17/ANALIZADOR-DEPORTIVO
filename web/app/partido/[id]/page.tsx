import Link from "next/link";
import { Suspense } from "react";
import Aviso, { Cargando } from "@/components/Aviso";
import Barra1x2 from "@/components/Barra1x2";
import {
  numDe,
  obtenerCornes,
  obtenerPredicciones,
  obtenerTarjetas,
  obtenerTiros,
  type CornesPartido,
  type DatosExtra,
  type PrediccionesPartido,
  type TarjetaJugador,
  type TarjetasPartido,
  type TirosPartido,
  type TiradorJugador,
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

  // Sección ESPN (Fase 15): si la API falla la sección queda honestamente vacía.
  let tarjetas: TarjetasPartido | null = null;
  try {
    tarjetas = await obtenerTarjetas(idNum);
  } catch {
    tarjetas = null;
  }

  // Fase 16: tiros y cornes leen el MISMO summary ESPN (endpoints on-request).
  let tiros: TirosPartido | null = null;
  try {
    tiros = await obtenerTiros(idNum);
  } catch {
    tiros = null;
  }
  let cornes: CornesPartido | null = null;
  try {
    cornes = await obtenerCornes(idNum);
  } catch {
    cornes = null;
  }

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

      {tarjetas && <SeccionTarjetas t={tarjetas} />}
      {tiros && <SeccionTiros t={tiros} />}
      {cornes && <SeccionCornes t={cornes} />}
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

/* ────────────── Tarjetas (Fase 15) — fuente ESPN, on-request ────────────── */

function SeccionTarjetas({ t }: { t: TarjetasPartido }) {
  return (
    <section style={{ marginTop: "2.4rem" }}>
      <h2 className="titulo-bloque">Tarjetas{t.fuente ? " · ESPN" : ""}</h2>
      <p className="titulo-sub">
        Total del partido (amarillas + rojas) desde una Poisson con las tasas
        por equipo encogidas hacia la media de liga. Cobertura del dominio:
        {` ${t.cobertura.con_datos}/${t.cobertura.jugados}`} jugados con datos
        (el backfill avanza con el cron).
      </p>

      {t.prediccion && (
        <div className="tabla-scroll">
          <table className="tabla">
            <thead>
              <tr>
                <th>Predicción</th>
                <th className="num">Valor</th>
              </tr>
            </thead>
            <tbody>
              <tr className="fila-modelo">
                <td>Tarjetas esperadas (total)</td>
                <td className="num">{num(t.prediccion.tarjetas_esperadas)}</td>
              </tr>
              <tr>
                <td>Prob. over 2.5</td>
                <td className="num">{pct(t.prediccion.prob_over_2_5)}</td>
              </tr>
              <tr>
                <td>Prob. over 3.5</td>
                <td className="num">{pct(t.prediccion.prob_over_3_5)}</td>
              </tr>
              <tr className="diag">
                <td colSpan={2}>
                  por equipo — local: {num(t.prediccion.por_equipo.local ?? null)} ·
                  visitante: {num(t.prediccion.por_equipo.visitante ?? null)}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      )}

      {t.reales && (
        <div className="tabla-scroll" style={{ marginTop: "1rem" }}>
          <table className="tabla">
            <thead>
              <tr>
                <th>Real</th>
                <th className="num">Amarillas</th>
                <th className="num">Rojas</th>
              </tr>
            </thead>
            <tbody>
              <tr className="fila-modelo">
                <td>{t.local}</td>
                <td className="num">{t.reales.local.amarillas}</td>
                <td className="num">{t.reales.local.rojas}</td>
              </tr>
              <tr>
                <td>{t.visitante}</td>
                <td className="num">{t.reales.visitante.amarillas}</td>
                <td className="num">{t.reales.visitante.rojas}</td>
              </tr>
              <tr className="diag">
                <td colSpan={3}>
                  {filaDeTarjetas(t.reales.local, t.reales.visitante) ||
                    "sin eventos asignados a jugador"}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      )}

      {t.propensos && (
        <div className="tabla-scroll" style={{ marginTop: "1rem" }}>
          <table className="tabla">
            <thead>
              <tr>
                <th>Propenso (por aparición)</th>
                <th className="num">Tarjetas</th>
                <th className="num">Jugados</th>
                <th className="num">Tasa</th>
              </tr>
            </thead>
            <tbody>
              <LadoPropensos lado="local" titulo={t.local} filas={t.propensos.local} />
              <LadoPropensos lado="visitante" titulo={t.visitante} filas={t.propensos.visitante} />
            </tbody>
          </table>
        </div>
      )}

      {t.calidad.length > 0 && (
        <p className="titulo-sub" style={{ marginTop: "1rem" }}>
          Calidad walk-forward:{" "}
          {t.calidad
            .map(
              (c) =>
                `O/U ${c.linea}: ${c.aciertos}/${c.evaluados} (${pct(c.accuracy, 0)}) · MAE ${num(c.mae)}`,
            )
            .join(" · ")}
        </p>
      )}
      <p className="titulo-sub">
        notas: {t.notas.join(" · ")}
      </p>
    </section>
  );
}

function LadoPropensos({
  lado,
  titulo,
  filas,
}: {
  lado: string;
  titulo: string;
  filas: TarjetaJugador[];
}) {
  if (filas.length === 0) {
    return (
      <tr>
        <td colSpan={4}>{titulo}: sin jugadores medibles todavía</td>
      </tr>
    );
  }
  return (
    <>
      <tr className="diag">
        <td colSpan={4}>{lado === "local" ? "🏠" : "✈️"} {titulo}</td>
      </tr>
      {filas.map((f) => (
        <tr key={f.nombre}>
          <td>{f.nombre}</td>
          <td className="num">{f.amarillas}</td>
          <td className="num">{f.apariciones}</td>
          <td className="num">
            {f.tasa === null ? "—" : num(f.tasa)}
          </td>
        </tr>
      ))}
    </>
  );
}

function filaDeTarjetas(
  local: NonNullable<TarjetasPartido["reales"]>["local"],
  visitante: NonNullable<TarjetasPartido["reales"]>["visitante"],
): string {
  const eventos = [...local.por_jugador, ...visitante.por_jugador]
    .sort((a, b) => (a.minuto ?? 99) - (b.minuto ?? 99))
    .map(
      (e) => `${e.nombre} ${e.minuto != null ? `${e.minuto}'` : ""} (${e.tipo})`.trim(),
    );
  return eventos.join(" · ");
}

/* ────────────── Tiros (Fase 16) — el mismo summary ESPN, on-request ───────── */

function SeccionTiros({ t }: { t: TirosPartido }) {
  return (
    <section style={{ marginTop: "2.4rem" }}>
      <h2 className="titulo-bloque">Tiros{t.fuente ? " · ESPN" : ""}</h2>
      <p className="titulo-sub">
        Total del partido (tiros y a puerta) desde DOS Poisson con las tasas por
        equipo encogidas hacia la media de liga — cada evento tiene su propio λ.
        Cobertura del dominio:
        {` ${t.cobertura.con_datos}/${t.cobertura.jugados}`} jugados con datos
        (el backfill avanza con el cron).
      </p>

      {t.prediccion && (
        <div className="tabla-scroll">
          <table className="tabla">
            <thead>
              <tr>
                <th>Predicción</th>
                <th className="num">Valor</th>
              </tr>
            </thead>
            <tbody>
              <tr className="fila-modelo">
                <td>Tiros esperados (total)</td>
                <td className="num">{num(t.prediccion.tiros_esperados)}</td>
              </tr>
              <tr className="fila-modelo">
                <td>A puerta esperados</td>
                <td className="num">{num(t.prediccion.a_puerta_esperados)}</td>
              </tr>
              <tr>
                <td>Prob. over 23.5 (tiros)</td>
                <td className="num">{pct(t.prediccion.prob_over_23_5)}</td>
              </tr>
              <tr>
                <td>Prob. over 8.5 (a puerta)</td>
                <td className="num">{pct(t.prediccion.prob_a_puerta_over_8_5)}</td>
              </tr>
              <tr className="diag">
                <td colSpan={2}>
                  por equipo — local: tiros{" "}
                  {num(t.prediccion.por_equipo.local?.tiros ?? null)} · a puerta{" "}
                  {num(t.prediccion.por_equipo.local?.a_puerta ?? null)} ·
                  visitante: tiros{" "}
                  {num(t.prediccion.por_equipo.visitante?.tiros ?? null)} · a
                  puerta {num(t.prediccion.por_equipo.visitante?.a_puerta ?? null)}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      )}

      {t.reales && (
        <div className="tabla-scroll" style={{ marginTop: "1rem" }}>
          <table className="tabla">
            <thead>
              <tr>
                <th>Real</th>
                <th className="num">Tiros</th>
                <th className="num">A puerta</th>
              </tr>
            </thead>
            <tbody>
              <tr className="fila-modelo">
                <td>{t.local}</td>
                <td className="num">{t.reales.local.total}</td>
                <td className="num">{t.reales.local.a_puerta}</td>
              </tr>
              <tr>
                <td>{t.visitante}</td>
                <td className="num">{t.reales.visitante.total}</td>
                <td className="num">{t.reales.visitante.a_puerta}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}

      {t.tiradores && (
        <div className="tabla-scroll" style={{ marginTop: "1rem" }}>
          <table className="tabla">
            <thead>
              <tr>
                <th>Tirador (por aparición)</th>
                <th className="num">Tiros</th>
                <th className="num">Jugados</th>
                <th className="num">Tasa</th>
              </tr>
            </thead>
            <tbody>
              <LadoTiradores titulo={t.local} filas={t.tiradores.local} />
              <LadoTiradores titulo={t.visitante} filas={t.tiradores.visitante} />
            </tbody>
          </table>
        </div>
      )}

      {t.calidad.length > 0 && (
        <p className="titulo-sub" style={{ marginTop: "1rem" }}>
          Calidad walk-forward:{" "}
          {t.calidad
            .map(
              (c) =>
                `O/U ${c.linea}: ${c.aciertos}/${c.evaluados} (${pct(c.accuracy, 0)}) · MAE ${num(c.mae)}`,
            )
            .join(" · ")}
        </p>
      )}
      <p className="titulo-sub">notas: {t.notas.join(" · ")}</p>
    </section>
  );
}

/* ────────────── Cornes (Fase 16) — el mismo summary ESPN, on-request ──────── */

function SeccionCornes({ t }: { t: CornesPartido }) {
  return (
    <section style={{ marginTop: "2.4rem" }}>
      <h2 className="titulo-bloque">Cornes{t.fuente ? " · ESPN" : ""}</h2>
      <p className="titulo-sub">
        Total de saques de esquina del partido («wonCorners» de ESPN por equipo)
        desde una Poisson con las tasas por equipo encogidas. Cobertura del
        dominio: {` ${t.cobertura.con_datos}/${t.cobertura.jugados}`} jugados con
        datos (el backfill avanza con el cron).
      </p>

      {t.prediccion && (
        <div className="tabla-scroll">
          <table className="tabla">
            <thead>
              <tr>
                <th>Predicción</th>
                <th className="num">Valor</th>
              </tr>
            </thead>
            <tbody>
              <tr className="fila-modelo">
                <td>Cornes esperados (total)</td>
                <td className="num">{num(t.prediccion.cornes_esperados)}</td>
              </tr>
              <tr>
                <td>Prob. over 9.5</td>
                <td className="num">{pct(t.prediccion.prob_over_9_5)}</td>
              </tr>
              <tr>
                <td>Prob. over 11.5</td>
                <td className="num">{pct(t.prediccion.prob_over_11_5)}</td>
              </tr>
              <tr className="diag">
                <td colSpan={2}>
                  por equipo — local: {num(t.prediccion.por_equipo.local ?? null)} ·
                  visitante: {num(t.prediccion.por_equipo.visitante ?? null)}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      )}

      {t.reales && (
        <div className="tabla-scroll" style={{ marginTop: "1rem" }}>
          <table className="tabla">
            <thead>
              <tr>
                <th>Real</th>
                <th className="num">Cornes</th>
              </tr>
            </thead>
            <tbody>
              <tr className="fila-modelo">
                <td>{t.local}</td>
                <td className="num">{t.reales.local.total}</td>
              </tr>
              <tr>
                <td>{t.visitante}</td>
                <td className="num">{t.reales.visitante.total}</td>
              </tr>
              <tr className="diag">
                <td colSpan={2}>
                  total del partido: {t.reales.local.total + t.reales.visitante.total}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      )}

      {t.calidad.length > 0 && (
        <p className="titulo-sub" style={{ marginTop: "1rem" }}>
          Calidad walk-forward:{" "}
          {t.calidad
            .map(
              (c) =>
                `O/U ${c.linea}: ${c.aciertos}/${c.evaluados} (${pct(c.accuracy, 0)}) · MAE ${num(c.mae)}`,
            )
            .join(" · ")}
        </p>
      )}
      <p className="titulo-sub">notas: {t.notas.join(" · ")}</p>
    </section>
  );
}

function LadoTiradores({ titulo, filas }: { titulo: string; filas: TiradorJugador[] }) {
  if (filas.length === 0) {
    return (
      <tr>
        <td colSpan={4}>{titulo}: sin tiradores medibles todavía</td>
      </tr>
    );
  }
  return (
    <>
      <tr className="diag">
        <td colSpan={4}>{titulo}</td>
      </tr>
      {filas.map((f) => (
        <tr key={f.nombre}>
          <td>{f.nombre}</td>
          <td className="num">{f.tiros}</td>
          <td className="num">{f.apariciones}</td>
          <td className="num">{f.tasa === null ? "—" : num(f.tasa)}</td>
        </tr>
      ))}
    </>
  );
}
