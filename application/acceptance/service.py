"""Fachada del contexto Pruebas de aceptacion (Fase 9). Un solo metodo
-- mismo criterio que el puerto (`domain.acceptance.ports.
InformeAceptacionWriter`): cada corrida produce exactamente un
`InformeAceptacion`, no hace falta componer varios casos de uso como en
`BatchesService`/`ReportsService`."""
from __future__ import annotations

from pathlib import Path

from application.batches.service import BatchesService
from application.documents.service import DocumentsService
from application.incidents.service import IncidentsService
from application.reports.service import ReportsService
from application.validity.service import ValidityService
from domain.acceptance.entities import InformeAceptacion

from .commands.ejecutar_pruebas_aceptacion import EjecutarPruebasDeAceptacion


class AcceptanceService:
    def __init__(
        self,
        documents: DocumentsService,
        validity: ValidityService,
        incidents: IncidentsService,
        batches: BatchesService,
        reports: ReportsService,
        proyecto_id: str,
    ):
        self._ejecutar = EjecutarPruebasDeAceptacion(documents, validity, incidents, batches, reports, proyecto_id)

    def ejecutar_pruebas_de_aceptacion(self, corpus_dir: Path) -> InformeAceptacion:
        return self._ejecutar.execute(corpus_dir)
