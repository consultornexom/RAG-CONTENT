"""Caso de uso: completar la revision humana de un documento ya
extraido (Modulo 8, Documento Maestro seccion 4.6: "Revision contra
originales"). EXTRAIDO -> EN_REVISION -> REVISADO en un solo paso
atomico, mismo principio que ClasificarDocumento/NormalizarDocumento.

Ademas de avanzar el estado, guarda un registro `Revision` propio
(ADR-001 seccion 5: "documento_id, revisor, fecha, alcance revisado,
incidencias detectadas") en `RevisionRepository` -- historial completo,
nunca se sobrescribe, a diferencia de `Documento` (que solo guarda el
estado/ruta de su revision MAS RECIENTE). `incidencias_detectadas` la
resuelve quien llama a este caso de uso (ver
application.documents.service.DocumentsService.revisar_documento` y
`ui.main_window.MainWindow._on_aprobar_revision`, que la arma
consultando `IncidentsService.listar_incidencias_de_documento()`) --
este caso de uso no importa `domain.incidents` en absoluto, solo
recibe la lista de ids ya armada (mismo principio que
`NormalizarDocumento` con las reglas del perfil).

Antes de avanzar el estado, pide a `GovernanceService` (Modulo 13,
application.governance) que verifique que el documento puede
aprobarse -- si tiene incidencias criticas todavia abiertas, la
verificacion lanza `IncidenciasCriticasAbiertasError` y este metodo
la deja propagarse sin mutar nada (Documento Maestro, seccion 4.7:
"no aprobar documentos con incidencias criticas abiertas"). Mismo
principio de acoplamiento cruzado resuelto en application, nunca en
domain, que ya usa RegistrarIncidencia con DocumentRepository."""
from __future__ import annotations

from application.governance.service import GovernanceService
from domain.documents.entities import Documento, EstadoDocumento, Revision
from domain.documents.exceptions import DocumentNotFoundError
from domain.documents.ports import DocumentRepository, RevisionRepository
from domain.projects.ports import AuditLogger


class RevisarDocumento:
    def __init__(
        self,
        repository: DocumentRepository,
        revision_repository: RevisionRepository,
        audit: AuditLogger,
        governance: GovernanceService,
    ):
        self._repository = repository
        self._revision_repository = revision_repository
        self._audit = audit
        self._governance = governance

    def execute(
        self,
        documento_id: str,
        revisor: str,
        comentario: str = "",
        incidencias_detectadas: list[str] | None = None,
    ) -> Documento:
        documento = self._repository.get(documento_id)
        if documento is None:
            raise DocumentNotFoundError(documento_id)

        revisor = revisor.strip()
        if not revisor:
            raise ValueError("El revisor no puede estar vacio")

        self._governance.verificar_documento_aprobable(documento_id)

        documento = documento.avanzar_a(EstadoDocumento.EN_REVISION).avanzar_a(EstadoDocumento.REVISADO)
        self._repository.save(documento)

        revision = Revision(
            documento_id=documento.id,
            revisor=revisor,
            comentario=comentario.strip(),
            incidencias_detectadas=incidencias_detectadas or [],
        )
        self._revision_repository.save(revision)

        self._audit.record(
            proyecto_id=documento.proyecto_id,
            accion="revisar_documento",
            valor_anterior=EstadoDocumento.EXTRAIDO.value,
            valor_nuevo=revisor,
            motivo=comentario.strip() or "Revision contra el original completada (Documento Maestro, Modulo 8).",
        )
        return documento
