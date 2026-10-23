// Motor de recomendaciones (Fase 14): función PURA que "lee el partido".
//
// Entrada: lo que /fixtures ya entrega — probabilidades 1/X/2 por voz,
// λ de goles por equipo, over/under 2.5 y marcador estimado. Nada nuevo
// del backend: toda la verdad ya baja en cada boletín.
//
// Salida: UNA frase de escenario con su cifra clave + el consenso bruto
// (promedio simple de las voces) para la barra única de la tarjeta.
//
// Reglas por prioridad (la primera que aplica gana):
//   1. sin consenso     → "pendiente"
//   2. partido con goles → λ combinada alta y over 2.5 respaldado
//   3. partido cerrado   → λ combinada baja
//   4. favorito claro    → el resultado dominante del consenso es amplio
//   5. voces divididas   → las firmas no coinciden en el resultado
//   6. resto             → "equilibrado"
//
// Honradez: los promedios entre voces son simples (sin pesos), y el motor
// no inventa datos que no viajan: donde no hay número, no hay cifra.

import type { Fixture } from "./api";
import { num, pct } from "./formato";

/** λ combinada a partir de la cual el partido "pinta con goles". */
const UMBRAL_GOLES_LAMBDA = 2.8;
/** Consenso mínimo sobre el over 2.5 para respaldar el caso "con goles". */
const UMBRAL_GOLES_OVER = 0.55;
/** λ combinada por debajo de la cual el partido "pinta cerrado". */
const UMBRAL_CERRADO_LAMBDA = 2.2;
/** Probabilidad mínima del resultado dominante para hablar de favorito. */
const UMBRAL_FAVORITO = 0.55;

export type Letra = "1" | "X" | "2";

export type TonoEscenario =
  | "pendiente"
  | "goles"
  | "cerrado"
  | "favorito"
  | "dividido"
  | "equilibrado";

export interface Escenario {
  /** Qué caso se narra (primera regla que aplica). */
  tono: TonoEscenario;
  /** La oración héroe, leyendo el partido en español. */
  frase: string;
  /** La cifra del escenario para el acento en oro (null si no hay). */
  clave: string | null;
  /** Promedio simple 1/X/2 de las voces que emiten (barra única). */
  consenso: { p1: number; px: number; p2: number } | null;
  /** Resultado dominante del consenso (null sin consenso). */
  dominante: Letra | null;
  /** true si las voces no coinciden en el resultado (divergencia). */
  dividido: boolean;
  /** λ combinada promedio entre las voces que la emiten. */
  lambdaGoles: number | null;
  /** Marcador estimado de referencia (primera voz que lo emite). */
  marcador: string | null;
}

function promedio(valores: number[]): number {
  return valores.reduce((a, b) => a + b, 0) / valores.length;
}

