"""Adaptador de LoteRepository sobre SQLAlchemy sobre proyecto.db
(ADR-001, seccion 4). domain.batches.ports no sabe que existe
SQLAlchemy; esta clase es la unica que lo importa -- mismo patron que
infrastructure.database.job_repository."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from domain.batches.entities import EstadoLote, Lote
from domain.batches.ports import LoteRepository

from .project_models import LoteModel


def _to_entity(row: LoteModel) -> Lote:
    return Lote(
        id=row.id,
        proyecto_id=row.proyecto_id,
        nombre=row.nombre,
        estado=EstadoLote(row.estado),
        creado_en=row.creado_en,
        actualizado_en=row.actualizado_en,
        cerrado_en=row.cerrado_en,
    )


def _to_row(lote: Lote, existing: Optional[LoteModel] = None) -> LoteModel:
    row = existing or LoteModel(id=lote.id)
    row.proyecto_id = lote.proyecto_id
    row.nombre = lote.nombre
    row.estado = lote.estado.value
    row.creado_en = lote.creado_en
    row.actualizado_en = lote.actualizado_en
    row.cerrado_en = lote.cerrado_en
    return row


class SqlAlchemyLoteRepository(LoteRepository):
    def __init__(self, session: Session):
        self._session = session

    def save(self, lote: Lote) -> None:
        existing = self._session.get(LoteModel, lote.id)
        row = _to_row(lote, existing)
        if existing is None:
            self._session.add(row)
        self._session.commit()

    def get(self, lote_id: str) -> Optional[Lote]:
        row = self._session.get(LoteModel, lote_id)
        return _to_entity(row) if row else None

    def list_by_proyecto(self, proyecto_id: str) -> list[Lote]:
        stmt = select(LoteModel).where(LoteModel.proyecto_id == proyecto_id).order_by(LoteModel.creado_en)
        rows = self._session.execute(stmt).scalars().all()
        return [_to_entity(r) for r in rows]

    def list(self) -> list[Lote]:
        rows = self._session.execute(select(LoteModel)).scalars().all()
        return [_to_entity(r) for r in rows]
