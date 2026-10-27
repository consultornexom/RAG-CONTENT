"""Caso de uso del Modulo 13 (Estados y dependencias): aplicar de
verdad las reglas de bloqueo de aprobacion (Documento Maestro, seccion
4.7 y 8.2), en vez de solo dejarlas consultables.

Primera regla (2026-07-28): "no aprobar documentos con incidencias
criticas abiertas" -- antes solo consultable via
application.incidents.service.IncidentsService.existen_criticas_abiertas().

Segunda regla (2026-07-28, Modulo 11 ya existe): "bloquear documentos
criticos con vigencia desconocida" -- a diferencia de la primera, esta
SOLO aplica si `Documento.criticidad == CRITICO`; un documento no
critico puede aprobarse aunque su vigencia no se haya registrado
todavia (Documento Maestro, seccion 4.7).

Depende directamente de `domain.incidents.ports.IncidentRepository`,
`domain.validity.ports.VigenciaRepository` y
`domain.documents.ports.DocumentRepository` (los puertos de los OTROS
contextos, no sus fachadas de aplicacion) -- mismo patron de
acoplamiento cruzado ya usado por
application.incidents.commands.registrar_incidencia.RegistrarIncidencia.
domain.governance no importa domain.incidents/domain.documents/
domain.validity en absoluto; ese cruce se resuelve aqui, en
application."""
from __future__ import annotations

from domain.documents.entities import Criticidad
from domain.documents.ports import DocumentRepository
from domain.governance.exceptions import IncidenciasCriticasAbiertasError, VigenciaDesconocidaError
from domain.incidents.entities import filtrar_criticas_abiertas
from domain.incidents.ports import IncidentRepository
from domain.validity.entities import vigencia_desconocida
from domain.validity.ports import VigenciaRepository


class VerificarDocumentoAprobable:
    def __init__(
        self,
        incident_repository: IncidentRepository,
        vigencia_repository: VigenciaRepository,
        document_repository: DocumentRepository,
    ):
        self._incident_repository = incident_repository
        self._vigencia_repository = vigencia_repository
        self._document_repository = document_repository

    def verificar(self, documento_id: str) -> None:
        """No devuelve nada si el documento puede aprobarse. Lanza
        `IncidenciasCriticasAbiertasError`/`VigenciaDesconocidaError` si
        no puede -- quien llama (por ejemplo,
        `application.documents.commands.revisar_documento.RevisarDocumento`)
        debe dejar que la excepcion se propague, no capturarla en
        silencio. Si el documento referenciado no existe, no es
        responsabilidad de esta verificacion reportarlo -- quien llama
        ya lo valido antes de invocarla (mismo principio que
        RegistrarIncidencia con su propia validacion de existencia)."""
        criticas = filtrar_criticas_abiertas(self._incident_repository.list_by_document(documento_id))
        if criticas:
            raise IncidenciasCriticasAbiertasError(documento_id, len(criticas))

        documento = self._document_repository.get(documento_id)
        if documento is not None and documento.criticidad == Criticidad.CRITICO:
            vigencia = self._vigencia_repository.get_by_document(documento_id)
            if vigencia_desconocida(vigencia):
                raise VigenciaDesconocidaError(documento_id)
