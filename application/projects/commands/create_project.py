"""Caso de uso: crear un proyecto (Documento Maestro, Hito H2 / Modulo 1).

Orquesta domain + infrastructure, sin conocer SQLAlchemy ni el sistema
de archivos directamente (ADR-001, seccion 4: application depende solo
de domain).
"""
from __future__ import annotations

from domain.profiles.ports import ProfileRepository
from domain.projects.entities import NivelConfidencialidad, Proyecto
from domain.projects.exceptions import DuplicateProjectNameError, ProfileNotFoundError
from domain.projects.ports import AuditLogger, ProjectFileStore, ProjectRepository


class CrearProyecto:
    def __init__(
        self,
        repository: ProjectRepository,
        profiles: ProfileRepository,
        file_store: ProjectFileStore,
        audit: AuditLogger,
    ):
        self._repository = repository
        self._profiles = profiles
        self._file_store = file_store
        self._audit = audit

    def execute(
        self,
        nombre: str,
        perfil_id: str,
        objetivo: str = "",
        usuarios_objetivo: list[str] | None = None,
        alcance: str = "",
        jurisdiccion: str = "",
        idioma: str = "es",
        confidencialidad: NivelConfidencialidad = NivelConfidencialidad.INTERNO,
        responsables: list[str] | None = None,
    ) -> Proyecto:
        if self._repository.get_by_name(nombre) is not None:
            raise DuplicateProjectNameError(nombre)

        if self._profiles.get(perfil_id) is None:
            raise ProfileNotFoundError(perfil_id)

        proyecto = Proyecto(
            nombre=nombre,
            perfil_id=perfil_id,
            objetivo=objetivo,
            usuarios_objetivo=usuarios_objetivo or [],
            alcance=alcance,
            jurisdiccion=jurisdiccion,
            idioma=idioma,
            confidencialidad=confidencialidad,
            responsables=responsables or [],
        )

        ruta = self._file_store.create_structure(proyecto)
        proyecto = proyecto.model_copy(update={"ruta_carpeta": ruta})
        self._repository.save(proyecto)

        self._audit.record(
            proyecto_id=proyecto.id,
            accion="crear_proyecto",
            valor_anterior=None,
            valor_nuevo=proyecto.nombre,
            motivo="Alta inicial del proyecto (Documento Maestro, Hito H2).",
        )
        return proyecto
