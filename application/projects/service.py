"""Fachada del contexto Proyectos (ADR-001, seccion 4: ui solo depende
de application, nunca de domain o infrastructure directamente)."""
from __future__ import annotations

from domain.profiles.entities import PerfilProyecto
from domain.profiles.ports import ProfileRepository
from domain.projects.entities import NivelConfidencialidad, Proyecto
from domain.projects.ports import AuditLogger, ProjectContentChecker, ProjectFileStore, ProjectRepository

from .commands.archive_project import ArchivarProyecto
from .commands.create_project import CrearProyecto
from .commands.delete_project import EliminarProyecto


class ProjectsService:
    def __init__(
        self,
        repository: ProjectRepository,
        profiles: ProfileRepository,
        file_store: ProjectFileStore,
        audit: AuditLogger,
        content_checker: ProjectContentChecker | None = None,
    ):
        self._repository = repository
        self._profiles = profiles
        self._crear = CrearProyecto(repository, profiles, file_store, audit)
        self._archivar = ArchivarProyecto(repository, audit)
        # content_checker es opcional solo para no romper a quien ya
        # instancia ProjectsService sin el (pruebas existentes que no
        # ejercitan eliminar_proyecto()) -- mismo criterio que RAG
        # STUDIO usa para su propio ProjectService/DeleteProject.
        self._eliminar = (
            EliminarProyecto(repository, file_store, content_checker, audit) if content_checker is not None else None
        )

    def crear_proyecto(
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
        return self._crear.execute(
            nombre=nombre,
            perfil_id=perfil_id,
            objetivo=objetivo,
            usuarios_objetivo=usuarios_objetivo,
            alcance=alcance,
            jurisdiccion=jurisdiccion,
            idioma=idioma,
            confidencialidad=confidencialidad,
            responsables=responsables,
        )

    def obtener_proyecto(self, proyecto_id: str) -> Proyecto | None:
        return self._repository.get(proyecto_id)

    def listar_proyectos(self, incluir_archivados: bool = True) -> list[Proyecto]:
        return self._repository.list(incluir_archivados=incluir_archivados)

    def listar_perfiles(self) -> list[PerfilProyecto]:
        return self._profiles.list()

    def archivar_proyecto(self, proyecto_id: str) -> Proyecto:
        """Auditoria 2026-09-02 (RAG_CONTENT_01): ver
        domain.projects.entities.Proyecto.archivar()."""
        return self._archivar.execute(proyecto_id)

    def eliminar_proyecto(self, proyecto_id: str) -> None:
        """Auditoria 2026-09-02 (RAG_CONTENT_01): borrado real, solo si
        el proyecto no tiene documentos registrados -- ver
        EliminarProyecto/ProjectInUseError."""
        if self._eliminar is None:
            raise RuntimeError(
                "ProjectsService no fue configurado con ProjectContentChecker; no se puede eliminar proyectos."
            )
        self._eliminar.execute(proyecto_id)
