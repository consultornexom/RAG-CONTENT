"""Entorno de Alembic para la linea global (aplicacion.db) -- ADR-001,
seccion 9: "Alembic con dos lineas de migracion independientes (esquema
global y esquema por proyecto)". Esta linea versiona
`infrastructure.database.models.Base` (proyectos, perfiles reutilizables
en el futuro, eventos de auditoria).

Se ejecuta tanto desde la CLI de Alembic (`alembic -c alembic_global.ini
upgrade head`, uso de desarrollo) como programaticamente desde
`infrastructure.database.migrations.upgrade_to_head()` en cada arranque
de la aplicacion (Documento Maestro, seccion 4.11.1: baja friccion --
el operador nunca ejecuta Alembic a mano).
"""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from infrastructure.database.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
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
