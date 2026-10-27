"""Puertos (interfaces) del contexto Proyectos.

Definidos en domain e implementados en infrastructure (ADR-001, seccion
4). domain nunca importa la implementacion concreta -- ni SQLAlchemy, ni
el sistema de archivos -- solo depende de estas abstracciones.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from domain.audit.entities import EventoAuditoria

from .entities import Proyecto


class ProjectRepository(ABC):
    """Persistencia de proyectos en la base global (aplicacion.db)."""

    @abstractmethod
    def save(self, proyecto: Proyecto) -> None: ...

    @abstractmethod
    def get(self, proyecto_id: str) -> Optional[Proyecto]: ...

    @abstractmethod
    def get_by_name(self, nombre: str) -> Optional[Proyecto]:
        """Auditoria 2026-09-02 (hallazgo real de la auditoria
        independiente de Archivar/Eliminar proyecto): busca solo entre
        proyectos con estado ACTIVO. Es el metodo que `CrearProyecto`
        usa para el chequeo de nombre duplicado -- si buscara entre
        todos los estados, un proyecto archivado bloquearia para siempre
        reutilizar su nombre, contradiciendo el proposito de archivar
        ("ya no procede"). No hay restriccion de unicidad de nombre
        entre proyectos ARCHIVADO."""
        ...

    @abstractmethod
    def list(self, incluir_archivados: bool = True) -> list[Proyecto]: ...

    @abstractmethod
    def delete(self, proyecto_id: str) -> None:
        """Auditoria 2026-09-02 (RAG_CONTENT_01): borra el registro del
        proyecto de la base global (aplicacion.db). Quien llama
        (application.projects.commands.delete_project.EliminarProyecto)
        ya valido que el proyecto no tiene documentos registrados --
        este metodo no repite esa validacion, solo ejecuta el borrado."""
        ...


class ProjectFileStore(ABC):
    """Estructura fisica de carpetas por proyecto (Documento Maestro,
    seccion 4.5): las 13 subcarpetas mas proyecto.yaml y proyecto.db."""

    @abstractmethod
    def create_structure(self, proyecto: Proyecto) -> str:
        """Crea la carpeta del proyecto con sus 13 subcarpetas y
        proyecto.yaml; devuelve la ruta absoluta creada. Debe fallar si
        la carpeta ya existe (ver ProjectFolderAlreadyExistsError)."""
        ...

    @abstractmethod
    def delete_structure(self, proyecto: Proyecto) -> None:
        """Auditoria 2026-09-02 (RAG_CONTENT_01): borra la carpeta
        completa de `proyecto` (incluido proyecto.db) del disco. Debe
        propagar cualquier error real (permisos, archivo en uso...) en
        vez de ignorarlo -- mismo criterio de RAG STUDIO tras su propio
        hallazgo (Ronda 4 de Validacion_observaciones_RAG_STUDIO.md):
        un borrado fisico a medias que se trata como exito deja datos
        huerfanos en disco sin ningun aviso. No borra el registro en
        `ProjectRepository` -- eso es responsabilidad de quien llama
        (EliminarProyecto), y debe pasar SOLO despues de que esto
        termine sin errores, para no dejar el indice global sin su
        carpeta si el borrado fisico fallara a medias."""
        ...


class ProjectContentChecker(ABC):
    """Auditoria 2026-09-02 (RAG_CONTENT_01): decide si un proyecto ya
    tiene documentos registrados (Modulo 3 en adelante), para que
    EliminarProyecto sepa si el borrado real es seguro. Vive en el
    contexto Proyectos pero su implementacion en infrastructure
    necesariamente consulta datos del contexto Documentos (proyecto.db)
    -- mismo patron de dependencia cruzada ya usado en RAG STUDIO
    (DeleteProject depende de SourceRepository del contexto Documentos)."""

    @abstractmethod
    def tiene_documentos(self, proyecto: Proyecto) -> bool:
        """True si `proyecto` ya tiene al menos un documento registrado
        en su proyecto.db. Un proyecto que nunca llego a abrirse para
        trabajar (proyecto.db no existe todavia) no tiene documentos --
        devuelve False sin error, nunca lanza solo por eso."""
        ...

    @abstractmethod
    def contar_documentos(self, proyecto: Proyecto) -> int:
        """Cantidad exacta de documentos registrados -- solo se llama
        cuando `tiene_documentos()` ya devolvio True, para que
        ProjectInUseError pueda informar cuantos hay (mismo criterio que
        RAG STUDIO: `ProjectInUseError(project_id, len(sources))`)."""
        ...


class AuditLogger(ABC):
    """Registro de auditoria no modificable desde la interfaz ordinaria
    (Documento Maestro, seccion 4.1)."""

    @abstractmethod
    def record(
        self,
        proyecto_id: Optional[str],
        accion: str,
        valor_anterior: Optional[str],
        valor_nuevo: Optional[str],
        motivo: str,
    ) -> None: ...

    @abstractmethod
    def list_by_project(self, proyecto_id: str, limite: Optional[int] = None) -> list[EventoAuditoria]:
        """Fase 11 (pantalla "Auditoria" del menu funcional, Documento
        Maestro seccion 4.11): consulta de solo lectura, mas reciente
        primero -- necesaria para que la interfaz pueda MOSTRAR lo que
        `record()` ya escribe desde la Fase 1, algo que hasta ahora
        ningun caso de uso necesitaba (solo se escribia auditoria,
        nunca se leia de vuelta). No agrega ninguna regla de negocio
        nueva, solo hace visible un dato que ya existia.

        `limite`: hallazgo real de la cuarta auditoria general
        (2026-08-01): esta tabla crece con CADA accion mutadora del
        sistema (mas de 30 comandos distintos la invocan), y desde que
        `CerrarLote` audita cada documento por separado (ver
        `application.batches.commands.cerrar_lote`), un proyecto de vida
        larga puede acumular miles de filas. Antes, tanto el panel de
        Auditoria como el tablero principal traian TODAS las filas a
        memoria Python y recien ahi truncaban (o ni eso) -- `limite`
        permite que el adaptador aplique un `LIMIT` real en la consulta
        SQL (aprovechando el indice de `eventos_auditoria.proyecto_id`),
        en vez de cargar de mas para descartar despues. `None`
        (predeterminado) preserva el comportamiento anterior: sin
        limite, todas las filas del proyecto."""
        ...
