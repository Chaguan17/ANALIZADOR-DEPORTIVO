import Link from "next/link";
import { Suspense } from "react";
import Aviso, { Cargando } from "@/components/Aviso";
import { obtenerPrecision, type MetricasModelo } from "@/lib/api";
import { LIGAS, nombreModelo, num, pct } from "@/lib/formato";

export const metadata = { title: "Precisión" };

// Escala fija de las barras de log loss (más corto = mejor; la uniforme 1.0986)
const LL_MIN = 0.95;
const LL_MAX = 1.2;

type Celda = {
  n: number;
  accuracy: number | null;
  log_loss: number | null;
  brier: number | null;
};

export default function Pagina() {
  return (
    <Suspense fallback={<Cargando />}>
      <Contenido />
    </Suspense>
  );
}

async function Contenido() {
  let metricas: MetricasModelo[];
  try {
    metricas = await obtenerPrecision();
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

  const celdas = new Map<string, Celda>();
  for (const m of metricas) {
    if (!m.liga) continue;
    celdas.set(`${m.modelo}|${m.liga}`, {
      n: m.evaluados,
      accuracy: m.accuracy,
      log_loss: m.log_loss,
      brier: m.brier,
    });
  }

  const modelos = [...new Set(metricas.map((m) => m.modelo))];

  // El mejor log loss de cada liga: merece el subrayado de su voz.
  const mejorPorLiga = new Map<string, string>();
  for (const l of LIGAS) {
    let mejor = "";
    let mejorLl = Infinity;
    for (const mo of modelos) {
      const ll = celdas.get(`${mo}|${l.codigo}`)?.log_loss;
      if (ll != null && ll < mejorLl) {
        mejorLl = ll;
        mejor = mo;
      }
    }
    if (mejor) mejorPorLiga.set(l.codigo, mejor);
  }

  return (
    <div className="contenedor">
      <h1 className="titulo-pagina">Precisión honesta</h1>
      <p className="titulo-sub">
        Cada pronóstico se compara con el resultado cuando este ya existe, sin
        volver a entrenar con el futuro (walk-forward). <b>Log loss</b> es la
        métrica reina: castiga la confianza desmedida y premia la calibración.
        Menor es mejor; cayendo por debajo de 1.0986 (la barra uniforme de
        puro azar 1X2) un modelo aporta información real.
      </p>

      <h2 className="titulo-bloque">Log loss (menor = mejor)</h2>
      <div className="tabla-scroll">
        <table className="tabla">
          <thead>
            <tr>
              <th>Modelo</th>
              {LIGAS.map((l) => (
                <th key={l.codigo} className="num">
                  {l.nombre}
                </th>
              ))}
              <th className="num">Total*</th>
            </tr>
          </thead>
          <tbody>
            {modelos.map((mo) => (
              <tr key={mo}>
                <td>
                  <span className="punto-voz" style={{ background: setColor(mo) }} />{" "}
                  {nombreModelo(mo)}
                </td>
                {LIGAS.map((l) => {
                  const c = celdas.get(`${mo}|${l.codigo}`);
                  const esMejor = mejorPorLiga.get(l.codigo) === mo;
                  return (
                    <td
                      key={l.codigo}
                      className="num"
                      style={
                        esMejor
                          ? { boxShadow: `inset 3px 0 0 ${setColor(mo)}` }
                          : undefined
                      }
                    >
                      {c?.log_loss != null ? (
                        <>
                          <strong>{num(c.log_loss, 4)}</strong>
                          {ness(c.log_loss)}
                        </>
                      ) : (
                        "—"
                      )}
                    </td>
                  );
                })}
                <td className="num">
                  {total(mo, celdas).ll != null ? (
                    <strong>{num(total(mo, celdas).ll!, 4)}</strong>
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
        La marca de color a la izquierda es el campeón de esa liga.* Total =
        promedio ponderado por n evaluados.
      </p>

      <h2 className="titulo-bloque">Acierto del favorito (1X2)</h2>
      <div className="tabla-scroll">
        <table className="tabla">
          <thead>
            <tr>
              <th>Modelo</th>
              {LIGAS.map((l) => (
                <th key={l.codigo} className="num">
                  {l.nombre}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {modelos.map((mo) => (
              <tr key={mo}>
                <td>
                  <span className="punto-voz" style={{ background: setColor(mo) }} />{" "}
                  {nombreModelo(mo)}
                </td>
                {LIGAS.map((l) => {
                  const c = celdas.get(`${mo}|${l.codigo}`);
                  return (
                    <td key={l.codigo} className="num">
                      {c ? (
                        <>
                          {pct(c.accuracy)}
                          <span className="diag"> · n {c.n}</span>
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

      <p className="titulo-sub" style={{ marginTop: "1.4rem" }}>
        Nota honesta: los 3 modelos compiten por las mismas ligas y guardan una
        fila por partido (UNIQUE partido+modelo), pero <b>no</b> sobre el mismo
        set: LightGBM evalúa menos partidos porque su calentamiento exige las 3
        clases presentes (46 partidos saltados vs 14 del baseline), y sus
        probabilidades llevan una mezcla con la uniforme por liga. Los 3
        esperan al próximo resultado para seguir la conversación…
        <Link href="/"> y tú puedes mirar sus últimas voces en los partidos
        vivos</Link>.
      </p>
    </div>
  );
}

/** Mini barrita bajo el log loss: posición del número en la escala 0.95–1.20. */
function ness(ll: number) {
  const ancho = Math.max(4, Math.min(100, ((ll - LL_MIN) / (LL_MAX - LL_MIN)) * 100));
  return (
    <>
      <br />
      <span
        aria-hidden="true"
        style={{
          display: "inline-block",
          width: "3.2rem",
          height: "0.35rem",
          background: "linear-gradient(90deg, var(--c-1) " + ancho + "%, var(--linea) " + ancho + "%)",
          borderRadius: 3,
        }}
      />
    </>
  );
}

function total(modelo: string, celdas: Map<string, Celda>): { ll: number | null } {
  let suma = 0;
  let n = 0;
  for (const l of LIGAS) {
    const c = celdas.get(`${modelo}|${l.codigo}`);
    if (c?.log_loss != null) {
      suma += c.log_loss * c.n;
      n += c.n;
    }
  }
  return { ll: n > 0 ? suma / n : null };
}

function setColor(modelo: string): string {
  if (modelo === "poisson_doble") return "var(--voz-poisson-doble)";
  if (modelo === "poisson_dc") return "var(--voz-poisson-dc)";
  return "var(--voz-lightgbm-v1)";
}
