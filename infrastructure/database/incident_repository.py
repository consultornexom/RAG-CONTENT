"""Adaptador de IncidentRepository sobre SQLAlchemy sobre proyecto.db
(ADR-001, seccion 4). domain.incidents.ports no sabe que existe
SQLAlchemy; esta clase es la unica que lo importa -- mismo patron que
infrastructure.database.document_repository.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from domain.incidents.entities import EstadoIncidencia, EtapaIncidencia, Incidencia, SeveridadIncidencia
from domain.incidents.ports import IncidentRepository

from .project_models import IncidenciaModel


def _to_entity(row: IncidenciaModel) -> Incidencia:
    return Incidencia(
        id=row.id,
        proyecto_id=row.proyecto_id,
        documento_id=row.documento_id,
        etapa=EtapaIncidencia(row.etapa),
        tipo=row.tipo,
        severidad=SeveridadIncidencia(row.severidad),
        evidencia=row.evidencia,
        impacto=row.impacto,
        responsable=row.responsable,
        estado=EstadoIncidencia(row.estado),
        respuesta=row.respuesta,
        decision=row.decision,
        cierre=row.cierre,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_row(incidencia: Incidencia, existing: Optional[IncidenciaModel] = None) -> IncidenciaModel:
    row = existing or IncidenciaModel(id=incidencia.id)
    row.proyecto_id = incidencia.proyecto_id
    row.documento_id = incidencia.documento_id
    row.etapa = incidencia.etapa.value
    row.tipo = incidencia.tipo
    row.severidad = incidencia.severidad.value
    row.evidencia = incidencia.evidencia
    row.impacto = incidencia.impacto
    row.responsable = incidencia.responsable
    row.estado = incidencia.estado.value
    row.respuesta = incidencia.respuesta
    row.decision = incidencia.decision
    row.cierre = incidencia.cierre
    row.created_at = incidencia.created_at
    row.updated_at = incidencia.updated_at
    return row


class SqlAlchemyIncidentRepository(IncidentRepository):
    def __init__(self, session: Session):
        self._session = session

    def save(self, incidencia: Incidencia) -> None:
        existing = self._session.get(IncidenciaModel, incidencia.id)
        row = _to_row(incidencia, existing)
        if existing is None:
            self._session.add(row)
        self._session.commit()

    def get(self, incidencia_id: str) -> Optional[Incidencia]:
        row = self._session.get(IncidenciaModel, incidencia_id)
        return _to_entity(row) if row else None

    def list_by_document(self, documento_id: str) -> list[Incidencia]:
        stmt = select(IncidenciaModel).where(IncidenciaModel.documento_id == documento_id)
        rows = self._session.execute(stmt).scalars().all()
        return [_to_entity(r) for r in rows]

    def list(self) -> list[Incidencia]:
        rows = self._session.execute(select(IncidenciaModel)).scalars().all()
        return [_to_entity(r) for r in rows]
