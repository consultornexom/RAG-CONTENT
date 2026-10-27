"""Caso de uso: archivar un proyecto (Auditoria 2026-09-02, hallazgo
real RAG_CONTENT_01 -- "tratamiento a proyecto que no proceden, como
eliminarlos"). Transicion de estado reversible por quien administre la
base directamente; no borra ningun archivo. Ver
domain.projects.entities.Proyecto.archivar() para la regla de negocio."""
from __future__ import annotations

from domain.projects.entities import Proyecto
from domain.projects.exceptions import ProjectNotFoundError
from domain.projects.ports import AuditLogger, ProjectRepository


class ArchivarProyecto:
    def __init__(self, repository: ProjectRepository, audit: AuditLogger):
        self._repository = repository
        self._audit = audit

    def execute(self, proyecto_id: str) -> Proyecto:
        proyecto = self._repository.get(proyecto_id)
        if proyecto is None:
            raise ProjectNotFoundError(proyecto_id)

        archivado = proyecto.archivar()
        self._repository.save(archivado)

        self._audit.record(
            proyecto_id=archivado.id,
            accion="archivar_proyecto",
            valor_anterior=proyecto.estado.value,
            valor_nuevo=archivado.estado.value,
            motivo="El proyecto ya no procede -- se archiva para sacarlo del selector de proyectos activos.",
        )
        return archivado