/** La letra que firma una voz (null = aún no emite probabilidades). */
export function letraDe(
  pr: Fixture["predicciones"][number] | undefined,
): Letra | null {
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
export function pctDe(
  pr: Fixture["predicciones"][number],
  letra: Letra,
): number | null {
  if (letra === "1") return pr.prob_local;
  if (letra === "X") return pr.prob_empate;
  return pr.prob_visita;
}

export function escenario(fixture: Fixture): Escenario {
  const completas = fixture.predicciones.filter(
    (p) =>
      p.prob_local !== null && p.prob_empate !== null && p.prob_visita !== null,
  );

  // ── consenso: promedio simple de las voces que emiten ────────────────
  const consenso =
    completas.length === 0
      ? null
      : {
          p1: promedio(completas.map((p) => p.prob_local as number)),
          px: promedio(completas.map((p) => p.prob_empate as number)),
          p2: promedio(completas.map((p) => p.prob_visita as number)),
        };

  const dominante: Letra | null = consenso
    ? ([
        [consenso.p1, "1"],
        [consenso.px, "X"],
        [consenso.p2, "2"],
      ].reduce((a, b) => (b[0] > a[0] ? b : a))[1] as Letra)
    : null;

  // ── divergencia: las firmas no coinciden en el resultado ─────────────
  const letrasFirmadas = new Set(
    fixture.predicciones
      .map((p) => letraDe(p))
      .filter((l): l is Letra => l !== null),
  );
  const conFirma = fixture.predicciones.filter((p) => letraDe(p) !== null).length;
  const dividido = conFirma >= 2 && letrasFirmadas.size > 1;

  // ── λ combinada del partido (goles esperados) ────────────────────────
  const conLambda = fixture.predicciones.filter(
    (p) => p.lam_local !== null && p.lam_visita !== null,
  );
  const lambdaGoles = conLambda.length
    ? promedio(conLambda.map((p) => (p.lam_local as number) + (p.lam_visita as number)))
    : null;

  // ── over/under 2.5 promedio entre las voces que lo emiten ────────────
  const conOver = fixture.predicciones.filter((p) => p.prob_over25 !== null);
  const over25 = conOver.length
    ? promedio(conOver.map((p) => p.prob_over25 as number))
    : null;
  const conUnder = fixture.predicciones.filter((p) => p.prob_under25 !== null);
  const under25 = conUnder.length
    ? promedio(conUnder.map((p) => p.prob_under25 as number))
    : null;

  // ── marcador estimado de referencia (primera voz que lo emite) ───────
  const marcador =
    fixture.predicciones.find((p) => p.marcador_estimado !== null)
      ?.marcador_estimado ?? null;

  // ── reglas por prioridad ─────────────────────────────────────────────
  const pctDominante = dominante
    ? ((dominante === "1"
        ? consenso!.p1
        : dominante === "X"
          ? consenso!.px
          : consenso!.p2) as number)
    : 0;

  let tono: TonoEscenario;
  if (!consenso) tono = "pendiente";
  else if (
    lambdaGoles !== null &&
    lambdaGoles >= UMBRAL_GOLES_LAMBDA &&
    over25 !== null &&
    over25 >= UMBRAL_GOLES_OVER
  )
    tono = "goles";
  else if (lambdaGoles !== null && lambdaGoles <= UMBRAL_CERRADO_LAMBDA)
    tono = "cerrado";
  else if (pctDominante >= UMBRAL_FAVORITO) tono = "favorito";
  else if (dividido) tono = "dividido";
  else tono = "equilibrado";

  // ── la frase y su cifra ──────────────────────────────────────────────
  const frases: Record<TonoEscenario, { frase: string; clave: string | null }> = {
    pendiente: {
      frase: "Pronóstico pendiente: las voces todavía no emiten probabilidades.",
      clave: null,
    },
    goles: {
      frase: `Partido con goles: el over 2.5 toma ${pct(over25, 0)} del consenso.`,
      clave: `λ ${num(lambdaGoles, 1)}`,
    },
    cerrado: {
      frase: `Partido cerrado: apenas ${num(lambdaGoles, 1)} goles estimados para la tarde.`,
      clave:
        under25 !== null
          ? `under 2.5 al ${pct(under25, 0)}`
          : lambdaGoles !== null
            ? `λ ${num(lambdaGoles, 1)}`
            : null,
    },
    favorito: {
      frase:
        dominante === "1"
          ? `${fixture.local} sale favorito del consenso.`
          : dominante === "2"
            ? `${fixture.visitante} sale favorito del consenso.`
            : "El empate se perfila como la salida dominante.",
      clave: dominante
        ? `${dominante} al ${pct(pctDominante, 0)}`
        : null,
    },
    dividido: {
      frase: "Voces divididas: cada voz firma un resultado distinto.",
      clave: null,
    },
    equilibrado: {
      frase: "Escenario abierto: sin favorito claro ni señal de goles.",
      clave: null,
    },
  };

  return {
    tono,
    frase: frases[tono].frase,
    clave: frases[tono].clave,
    consenso,
    dominante,
    dividido,
    lambdaGoles,
    marcador,
  };
}
