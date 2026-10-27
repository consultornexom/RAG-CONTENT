"""Entorno de Alembic para la linea por proyecto (proyecto.db) --
ADR-001, seccion 9: la segunda de las "dos lineas de migracion
independientes". Esta linea versiona
`infrastructure.database.project_models.BaseProyecto` (documentos,
versiones, extracciones, revisiones, etc. -- todo lo que vive dentro de
un unico proyecto).

Se aplica sobre un proyecto.db distinto en cada llamada -- no hay una
sola base "de linea de proyecto", sino una por cada proyecto creado (ver
infrastructure.database.migrations.upgrade_to_head(), invocado desde
app.bootstrap.abrir_proyecto())."""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from infrastructure.database.project_models import BaseProyecto

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = BaseProyecto.metadata


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
