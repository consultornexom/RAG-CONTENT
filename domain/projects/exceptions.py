"""Excepciones del contexto Proyectos."""
from __future__ import annotations


class ProjectDomainError(Exception):
    """Raiz de las excepciones de este contexto."""


class DuplicateProjectNameError(ProjectDomainError):
    def __init__(self, nombre: str):
        super().__init__(f"Ya existe un proyecto activo con el nombre '{nombre}'.")
        self.nombre = nombre


class ProfileNotFoundError(ProjectDomainError):
    def __init__(self, perfil_id: str):
        super().__init__(f"No se encontro el perfil '{perfil_id}'. Cargue el paquete de perfil antes de crear el proyecto.")
        self.perfil_id = perfil_id


class ProjectFolderAlreadyExistsError(ProjectDomainError):
    def __init__(self, ruta: str):
        super().__init__(
            f"La carpeta de proyecto '{ruta}' ya existe. No se crea un proyecto nuevo sobre una "
            "carpeta existente (Documento Maestro, seccion 4.1: originales inmutables / trazabilidad)."
        )
        self.ruta = ruta


class ProjectNotFoundError(ProjectDomainError):
    """Auditoria 2026-09-02 (RAG_CONTENT_01): usada por ArchivarProyecto
    y EliminarProyecto -- mismo criterio que ProfileNotFoundError."""

    def __init__(self, proyecto_id: str):
        super().__init__(f"No existe un proyecto con id={proyecto_id!r}.")
        self.proyecto_id = proyecto_id


class ProjectAlreadyArchivedError(ProjectDomainError):
    """Auditoria 2026-09-02: `Proyecto.archivar()` es una transicion de
    un solo sentido (ACTIVO -> ARCHIVADO) -- volver a archivar un
    proyecto ya archivado no tiene efecto util y probablemente indica
    que la interfaz muestra datos obsoletos (dos clics rapidos, dos
    pestanas abiertas...), asi que se avisa en vez de ignorarlo en
    silencio."""

    def __init__(self, proyecto_id: str):
        super().__init__(f"El proyecto {proyecto_id!r} ya esta archivado.")
        self.proyecto_id = proyecto_id


class ProjectInUseError(ProjectDomainError):
    """Auditoria 2026-09-02 (RAG_CONTENT_01, mismo criterio que
    RAG STUDIO usa para su propio DeleteProject -- ver
    application/projects/commands/delete_project.py en RAG STUDIO):
    eliminar de verdad un proyecto (borrar su carpeta completa, incluida
    proyecto.db) solo se permite si todavia no tiene ningun documento
    registrado. Un proyecto con trabajo real siempre tiene que
    archivarse, nunca eliminarse -- eliminarlo perderia originales,
    extracciones, revisiones y auditoria sin posibilidad de
    recuperacion, en contra del principio de trazabilidad del Documento
    Maestro, seccion 4.1."""

    def __init__(self, proyecto_id: str, cantidad_documentos: int):
        super().__init__(
            f"El proyecto {proyecto_id!r} tiene {cantidad_documentos} documento(s) registrado(s) -- "
            "no se puede eliminar (perderia trabajo real e informacion de auditoria). Archivelo en su lugar."
        )
        self.proyecto_id = proyecto_id
        self.cantidad_documentos = cantidad_documentos
