"""Contexto de Alembic — conecta las migraciones con los modelos ORM.

- Importa `Base.metadata` del backend (single source of truth del esquema).
- La URL de conexión viene de `backend/app/config.py` (que lee el `.env` raíz).
- `sys.path` inserta la raíz del repo para importar los paquetes desde cualquier CWD.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy import engine_from_config

from alembic import context

# repo/backend/alembic/env.py → raíz del repo = 3 niveles arriba
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.config import DATABASE_URL  # noqa: E402
from backend.app.db import Base  # noqa: E402
import backend.app.models  # noqa: E402,F401  (registra los modelos en Base.metadata)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# La URL nace del .env, no del ini (misma fuente de verdad que la app)
config.set_main_option("sqlalchemy.url", DATABASE_URL)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Genera el SQL sin conectar (útil para revisar el DDL comparado)."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Modo normal: conecta y ejecuta las migraciones."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
