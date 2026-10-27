"""Fachada del contexto Incidencias (ADR-001, seccion 4: ui solo depende
de application)."""
from __future__ import annotations

from domain.documents.ports import DocumentRepository
from domain.incidents.entities import EtapaIncidencia, Incidencia, SeveridadIncidencia, filtrar_criticas_abiertas
from domain.incidents.ports import IncidentRepository
from domain.projects.ports import AuditLogger

from .commands.asignar_incidencia import AsignarIncidencia
from .commands.cerrar_incidencia import CerrarIncidencia
from .commands.decidir_incidencia import DecidirIncidencia
from .commands.registrar_incidencia import RegistrarIncidencia
from .commands.responder_incidencia import ResponderIncidencia


class IncidentsService:
    def __init__(
        self,
        repository: IncidentRepository,
        document_repository: DocumentRepository,
        audit: AuditLogger,
    ):
        self._repository = repository
        self._registrar = RegistrarIncidencia(repository, document_repository, audit)
        self._asignar = AsignarIncidencia(repository, audit)
        self._responder = ResponderIncidencia(repository, audit)
        self._decidir = DecidirIncidencia(repository, audit)
        self._cerrar = CerrarIncidencia(repository, audit)

    def registrar_incidencia(
        self,
        proyecto_id: str,
        documento_id: str,
        etapa: EtapaIncidencia,
        tipo: str,
        severidad: SeveridadIncidencia,
        evidencia: str,
        impacto: str,
    ) -> Incidencia:
        return self._registrar.execute(proyecto_id, documento_id, etapa, tipo, severidad, evidencia, impacto)

    def asignar_incidencia(self, incidencia_id: str, responsable: str) -> Incidencia:
        return self._asignar.execute(incidencia_id, responsable)

    def responder_incidencia(self, incidencia_id: str, respuesta: str) -> Incidencia:
        return self._responder.execute(incidencia_id, respuesta)

    def decidir_incidencia(self, incidencia_id: str, decision: str, resuelta: bool) -> Incidencia:
        return self._decidir.execute(incidencia_id, decision, resuelta)

    def cerrar_incidencia(self, incidencia_id: str, cierre: str) -> Incidencia:
        return self._cerrar.execute(incidencia_id, cierre)

    def obtener_incidencia(self, incidencia_id: str) -> Incidencia | None:
        return self._repository.get(incidencia_id)

    def listar_incidencias_de_documento(self, documento_id: str) -> list[Incidencia]:
        return self._repository.list_by_document(documento_id)

    def listar_incidencias(self) -> list[Incidencia]:
        return self._repository.list()

    def existen_criticas_abiertas(self, documento_id: str) -> bool:
        """True si el documento tiene al menos una incidencia con
        severidad CRITICA todavia abierta.

        Consulta de solo lectura -- no bloquea nada por si misma. Quien
        la usa para impedir de verdad que un documento avance
        (Documento Maestro, seccion 8.2: "Incidencias criticas
        abiertas: 0") es application.governance.verificar_documento_
        aprobable.VerificarDocumentoAprobable (Modulo 13), que reutiliza
        el mismo criterio via domain.incidents.entities.
        filtrar_criticas_abiertas() en vez de duplicarlo."""
        return bool(filtrar_criticas_abiertas(self._repository.list_by_document(documento_id)))
