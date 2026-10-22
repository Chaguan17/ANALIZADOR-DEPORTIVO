// Contratos 1:1 con backend/app/api.py (Fase 8) — mismos nombres de campos.
// La web NUNCA toca la BD directo: toda la verdad baja por la API.

const POR_DEFECTO = "http://127.0.0.1:8000";

// El navegador debe reach http://localhost:8000 (el puerto mapeado);
// el servidor puede usar un host interno (en docker: http://api:8000).
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? POR_DEFECTO;

function origen(): string {
  if (typeof window !== "undefined") return API_URL;
  return process.env.API_URL_SERVIDOR ?? API_URL;
}

export interface PrediccionResumen {
  modelo: string;
  prob_local: number | null;
  prob_empate: number | null;
  prob_visita: number | null;
  lam_local: number | null;
  lam_visita: number | null;
  marcador_estimado: string | null;
  prob_over25: number | null;
  prob_under25: number | null;
}

// JSONB libre (rho de DC, mezcla_uniforme de LGBM, ids de equipos, ...)
export type DatosExtra = Record<string, unknown>;

export interface PrediccionDetalle extends PrediccionResumen {
  datos: DatosExtra | null;
}

export interface PartidosInfo {
  partido_id_api: number;
  liga: string;
  temporada: number;
  fecha_utc: string;
  estado: string;
  jornada: number | null;
  local: string;
  visitante: string;
}

export interface Fixture extends PartidosInfo {
  predicciones: PrediccionResumen[];
}

export interface PrediccionesPartido extends PartidosInfo {
  predicciones: PrediccionDetalle[];
}

export interface ResultadoReciente extends PartidosInfo {
  goles_local: number | null;
  goles_visitante: number | null;
}

export interface ClasificacionFila {
  liga: string;
  temporada: number;
  posicion: number;
  equipo_id_api: number;
  equipo: string;
  jugados: number;
  ganados: number;
  empatados: number;
  perdidos: number;
  goles_favor: number;
  goles_contra: number;
  diferencia_goles: number;
  puntos: number;
  forma: string | null;
}

export interface EquipoDetalle {
  equipo_id_api: number;
  nombre: string;
  nombre_corto: string | null;
  tla: string | null;
  fundacion: number | null;
  escudo_url: string | null;
  clasificacion: ClasificacionFila | null;
  ultimos5: ResultadoReciente[];
  proximos3: Fixture[];
}

export interface JugadorDetalle {
  jugador_id_api: number;
  nombre: string;
  fecha_nac: string | null;
  nacionalidad: string | null;
  posicion: string | null;
  equipo_id_api: number | null;
  equipo: string | null;
  nota: string;
}

export interface MetricasModelo {
  modelo: string;
  liga: string | null;
  evaluados: number;
  accuracy: number | null;
  log_loss: number | null;
  brier: number | null;
}

/** Lee un número del JSONB de diagnóstico (o null si no viaja). */
export function numDe(o: DatosExtra | null, clave: string): number | null {
  if (!o) return null;
  const v = o[clave];
  return typeof v === "number" ? v : null;
}

async function jsonDe<T>(ruta: string): Promise<T> {
  const res = await fetch(`${origen()}${ruta}`, { cache: "no-store" });
  if (!res.ok) {
    let detalle = "";
    try {
      const cuerpo = (await res.json()) as { detail?: string };
      detalle = cuerpo.detail ? ` (${cuerpo.detail})` : "";
    } catch {
      // cuerpo sin JSON: no pasa nada, el código basta
    }
    throw new Error(`la API respondió ${res.status}${detalle}`);
  }
  return (await res.json()) as T;
}

export const obtenerFixtures = (liga: string, limite = 20) =>
  jsonDe<Fixture[]>(`/fixtures?liga=${liga}&limite=${limite}`);

export const obtenerPredicciones = (idPartido: number) =>
  jsonDe<PrediccionesPartido>(`/predictions/${idPartido}`);

export const obtenerEquipo = (idEquipo: number) =>
  jsonDe<EquipoDetalle>(`/teams/${idEquipo}`);

export const obtenerJugador = (idJugador: number) =>
  jsonDe<JugadorDetalle>(`/players/${idJugador}`);

export const obtenerRankings = (liga: string) =>
  jsonDe<ClasificacionFila[]>(`/rankings?liga=${liga}`);

export const obtenerPrecision = () => jsonDe<MetricasModelo[]>("/model-accuracy");
