"""Caso de uso: crear un lote nuevo, ABIERTO, dentro de un proyecto
(Fase 7, Documento Maestro seccion 4.10)."""
from __future__ import annotations

from domain.batches.entities import Lote
from domain.batches.ports import LoteRepository
from domain.projects.ports import AuditLogger


class CrearLote:
    def __init__(self, repository: LoteRepository, audit: AuditLogger):
        self._repository = repository
        self._audit = audit

    def execute(self, proyecto_id: str, nombre: str) -> Lote:
        lote = Lote(proyecto_id=proyecto_id, nombre=nombre)
        self._repository.save(lote)
        self._audit.record(
            proyecto_id=proyecto_id,
            accion="crear_lote",
            valor_anterior=None,
            valor_nuevo=lote.nombre,
            motivo="Alta de un lote nuevo (Documento Maestro, seccion 4.10).",
        )
        return lote
