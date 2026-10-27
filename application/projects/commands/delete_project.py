"""Caso de uso: eliminar de verdad un proyecto (Auditoria 2026-09-02,
hallazgo real RAG_CONTENT_01 -- "tratamiento a proyecto que no
proceden, como eliminarlos"). Mismo criterio que RAG STUDIO adopto para
su propio DeleteProject (Ronda 3/4 de
Validacion_observaciones_RAG_STUDIO.md): "Archivar" (ver
ArchivarProyecto) es la unica operacion siempre disponible; eliminar de
verdad -- borrar la carpeta completa del proyecto, con proyecto.db
incluido -- solo se permite si el proyecto todavia no tiene ningun
documento registrado, para no perder trabajo real ni informacion de
auditoria sin posibilidad de recuperacion (Documento Maestro, seccion
4.1).

Auditoria 2026-09-02 (hallazgo real de la auditoria independiente de
esta misma ronda, severidad medio-alta): la primera version de esta
clase no dejaba ningun rastro en `eventos_auditoria` al eliminar un
proyecto -- la unica operacion mutadora de todo el sistema que no
auditaba nada (confirmado por grep: mas de 30 comandos de application/
llaman a `audit.record(...)`, incluido `CerrarLote`, mucho menos
destructivo que esto). Tras eliminar un proyecto no quedaba ninguna
evidencia de quien lo borro ni cuando. Se agrega el mismo patron que
`ArchivarProyecto` ya usaba. El evento se registra DESPUES de que la
carpeta y el indice ya se borraron -- `eventos_auditoria` vive en
`aplicacion.db` (la base global), una tabla distinta de `proyectos` y
sin ninguna relacion de llave foranea entre ambas (ver
infrastructure/database/models.py), asi que sigue existiendo y siendo
consultable aunque el proyecto que referencia ya no este."""
from __future__ import annotations

from domain.projects.exceptions import ProjectInUseError, ProjectNotFoundError
from domain.projects.ports import AuditLogger, ProjectContentChecker, ProjectFileStore, ProjectRepository


class EliminarProyecto:
    def __init__(
        self,
        repository: ProjectRepository,
        file_store: ProjectFileStore,
        content_checker: ProjectContentChecker,
        audit: AuditLogger,
    ):
        self._repository = repository
        self._file_store = file_store
        self._content_checker = content_checker
        self._audit = audit

    def execute(self, proyecto_id: str) -> None:
        proyecto = self._repository.get(proyecto_id)
        if proyecto is None:
            raise ProjectNotFoundError(proyecto_id)

        if self._content_checker.tiene_documentos(proyecto):
            # No se necesita el conteo exacto para la decision (alcanza
            # con saber que hay al menos uno), pero el mensaje de
            # ProjectInUseError es mas util con un numero real -- ver
            # SqlAlchemyProjectContentChecker.
            cantidad = self._content_checker.contar_documentos(proyecto)
            raise ProjectInUseError(proyecto_id, cantidad)

        # Orden deliberado (misma leccion que RAG STUDIO aprendio en su
        # Ronda 4): la carpeta se borra PRIMERO, y el registro del
        # indice global recien despues, y solo si lo anterior no lanzo
        # ningun error. Al reves (indice primero) un fallo fisico a
        # medias deja el proyecto invisible en la app pero sus archivos
        # todavia en disco, sin ningun aviso.
        self._file_store.delete_structure(proyecto)
        self._repository.delete(proyecto.id)

        self._audit.record(
            proyecto_id=proyecto.id,
            accion="eliminar_proyecto",
            valor_anterior=proyecto.estado.value,
            valor_nuevo=None,
            motivo="Eliminacion real y permanente (sin documentos registrados): carpeta e indice borrados.",
        )
