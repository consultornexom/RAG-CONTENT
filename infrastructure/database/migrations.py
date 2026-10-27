"""Aplica las migraciones de Alembic mediante la API programatica, sin
requerir que el operador ejecute Alembic desde una terminal (Documento
Maestro, seccion 4.11.1: principios de baja friccion). Sustituye al
`metadata.create_all()` que se usaba como parche temporal en el
esqueleto de la Fase 1 (ver ADR-001, seccion 9: "dos lineas de
migracion independientes").

Cada llamada a `upgrade_to_head()` es idempotente: si la base ya esta
al dia, Alembic no hace nada; si es la primera vez que se abre (archivo
SQLite nuevo o inexistente), crea todas las tablas ejecutando, en
orden, cada revision desde el principio.
"""
from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic import command

_RAIZ_MIGRACIONES = Path(__file__).resolve().parents[2] / "migrations"

RUTA_LINEA_GLOBAL = _RAIZ_MIGRACIONES / "global"
"""Linea de migracion de aplicacion.db (proyectos, eventos de
auditoria) -- ver infrastructure.database.models.Base."""

RUTA_LINEA_PROYECTO = _RAIZ_MIGRACIONES / "project"
"""Linea de migracion de proyecto.db (documentos) -- ver
infrastructure.database.project_models.BaseProyecto."""


def upgrade_to_head(db_path: Path, script_location: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    cfg = Config()
    cfg.set_main_option("script_location", str(script_location))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(cfg, "head")
