import type { Metadata } from "next";
import { Archivo, Spline_Sans_Mono } from "next/font/google";
import Encabezado, { Pie } from "@/components/Encabezado";
import "./globals.css";

// Fuente de identidad: Archivo (-variable, con eje wdth para los carteles deportivos).
const archivo = Archivo({
  subsets: ["latin"],
  variable: "--font-archivo",
  axes: ["wdth"],
});

// Números de tablero: la verdad de los datos en tipografía de monoespaciada.
const numeros = Spline_Sans_Mono({
  subsets: ["latin"],
  variable: "--font-num",
});

export const metadata: Metadata = {
  title: {
    default: "Analizador Deportivo",
    template: "%s · Analizador Deportivo",
  },
  description:
    "Predicciones de fútbol con tres modelos compitiendo (Poisson, Dixon-Coles, LightGBM), datos de football-data.org y evaluación walk-forward honesta.",
};

export default function RootLayout({
  children,
}: LayoutProps<"/">) {
  return (
    <html
      lang="es"
      className={`${archivo.variable} ${numeros.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <Encabezado />
        <main className="grow">{children}</main>
        <Pie />
      </body>
    </html>
  );
}
