"""Motor de base de datos SQLite en modo WAL (Documento Maestro, seccion
4.3), reutilizable tanto para la base global (aplicacion.db) como para
cada base por proyecto (proyecto.db) -- ADR-001, seccion 9: "dos lineas
de migracion independientes (esquema global y esquema por proyecto)".

Ya no crea las tablas directamente desde los modelos
(`metadata.create_all`, el parche temporal de la Fase 1): quien llama
debe invocar antes `infrastructure.database.migrations.upgrade_to_head()`
sobre la misma ruta -- ver app.bootstrap, que ya lo hace por ambas
lineas. `build_engine()` solo abre el motor sobre una base que se asume
ya migrada."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine, event


def _activar_wal(dbapi_connection, connection_record) -> None:  # noqa: ANN001
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def build_engine(db_path: Path) -> Engine:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    event.listen(engine, "connect", _activar_wal)
    return engine
