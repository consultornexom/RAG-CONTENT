"""Adaptador de TrabajoRepository sobre SQLAlchemy sobre proyecto.db
(ADR-001, seccion 4). domain.jobs.ports no sabe que existe SQLAlchemy;
esta clase es la unica que lo importa -- mismo patron que
infrastructure.database.document_repository.

`list_pendientes_por_prioridad()` filtra por estado en SQL (usa el
indice de `TrabajoModel.estado`) pero ordena en Python con
`domain.jobs.entities.orden_prioridad()` -- la funcion pura que ya
declara el criterio de orden, para no duplicarlo como una expresion
CASE en SQL (mismo principio que domain.validity.entities.
vigencia_desconocida(), reutilizada en vez de reimplementada)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from domain.jobs.entities import EstadoTrabajo, Prioridad, Trabajo, TipoTrabajo, orden_prioridad
from domain.jobs.ports import TrabajoRepository

from .project_models import TrabajoModel


def _to_entity(row: TrabajoModel) -> Trabajo:
    return Trabajo(
        id=row.id,
        proyecto_id=row.proyecto_id,
        tipo=TipoTrabajo(row.tipo),
        documento_id=row.documento_id,
        estado=EstadoTrabajo(row.estado),
        prioridad=Prioridad(row.prioridad),
        intentos=row.intentos,
        max_intentos=row.max_intentos,
        mensaje_error=row.mensaje_error,
        creado_en=row.creado_en,
        actualizado_en=row.actualizado_en,
        iniciado_en=row.iniciado_en,
        finalizado_en=row.finalizado_en,
    )


def _to_row(trabajo: Trabajo, existing: Optional[TrabajoModel] = None) -> TrabajoModel:
    row = existing or TrabajoModel(id=trabajo.id)
    row.proyecto_id = trabajo.proyecto_id
    row.tipo = trabajo.tipo.value
    row.documento_id = trabajo.documento_id
    row.estado = trabajo.estado.value
    row.prioridad = trabajo.prioridad.value
    row.intentos = trabajo.intentos
    row.max_intentos = trabajo.max_intentos
    row.mensaje_error = trabajo.mensaje_error
    row.creado_en = trabajo.creado_en
    row.actualizado_en = trabajo.actualizado_en
    row.iniciado_en = trabajo.iniciado_en
    row.finalizado_en = trabajo.finalizado_en
    return row


class SqlAlchemyTrabajoRepository(TrabajoRepository):
    def __init__(self, session: Session):
        self._session = session

    def save(self, trabajo: Trabajo) -> None:
        existing = self._session.get(TrabajoModel, trabajo.id)
        row = _to_row(trabajo, existing)
        if existing is None:
            self._session.add(row)
        self._session.commit()

    def get(self, trabajo_id: str) -> Optional[Trabajo]:
        row = self._session.get(TrabajoModel, trabajo_id)
        return _to_entity(row) if row else None

    def list_by_estado(self, estado: EstadoTrabajo) -> list[Trabajo]:
        stmt = select(TrabajoModel).where(TrabajoModel.estado == EstadoTrabajo(estado).value)
        rows = self._session.execute(stmt).scalars().all()
        return [_to_entity(r) for r in rows]

    def list_by_document(self, documento_id: str) -> list[Trabajo]:
        stmt = (
            select(TrabajoModel)
            .where(TrabajoModel.documento_id == documento_id)
            .order_by(TrabajoModel.creado_en)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [_to_entity(r) for r in rows]

    def list_pendientes_por_prioridad(self) -> list[Trabajo]:
        pendientes = self.list_by_estado(EstadoTrabajo.PENDIENTE)
        return sorted(pendientes, key=lambda t: (orden_prioridad(t.prioridad), t.creado_en))

    def list(self) -> list[Trabajo]:
        """Definido al final -- ver el docstring de
        domain.jobs.ports.TrabajoRepository.list() sobre por que un
        metodo llamado `list` debe ir despues de cualquier otro metodo
        de la clase que anote su retorno como `list[...]`."""
        rows = self._session.execute(select(TrabajoModel)).scalars().all()
        return [_to_entity(r) for r in rows]
