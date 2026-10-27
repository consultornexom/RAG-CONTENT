"""quita restriccion unica de nombre en proyectos

Revision ID: e567d7d3174e
Revises: 3ab8296484bc
Create Date: 2026-09-02 14:20:18.297600

Auditoria 2026-09-02 (hallazgo real de la auditoria independiente de la
ronda de Archivar/Eliminar proyecto, RAG_CONTENT_01): el `UniqueConstraint
('nombre')` de la migracion inicial (6824add93305) bloqueaba para siempre
volver a crear un proyecto ACTIVO con el mismo nombre que uno ya
ARCHIVADO -- justo el escenario que motivo agregar "Archivar" en primer
lugar (un proyecto mal nombrado se archiva, y despues no se puede crear
el correcto con el nombre que en realidad se queria usar). La unicidad
pasa a exigirse solo entre proyectos ACTIVOS, en la capa de aplicacion
(ver `infrastructure/database/repository.py::get_by_name`, que ahora
filtra por `estado=ACTIVO`).

SQLite no soporta `ALTER TABLE ... DROP CONSTRAINT` ni dejar caer una
restriccion UNIQUE definida inline en el CREATE TABLE original -- la
unica forma real de quitarla es recrear la tabla (mismo patron que
Alembic usa internamente en modo batch para SQLite). Se hace explicito
aqui en vez de con `op.batch_alter_table(...)` porque una restriccion
UNIQUE sin nombre propio (como la de la migracion inicial) no tiene un
identificador que `drop_constraint()` pueda referenciar de forma
confiable.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e567d7d3174e'
down_revision: Union[str, None] = '3ab8296484bc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNAS = (
    "id, nombre, perfil_id, objetivo, usuarios_objetivo_csv, alcance, "
    "jurisdiccion, idioma, confidencialidad, responsables_csv, estado, "
    "ruta_carpeta, created_at, updated_at"
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE proyectos_tmp (
            id VARCHAR(16) NOT NULL,
            nombre VARCHAR(200) NOT NULL,
            perfil_id VARCHAR(100) NOT NULL,
            objetivo TEXT NOT NULL,
            usuarios_objetivo_csv TEXT NOT NULL,
            alcance TEXT NOT NULL,
            jurisdiccion VARCHAR(200) NOT NULL,
            idioma VARCHAR(10) NOT NULL,
            confidencialidad VARCHAR(20) NOT NULL,
            responsables_csv TEXT NOT NULL,
            estado VARCHAR(20) NOT NULL,
            ruta_carpeta TEXT NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            PRIMARY KEY (id)
        )
        """
    )
    # nosec B608 -- _COLUMNAS es una constante de este mismo modulo (los
    # nombres fijos de columna de la tabla), no un dato externo ni de
    # usuario; no hay ninguna cadena interpolada que provenga de fuera
    # de este archivo de migracion.
    op.execute(f"INSERT INTO proyectos_tmp ({_COLUMNAS}) SELECT {_COLUMNAS} FROM proyectos")  # nosec B608
    op.execute("DROP TABLE proyectos")
    op.execute("ALTER TABLE proyectos_tmp RENAME TO proyectos")
    op.create_index(op.f("ix_proyectos_nombre"), "proyectos", ["nombre"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_proyectos_nombre"), table_name="proyectos")
    op.execute(
        """
        CREATE TABLE proyectos_tmp (
            id VARCHAR(16) NOT NULL,
            nombre VARCHAR(200) NOT NULL,
            perfil_id VARCHAR(100) NOT NULL,
            objetivo TEXT NOT NULL,
            usuarios_objetivo_csv TEXT NOT NULL,
            alcance TEXT NOT NULL,
            jurisdiccion VARCHAR(200) NOT NULL,
            idioma VARCHAR(10) NOT NULL,
            confidencialidad VARCHAR(20) NOT NULL,
            responsables_csv TEXT NOT NULL,
            estado VARCHAR(20) NOT NULL,
            ruta_carpeta TEXT NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            PRIMARY KEY (id),
            UNIQUE (nombre)
        )
        """
    )
    # nosec B608 -- _COLUMNAS es una constante de este mismo modulo (los
    # nombres fijos de columna de la tabla), no un dato externo ni de
    # usuario; no hay ninguna cadena interpolada que provenga de fuera
    # de este archivo de migracion.
    op.execute(f"INSERT INTO proyectos_tmp ({_COLUMNAS}) SELECT {_COLUMNAS} FROM proyectos")  # nosec B608
    op.execute("DROP TABLE proyectos")
    op.execute("ALTER TABLE proyectos_tmp RENAME TO proyectos")
