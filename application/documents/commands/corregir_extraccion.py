"""Caso de uso: guardar una correccion humana del Markdown extraido
(Modulo 8, Documento Maestro seccion 4.6: "corregir"). A diferencia de
RevisarDocumento (que avanza EXTRAIDO -> EN_REVISION -> REVISADO), esta
operacion NO cambia el estado del documento -- puede llamarse varias
veces mientras el revisor sigue trabajando en el panel de edicion,
antes de aprobar la revision."""
from __future__ import annotations

from domain.documents.entities import Documento, EstadoDocumento
from domain.documents.exceptions import CorreccionRequiereEstadoExtraidoError, DocumentNotFoundError
from domain.documents.ports import DocumentRepository, ExtractionOutputStore
from domain.projects.ports import AuditLogger


class CorregirExtraccion:
    def __init__(
        self,
        repository: DocumentRepository,
        output_store: ExtractionOutputStore,
        audit: AuditLogger,
    ):
        self._repository = repository
        self._output_store = output_store
        self._audit = audit

    def execute(self, documento_id: str, markdown_corregido: str) -> Documento:
        documento = self._repository.get(documento_id)
        if documento is None:
            raise DocumentNotFoundError(documento_id)
        # Hallazgo real de la cuarta auditoria general (2026-08-01): antes
        # se llamaba a `self._output_store.guardar(...)` ANTES de que
        # `documento.corregir()` validara `estado == EXTRAIDO` -- si este
        # caso de uso se invocaba sobre un documento en cualquier otro
        # estado, ya quedaba un archivo escrito en `05_revisiones/` antes
        # del rechazo (mismo patron de bug ya corregido en
        # `registrar_documento.py`: validar antes de tocar el sistema de
        # archivos, nunca despues). Se valida aqui, de forma explicita y
        # temprana, en vez de confiar en que `corregir()` se invoque antes
        # de la escritura.
        if documento.estado != EstadoDocumento.EXTRAIDO:
            raise CorreccionRequiereEstadoExtraidoError(documento.id, documento.estado.value)

        ruta_revisado = self._output_store.guardar(documento.id, markdown_corregido)
        documento = documento.corregir(ruta_revisado)
        self._repository.save(documento)

        self._audit.record(
            proyecto_id=documento.proyecto_id,
            accion="corregir_extraccion",
            valor_anterior=None,
            valor_nuevo=ruta_revisado,
            motivo="Correccion humana del Markdown extraido contra el original (Documento Maestro, Modulo 8).",
        )
        return documento
