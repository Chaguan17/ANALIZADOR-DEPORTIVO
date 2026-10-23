"""Lector del JSONB `stats_partido` para los modelos de Fases 15-16.

Los tres dominios (tarjetas · tiros · cornes) leen exactamente la misma
materia prima: partidos jugados con la marca de ingesta ESPN en ambos lados.
Este módulo la hidrata una sola vez y cada modelo usa lo que necesita:

    fila = {
        "fecha":     datetime UTC del partido,
        "partido":   partido_id_api,
        "local":     id_equipo_local,
        "visitante": id_equipo_visitante,
        "datos_l":   JSONB completo del lado local  (o {} si le falta),
        "datos_v":   JSONB completo del lado visita (o {} si le falta),
    }

Regla de inclusión: el partido entra si AMBOS lados traen datos["espn"]
(la ingesta ESPN deja esa huella hasta cuando el summary no traía stats:
es la marca "vacio"). Cada modelo luego salta las filas a las que les
falte SU clave de dominio ("tarjetas"/"tiros"/"cornes") — así una fila
marca-de-vacío no contamina ninguna métrica.
"""

from __future__ import annotations

from sqlalchemy import select

from .models import Partido, StatsPartido


def filas_de_liga(session, liga: str) -> list[dict]:
    """Filas hidratadas de una liga: jugados con ambos lados ESPN ordenados por fecha."""
    jugados = (
        session.scalars(
            select(Partido)
            .where(Partido.liga == liga, Partido.estado == "FINISHED")
            .order_by(Partido.utc_date, Partido.id_api)
        )
        .all()
    )
    if not jugados:
        return []
    ids_de_partido = [p.id_api for p in jugados]
    stats = (
        session.scalars(
            select(StatsPartido).where(StatsPartido.partido_id_api.in_(ids_de_partido))
        )
        .all()
    )

    # {partido_id: {equipo_id: datos}} — la marca ESPN se guarda solo si ambos lados
    por_partido: dict[int, dict[int, dict]] = {}
    for stat in stats:
        datos = stat.datos or {}
        if not datos.get("espn"):
            continue  # filas ajenas a ESPN (otra fuente futura) quedan fuera
        por_partido.setdefault(stat.partido_id_api, {})[stat.equipo_id_api] = datos

    salida: list[dict] = []
    for p in jugados:
        lados = por_partido.get(p.id_api) or {}
        if p.id_local not in lados or p.id_visitante not in lados:
            continue  # necesita MARCAS de ambos lados (partido completo)
        salida.append({
            "fecha": p.utc_date,
            "partido": p.id_api,
            "local": p.id_local,
            "visitante": p.id_visitante,
            "datos_l": lados[p.id_local],
            "datos_v": lados[p.id_visitante],
        })
    return salida
