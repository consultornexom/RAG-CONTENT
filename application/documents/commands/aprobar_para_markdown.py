"""Caso de uso: aprobar un documento ya normalizado para generar su
Markdown final (Modulo 12/13, Documento Maestro seccion 4.6.1 y 4.7).
NORMALIZADO -> PENDIENTE_DE_APROBACION -> APROBADO_PARA_MARKDOWN en un
solo paso atomico -- mismo principio que RevisarDocumento colapsando
EXTRAIDO -> EN_REVISION -> REVISADO.

Ademas de avanzar el estado, guarda un registro `Aprobacion` propio
(Documento Maestro, seccion 4.10) en `AprobacionRepository` -- historial
completo, nunca se sobrescribe, mismo reparto de responsabilidades que
RevisarDocumento con `Revision`.

Antes de avanzar el estado, pide a `GovernanceService` (Modulo 13) que
verifique que el documento puede aprobarse -- la MISMA regla que ya
aplica RevisarDocumento (incidencias criticas abiertas / vigencia
desconocida en documentos criticos), reutilizada aqui como segundo
punto de control: un documento sin incidencias criticas al momento de
REVISADO podria tener una registrada despues, mientras estaba en
NORMALIZADO o PENDIENTE_DE_APROBACION -- RegistrarIncidencia no
restringe el estado del documento sobre el que se abre una incidencia."""
from __future__ import annotations

from application.governance.service import GovernanceService
from domain.documents.entities import Aprobacion, Documento
from domain.documents.exceptions import DocumentNotFoundError
from domain.documents.ports import AprobacionRepository, DocumentRepository
from domain.projects.ports import AuditLogger


class AprobarParaMarkdown:
    def __init__(
        self,
        repository: DocumentRepository,
        aprobacion_repository: AprobacionRepository,
        audit: AuditLogger,
        governance: GovernanceService,
    ):
        self._repository = repository
        self._aprobacion_repository = aprobacion_repository
        self._audit = audit
        self._governance = governance

    def execute(self, documento_id: str, aprobador: str, comentario: str = "") -> Documento:
        documento = self._repository.get(documento_id)
        if documento is None:
            raise DocumentNotFoundError(documento_id)

        aprobador = aprobador.strip()
        if not aprobador:
            raise ValueError("El aprobador no puede estar vacio")

        self._governance.verificar_documento_aprobable(documento_id)

        documento = documento.aprobar_para_markdown()
        self._repository.save(documento)

        aprobacion = Aprobacion(documento_id=documento.id, aprobador=aprobador, comentario=comentario.strip())
        self._aprobacion_repository.save(aprobacion)

        self._audit.record(
            proyecto_id=documento.proyecto_id,
            accion="aprobar_para_markdown",
            valor_anterior=None,
            valor_nuevo=aprobador,
            motivo=comentario.strip() or "Aprobacion para generar Markdown final (Documento Maestro, Modulo 12/13).",
        )
        return documento
