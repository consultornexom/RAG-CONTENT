"""Adaptador de VigenciaRepository sobre SQLAlchemy sobre proyecto.db
(ADR-001, seccion 4) -- mismo patron que
infrastructure.database.source_repository (clave `documento_id`
directa, a lo sumo una Vigencia por documento)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from domain.validity.entities import Vigencia
from domain.validity.ports import VigenciaRepository

from .project_models import VigenciaModel


def _to_entity(row: VigenciaModel) -> Vigencia:
    return Vigencia(
        documento_id=row.documento_id,
        fecha_emision=row.fecha_emision,
        vigente_desde=row.vigente_desde,
        vigente_hasta=row.vigente_hasta,
        sin_vencimiento=row.sin_vencimiento,
        autoridad=row.autoridad,
        sustituye_a=row.sustituye_a,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_row(vigencia: Vigencia, existing: Optional[VigenciaModel] = None) -> VigenciaModel:
    row = existing or VigenciaModel(documento_id=vigencia.documento_id)
    row.fecha_emision = vigencia.fecha_emision
    row.vigente_desde = vigencia.vigente_desde
    row.vigente_hasta = vigencia.vigente_hasta
    row.sin_vencimiento = vigencia.sin_vencimiento
    row.autoridad = vigencia.autoridad
    row.sustituye_a = vigencia.sustituye_a
    row.created_at = vigencia.created_at
    row.updated_at = vigencia.updated_at
    return row


class SqlAlchemyVigenciaRepository(VigenciaRepository):
    def __init__(self, session: Session):
        self._session = session

    def save(self, vigencia: Vigencia) -> None:
        existing = self._session.get(VigenciaModel, vigencia.documento_id)
        row = _to_row(vigencia, existing)
        if existing is None:
            self._session.add(row)
        self._session.commit()

    def get_by_document(self, documento_id: str) -> Optional[Vigencia]:
        row = self._session.get(VigenciaModel, documento_id)
        return _to_entity(row) if row else None
