"""Adaptador de FuenteRepository sobre SQLAlchemy sobre proyecto.db
(ADR-001, seccion 4). domain.validity.ports no sabe que existe
SQLAlchemy; esta clase es la unica que lo importa -- mismo patron que
infrastructure.database.incident_repository.

A diferencia de IncidentRepository/DocumentRepository, la clave con la
que se busca/guarda es `documento_id` directamente (no un `id`
sintetico): a lo sumo existe una Fuente por documento (ver
domain.validity.entities.Fuente)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from domain.validity.entities import Fuente
from domain.validity.ports import FuenteRepository

from .project_models import FuenteModel


def _to_entity(row: FuenteModel) -> Fuente:
    return Fuente(
        documento_id=row.documento_id,
        sistema_origen=row.sistema_origen,
        autoridad=row.autoridad,
        evidencia_consulta=row.evidencia_consulta,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_row(fuente: Fuente, existing: Optional[FuenteModel] = None) -> FuenteModel:
    row = existing or FuenteModel(documento_id=fuente.documento_id)
    row.sistema_origen = fuente.sistema_origen
    row.autoridad = fuente.autoridad
    row.evidencia_consulta = fuente.evidencia_consulta
    row.created_at = fuente.created_at
    row.updated_at = fuente.updated_at
    return row


class SqlAlchemyFuenteRepository(FuenteRepository):
    def __init__(self, session: Session):
        self._session = session

    def save(self, fuente: Fuente) -> None:
        existing = self._session.get(FuenteModel, fuente.documento_id)
        row = _to_row(fuente, existing)
        if existing is None:
            self._session.add(row)
        self._session.commit()

    def get_by_document(self, documento_id: str) -> Optional[Fuente]:
        row = self._session.get(FuenteModel, documento_id)
        return _to_entity(row) if row else None
