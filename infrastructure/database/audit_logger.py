"""Adaptador de AuditLogger sobre SQLAlchemy (ADR-001, seccion 4)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from domain.audit.entities import EventoAuditoria
from domain.projects.ports import AuditLogger

from .models import EventoAuditoriaModel


class SqlAlchemyAuditLogger(AuditLogger):
    def __init__(self, session: Session):
        self._session = session

    def record(
        self,
        proyecto_id: Optional[str],
        accion: str,
        valor_anterior: Optional[str],
        valor_nuevo: Optional[str],
        motivo: str,
    ) -> None:
        evento = EventoAuditoria(
            proyecto_id=proyecto_id,
            accion=accion,
            valor_anterior=valor_anterior,
            valor_nuevo=valor_nuevo,
            motivo=motivo,
        )
        row = EventoAuditoriaModel(
            id=evento.id,
            proyecto_id=evento.proyecto_id,
            accion=evento.accion,
            valor_anterior=evento.valor_anterior,
            valor_nuevo=evento.valor_nuevo,
            motivo=evento.motivo,
            fecha=evento.fecha,
        )
        self._session.add(row)
        self._session.commit()

    def list_by_project(self, proyecto_id: str, limite: Optional[int] = None) -> list[EventoAuditoria]:
        consulta = (
            select(EventoAuditoriaModel)
            .where(EventoAuditoriaModel.proyecto_id == proyecto_id)
            .order_by(EventoAuditoriaModel.fecha.desc())
        )
        # Hallazgo real de la cuarta auditoria general (2026-08-01): un
        # LIMIT real en SQL (no un slice de Python despues de traer todo)
        # es lo que de verdad evita el table scan completo -- se
        # aprovecha aqui el indice de eventos_auditoria.proyecto_id
        # (migracion 3ab8296484bc).
        if limite is not None:
            consulta = consulta.limit(limite)
        filas = self._session.execute(consulta).scalars().all()
        return [
            EventoAuditoria(
                id=fila.id,
                proyecto_id=fila.proyecto_id,
                accion=fila.accion,
                valor_anterior=fila.valor_anterior,
                valor_nuevo=fila.valor_nuevo,
                motivo=fila.motivo,
                fecha=fila.fecha,
            )
            for fila in filas
        ]
