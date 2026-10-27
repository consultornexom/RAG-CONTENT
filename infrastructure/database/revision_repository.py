"""Adaptador de RevisionRepository sobre SQLAlchemy sobre proyecto.db
(ADR-001, seccion 4). domain.documents.ports no sabe que existe
SQLAlchemy; esta clase es la unica que lo importa -- mismo patron que
infrastructure.database.incident_repository.

A diferencia de SqlAlchemyDocumentRepository/SqlAlchemyIncidentRepository
(que hacen upsert via session.get() + actualizar fila existente),
save() aqui siempre inserta una fila nueva -- domain.documents.entities.
Revision es un registro inmutable, nunca se actualiza uno existente."""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from domain.documents.entities import Revision
from domain.documents.ports import RevisionRepository

from .project_models import RevisionModel


def _to_entity(row: RevisionModel) -> Revision:
    return Revision(
        id=row.id,
        documento_id=row.documento_id,
        revisor=row.revisor,
        comentario=row.comentario,
        incidencias_detectadas=json.loads(row.incidencias_detectadas_json),
        fecha=row.fecha,
    )


def _to_row(revision: Revision) -> RevisionModel:
    return RevisionModel(
        id=revision.id,
        documento_id=revision.documento_id,
        revisor=revision.revisor,
        comentario=revision.comentario,
        incidencias_detectadas_json=json.dumps(revision.incidencias_detectadas),
        fecha=revision.fecha,
    )


class SqlAlchemyRevisionRepository(RevisionRepository):
    def __init__(self, session: Session):
        self._session = session

    def save(self, revision: Revision) -> None:
        self._session.add(_to_row(revision))
        self._session.commit()

    def list_by_document(self, documento_id: str) -> list[Revision]:
        stmt = (
            select(RevisionModel)
            .where(RevisionModel.documento_id == documento_id)
            .order_by(RevisionModel.fecha)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [_to_entity(r) for r in rows]
