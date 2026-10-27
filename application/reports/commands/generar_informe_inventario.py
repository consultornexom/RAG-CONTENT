"""Caso de uso de Fase 8: "Informe de inventario" (Documento Maestro,
seccion 7.1: "Recibidos, formatos, areas, prioridades, duplicados,
vigencias y estados"). Sin columna de duplicados -- ver el docstring de
`domain.reports.entities.FilaInventario` sobre por que ese numero esta
garantizado en 0 por construccion.

Depende directamente de `domain.validity.ports.VigenciaRepository` (el
puerto del otro contexto, no su fachada) -- mismo patron de acoplamiento
cruzado ya usado por `GenerarManifiesto`/`RegistrarIncidencia`."""
from __future__ import annotations

from datetime import datetime, timezone

from domain.documents.entities import Documento
from domain.documents.ports import DocumentRepository
from domain.reports.entities import FilaInventario
from domain.reports.ports import ReportWriter
from domain.validity.entities import vigencia_desconocida
from domain.validity.ports import VigenciaRepository


def _vigencia_str(documento_id: str, vigencia_repository: VigenciaRepository) -> str:
    vigencia = vigencia_repository.get_by_document(documento_id)
    if vigencia is None or vigencia_desconocida(vigencia):
        return "desconocida"
    if vigencia.sin_vencimiento:
        return "sin_vencimiento"
    hoy = datetime.now(timezone.utc).date()
    return "vigente" if vigencia.esta_vigente_en(hoy) else "vencida"


def _fila_de(documento: Documento, vigencia_repository: VigenciaRepository) -> FilaInventario:
    return FilaInventario(
        documento_id=documento.id,
        nombre_original=documento.nombre_original,
        formato=documento.formato.value,
        area_propietaria=documento.metadatos.get("area_propietaria", ""),
        prioridad=documento.prioridad.value,
        criticidad=documento.criticidad.value,
        estado=documento.estado.value,
        vigencia=_vigencia_str(documento.id, vigencia_repository),
    )


class GenerarInformeInventario:
    def __init__(
        self, document_repository: DocumentRepository, vigencia_repository: VigenciaRepository, writer: ReportWriter
    ):
        self._document_repository = document_repository
        self._vigencia_repository = vigencia_repository
        self._writer = writer

    def execute(self) -> str:
        """Devuelve la ruta absoluta del informe escrito. Incluye todos
        los documentos del proyecto, sin importar su estado -- a
        diferencia del manifiesto (Modulo 12), este informe es de
        inventario completo, no de entrega."""
        filas = [_fila_de(d, self._vigencia_repository) for d in self._document_repository.list()]
        return self._writer.escribir_inventario(filas)
