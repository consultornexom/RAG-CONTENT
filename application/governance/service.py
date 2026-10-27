"""Fachada del contexto Gobernanza (ADR-001, seccion 4: ui solo depende
de application). Modulo 13 (Estados y dependencias) aplica tres reglas
reales (Documento Maestro, seccion 4.7):
1. No aprobar con incidencias criticas abiertas.
2. Bloquear documentos criticos con vigencia desconocida (Modulo 11).
3. No liberar contenido sin fuente, hash y aprobacion (2026-07-28,
   Modulo 12/11) -- ver verificar_documento_liberable().
Quien usa este servicio (RevisarDocumento, AprobarParaMarkdown,
LiberarDocumento, la GUI) sigue llamandolo igual."""
from __future__ import annotations

from domain.documents.ports import AprobacionRepository, DocumentRepository
from domain.incidents.ports import IncidentRepository
from domain.validity.ports import FuenteRepository, VigenciaRepository

from .verificar_documento_aprobable import VerificarDocumentoAprobable
from .verificar_documento_liberable import VerificarDocumentoLiberable


class GovernanceService:
    def __init__(
        self,
        incident_repository: IncidentRepository,
        vigencia_repository: VigenciaRepository,
        document_repository: DocumentRepository,
        fuente_repository: FuenteRepository,
        aprobacion_repository: AprobacionRepository,
    ):
        self._verificar_aprobable = VerificarDocumentoAprobable(
            incident_repository, vigencia_repository, document_repository
        )
        self._verificar_liberable = VerificarDocumentoLiberable(fuente_repository, aprobacion_repository)

    def verificar_documento_aprobable(self, documento_id: str) -> None:
        """Lanza `domain.governance.exceptions.
        IncidenciasCriticasAbiertasError` o `VigenciaDesconocidaError` si
        el documento no puede aprobarse todavia (ya sea para REVISADO o
        para APROBADO_PARA_MARKDOWN -- misma regla, dos puntos de
        control). No devuelve nada si puede."""
        self._verificar_aprobable.verificar(documento_id)

    def verificar_documento_liberable(self, documento_id: str) -> None:
        """Lanza `domain.governance.exceptions.FuenteFaltanteError` o
        `AprobacionFaltanteError` si el documento no puede liberarse
        todavia. No devuelve nada si puede."""
        self._verificar_liberable.verificar(documento_id)
