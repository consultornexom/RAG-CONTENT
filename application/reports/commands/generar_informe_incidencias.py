"""Caso de uso de Fase 8: "Reporte de incidencias" (Documento Maestro,
seccion 7.1: "Abiertas, cerradas, criticas, vencidas, responsables,
tipos y documentos"). El unico de los siete informes que solo depende
de un repositorio (`IncidentRepository` ya expone `list()` de todo el
proyecto) -- ver `domain.reports.entities.FilaIncidencia.vencida` sobre
por que esa columna queda en `None` en esta version."""
from __future__ import annotations

from domain.incidents.ports import IncidentRepository
from domain.reports.entities import FilaIncidencia
from domain.reports.ports import ReportWriter


class GenerarInformeIncidencias:
    def __init__(self, incident_repository: IncidentRepository, writer: ReportWriter):
        self._incident_repository = incident_repository
        self._writer = writer

    def execute(self) -> str:
        """Devuelve la ruta absoluta del informe escrito."""
        filas = [
            FilaIncidencia(
                incidencia_id=incidencia.id,
                documento_id=incidencia.documento_id,
                etapa=incidencia.etapa.value,
                tipo=incidencia.tipo,
                severidad=incidencia.severidad.value,
                estado=incidencia.estado.value,
                responsable=incidencia.responsable or "",
                abierta=incidencia.esta_abierta(),
            )
            for incidencia in self._incident_repository.list()
        ]
        return self._writer.escribir_incidencias(filas)
