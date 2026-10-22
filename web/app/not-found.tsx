import Link from "next/link";

export default function NoEncontrado() {
  return (
    <div className="contenedor">
      <h1 className="titulo-pagina">Esta esquina de la web no existe.</h1>
      <p className="titulo-sub">
        La ruta que pediste no está construida (o se escribió a mano mal). Lo
        vivo está en <Link href="/">Partidos</Link>.
      </p>
    </div>
  );
}
