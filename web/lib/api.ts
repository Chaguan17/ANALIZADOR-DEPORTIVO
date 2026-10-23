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

export interface TorneoLiga {
  liga: string;
  evaluados: number;
  aciertos: number;
  accuracy: number | null;
}

export interface TorneoO25 {
  evaluados: number;
  aciertos: number;
  accuracy: number | null;
}

export interface TorneoForma {
  partido_id_api: number;
  liga: string;
  fecha_utc: string;
  local: string;
  visitante: string;
  goles_local: number;
  goles_visitante: number;
  elegido: string;
  resultado: string;
  acierto_1x2: boolean;
  log_loss_prediccion: number | null;
}

export interface TorneoModelo {
  modelo: string;
  evaluados: number;
  aciertos: number;
  accuracy: number | null;
  log_loss: number | null;
  brier: number | null;
  o25: TorneoO25 | null;
  por_liga: TorneoLiga[];
  forma: TorneoForma[];
}

// ── Fase 15: tarjetas con stats ESPN (on-request; datos en stats_partido) ──

export interface CalidadLinea {
  linea: number;
  evaluados: number;
  aciertos: number;
  accuracy: number | null;
  mae: number | null;
}

export interface CoberturaEspn {
  jugados: number;
  con_datos: number;
}

export interface JugadorEvento {
  nombre: string;
  minuto: number | null;
  tipo: string;
}

export interface TarjetaJugador {
  nombre: string;
  amarillas: number;
  rojas: number;
  apariciones: number;
  tasa: number | null;
}

export interface TarjetaLadoReal {
  amarillas: number;
  rojas: number;
  por_jugador: JugadorEvento[];
}

export interface PredTarjetas {
  tarjetas_esperadas: number;
  prob_over_2_5: number;
  prob_over_3_5: number;
  por_equipo: Record<string, number | null>;
}

export interface TarjetasPartido {
  partido_id_api: number;
  liga: string;
  fecha_utc: string;
  estado: string;
  jornada: number | null;
  local: string;
  visitante: string;
  fuente: string | null;
  cobertura: CoberturaEspn;
  calidad: CalidadLinea[];
  reales: Record<"local" | "visitante", TarjetaLadoReal> | null;
  prediccion: PredTarjetas | null;
  propensos: Record<string, TarjetaJugador[]> | null;
  notas: string[];
}

export interface TarjetaEquipoTemporada {
  equipo_id_api: number;
  nombre: string;
  partidos: number;
  tarjetas: number;
  tasa: number;
}

export interface TarjetaJugadorLiga extends TarjetaJugador {
  equipo: string;
  equipo_id_api: number;
}

export interface TarjetasLiga {
  liga: string;
  cobertura: CoberturaEspn;
  calidad: CalidadLinea[];
  equipos: TarjetaEquipoTemporada[];
  propensos: TarjetaJugadorLiga[];
  notas: string[];
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

export const obtenerTorneo = () => jsonDe<TorneoModelo[]>("/torneo");

export const obtenerTarjetasLiga = (liga: string) =>
  jsonDe<TarjetasLiga>(`/tarjetas?liga=${liga}`);

export const obtenerTarjetas = (idPartido: number) =>
  jsonDe<TarjetasPartido>(`/partido/${idPartido}/tarjetas`);
