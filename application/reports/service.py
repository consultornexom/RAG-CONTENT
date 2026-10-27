"""Fachada del contexto Reportes (ADR-001, seccion 4: ui solo depende de
application). Documento Maestro, seccion 7.1: siete documentos --
`generar_todos_los_informes()` es una conveniencia para un futuro boton
unico de la GUI (Fase 11, "generar toda la documentacion del proyecto"),
sin que ningun caso de uso individual dependa de ella."""
from __future__ import annotations

from application.governance.service import GovernanceService
from domain.batches.ports import LoteRepository
from domain.documents.ports import AprobacionRepository, DocumentRepository, RevisionRepository
from domain.incidents.ports import IncidentRepository
from domain.jobs.ports import TrabajoRepository
from domain.reports.ports import ReportWriter
from domain.validity.ports import VigenciaRepository

from .commands.generar_acta_cierre_lote import GenerarActaCierreLote
from .commands.generar_informe_calidad import GenerarInformeCalidad
from .commands.generar_informe_incidencias import GenerarInformeIncidencias
from .commands.generar_informe_inventario import GenerarInformeInventario
from .commands.generar_informe_procesamiento import GenerarInformeProcesamiento
from .commands.generar_informe_revision import GenerarInformeRevision
from .commands.generar_informe_trazabilidad import GenerarInformeTrazabilidad


class ReportsService:
    def __init__(
        self,
        document_repository: DocumentRepository,
        vigencia_repository: VigenciaRepository,
        trabajo_repository: TrabajoRepository,
        revision_repository: RevisionRepository,
        incident_repository: IncidentRepository,
        aprobacion_repository: AprobacionRepository,
        lote_repository: LoteRepository,
        governance: GovernanceService,
        writer: ReportWriter,
    ):
        self._generar_inventario = GenerarInformeInventario(document_repository, vigencia_repository, writer)
        self._generar_procesamiento = GenerarInformeProcesamiento(document_repository, trabajo_repository, writer)
        self._generar_revision = GenerarInformeRevision(document_repository, revision_repository, writer)
        self._generar_incidencias = GenerarInformeIncidencias(incident_repository, writer)
        self._generar_calidad = GenerarInformeCalidad(document_repository, governance, writer)
        self._generar_trazabilidad = GenerarInformeTrazabilidad(document_repository, aprobacion_repository, writer)
        self._generar_acta = GenerarActaCierreLote(
            lote_repository, document_repository, aprobacion_repository, governance, writer
        )

    def generar_informe_inventario(self) -> str:
        return self._generar_inventario.execute()

    def generar_informe_procesamiento(self) -> str:
        return self._generar_procesamiento.execute()

    def generar_informe_revision(self) -> str:
        return self._generar_revision.execute()

    def generar_informe_incidencias(self) -> str:
        return self._generar_incidencias.execute()

    def generar_informe_calidad(self) -> str:
        return self._generar_calidad.execute()

    def generar_informe_trazabilidad(self) -> str:
        return self._generar_trazabilidad.execute()

    def generar_acta_cierre_lote(self, lote_id: str) -> str:
        return self._generar_acta.execute(lote_id)

    def generar_todos_los_informes(self) -> dict[str, str]:
        """Genera los seis informes de todo el proyecto (sin incluir el
        acta de cierre de lote, que exige un `lote_id` concreto) y
        devuelve un diccionario {nombre_informe: ruta_absoluta}."""
        return {
            "inventario": self.generar_informe_inventario(),
            "procesamiento": self.generar_informe_procesamiento(),
            "revision": self.generar_informe_revision(),
            "incidencias": self.generar_informe_incidencias(),
            "calidad": self.generar_informe_calidad(),
            "trazabilidad": self.generar_informe_trazabilidad(),
        }
