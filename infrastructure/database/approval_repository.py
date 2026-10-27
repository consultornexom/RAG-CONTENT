"""Adaptador de AprobacionRepository sobre SQLAlchemy sobre proyecto.db
(ADR-001, seccion 4). domain.documents.ports no sabe que existe
SQLAlchemy; esta clase es la unica que lo importa -- mismo patron que
infrastructure.database.revision_repository.

save() siempre inserta una fila nueva -- domain.documents.entities.
Aprobacion es un registro inmutable, nunca se actualiza uno existente."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from domain.documents.entities import Aprobacion
from domain.documents.ports import AprobacionRepository

from .project_models import AprobacionModel


def _to_entity(row: AprobacionModel) -> Aprobacion:
    return Aprobacion(
        id=row.id,
        documento_id=row.documento_id,
        aprobador=row.aprobador,
        comentario=row.comentario,
        fecha=row.fecha,
    )


def _to_row(aprobacion: Aprobacion) -> AprobacionModel:
    return AprobacionModel(
        id=aprobacion.id,
        documento_id=aprobacion.documento_id,
        aprobador=aprobacion.aprobador,
        comentario=aprobacion.comentario,
        fecha=aprobacion.fecha,
    )


class SqlAlchemyAprobacionRepository(AprobacionRepository):
    def __init__(self, session: Session):
        self._session = session

    def save(self, aprobacion: Aprobacion) -> None:
        self._session.add(_to_row(aprobacion))
        self._session.commit()

    def list_by_document(self, documento_id: str) -> list[Aprobacion]:
        stmt = (
            select(AprobacionModel)
            .where(AprobacionModel.documento_id == documento_id)
            .order_by(AprobacionModel.fecha)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [_to_entity(r) for r in rows]
