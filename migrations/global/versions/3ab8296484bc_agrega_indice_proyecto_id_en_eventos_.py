"""agrega indice en eventos_auditoria.proyecto_id

Revision ID: 3ab8296484bc
Revises: 6824add93305
Create Date: 2026-08-01 00:00:00.000000

Hallazgo de la tercera auditoria general (2026-07-31), aplicado en la
cuarta ronda de correcciones: desde que `CerrarLote` audita la
resolucion de cada documento por separado ademas del evento agregado
(ver `application/batches/commands/cerrar_lote.py` y la migracion de
proyecto correspondiente), el volumen de filas en `eventos_auditoria`
crece proporcional a la cantidad de documentos por lote, no solo a la
cantidad de lotes cerrados. Cualquier consulta que filtre este
historial por `proyecto_id` (paneles futuros, informes, soporte) se
beneficia de un indice en vez de un table scan completo sobre la tabla
global compartida por todos los proyectos.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '3ab8296484bc'
down_revision: Union[str, None] = '6824add93305'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        op.f('ix_eventos_auditoria_proyecto_id'),
        'eventos_auditoria',
        ['proyecto_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_eventos_auditoria_proyecto_id'), table_name='eventos_auditoria')
