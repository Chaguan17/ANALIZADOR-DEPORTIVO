// Diccionarios de dominio (español) y formateadores.

export const LIGAS = [
  { codigo: "PD", nombre: "LaLiga" },
  { codigo: "PL", nombre: "Premier League" },
  { codigo: "SA", nombre: "Serie A" },
  { codigo: "BL1", nombre: "Bundesliga" },
  { codigo: "CL", nombre: "Champions League" },
] as const;

export type LigaCodigo = (typeof LIGAS)[number]["codigo"];

export function nombreLiga(codigo: string): string {
  return LIGAS.find((l) => l.codigo === codigo)?.nombre ?? codigo;
}

export function esLigaValida(
  codigo: string | string[] | undefined,
): codigo is string {
  if (typeof codigo !== "string") return false;
  return LIGAS.some((l) => l.codigo === codigo);
}

// Las tres voces del proyecto, en el orden en que nacieron.
// Un color por voz — se repite en toda la interfaz.
export const MODELOS = [
  { id: "poisson_doble", nombre: "Poisson", nota: "estructura de goles" },
  {
    id: "poisson_dc",
    nombre: "Dixon-Coles",
    nota: "poisson + τ en marcadores bajos",
  },
  {
    id: "lightgbm_v1",
    nombre: "LightGBM",
    nota: "árboles · mezcla con la uniforme",
  },
] as const;

export function nombreModelo(id: string): string {
  return MODELOS.find((m) => m.id === id)?.nombre ?? id;
}

export function esModeloValido(
  id: string | string[] | undefined,
): id is string {
  if (typeof id !== "string") return false;
  return MODELOS.some((m) => m.id === id);
}

const DIAS = ["DOM", "LUN", "MAR", "MIÉ", "JUE", "VIE", "SÁB"];
const MESES = [
  "ENE", "FEB", "MAR", "ABR", "MAY", "JUN",
  "JUL", "AGO", "SEP", "OCT", "NOV", "DIC",
];

/** "23 OCT · 21:30" (horario UTC siempre marcado aparte para no mentir). */
export function fechaCorta(iso: string): string {
  const d = new Date(iso);
  const hh = String(d.getUTCHours()).padStart(2, "0");
  const mm = String(d.getUTCMinutes()).padStart(2, "0");
  return `${d.getUTCDate()} ${MESES[d.getUTCMonth()]} · ${hh}:${mm}`;
}

/** "VIE 24 OCT" para filas compactas. */
export function fechaDia(iso: string): string {
  const d = new Date(iso);
  return `${DIAS[d.getUTCDay()]} ${d.getUTCDate()} ${MESES[d.getUTCMonth()]}`;
}

/** "21:30 Z" — la Z recuerda que es hora UTC. */
export function horaUtc(iso: string): string {
  const d = new Date(iso);
  const hh = String(d.getUTCHours()).padStart(2, "0");
  const mm = String(d.getUTCMinutes()).padStart(2, "0");
  return `${hh}:${mm} UTC`;
}

/** null-robusto: "55.4%" o "—" cuando el modelo no emite esa salida. */
export function pct(valor: number | null | undefined, dec = 1): string {
  if (valor === null || valor === undefined) return "—";
  return `${(100 * valor).toFixed(dec)}%`;
}

export function num(valor: number | null | undefined, dec = 2): string {
  if (valor === null || valor === undefined) return "—";
  return valor.toFixed(dec);
}
