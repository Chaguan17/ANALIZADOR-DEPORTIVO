"""Motor de base de datos y sesión SQLAlchemy (Fase 3).

- `engine`: conexión única al Postgres (local con docker-compose / Neon en nube).
- `SessionLocal`: fábrica de sesiones; `expire_on_commit=False` para poder leer
  atributos después del commit (accesos idempotentes con merge).
- `Base`: clase declarativa raíz que Alembic usará para detectar cambios y
  autogenerar migraciones.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base declarativa de todos los modelos ORM."""
