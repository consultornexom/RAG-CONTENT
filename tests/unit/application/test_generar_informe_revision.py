"""GenerarInformeRevision (Fase 8, Documento Maestro seccion 7.1)."""
from __future__ import annotations

from application.reports.commands.generar_informe_revision import GenerarInformeRevision
from domain.documents.entities import Documento, FormatoDocumento, Revision
from domain.documents.ports import RevisionRepository
from domain.reports.ports import ReportWriter
from tests.unit.application._fakes import _FakeDocumentRepository

_HASH = "1" * 64


class _FakeRevisionRepository(RevisionRepository):
    def __init__(self, revisiones: list[Revision] | None = None) -> None:
        self._revisiones = list(revisiones or [])

    def save(self, revision: Revision) -> None:
        self._revisiones.append(revision)

    def list_by_document(self, documento_id: str):
        return [r for r in self._revisiones if r.documento_id == documento_id]


class _FakeReportWriter(ReportWriter):
    def __init__(self) -> None:
        self.filas = None

    def escribir_inventario(self, filas):
        raise NotImplementedError

    def escribir_procesamiento(self, filas):
        raise NotImplementedError

    def escribir_revision(self, filas):
        self.filas = filas
        return "/tmp/informe_revision.csv"

    def escribir_incidencias(self, filas):
        raise NotImplementedError

    def escribir_calidad(self, filas):
        raise NotImplementedError

    def escribir_trazabilidad(self, filas):
        raise NotImplementedError

    def escribir_acta_cierre_lote(self, acta):
        raise NotImplementedError


def _documento(documento_id: str) -> Documento:
    return Documento(
        id=documento_id,
        proyecto_id="PROY-0001",
        nombre_original="politica.pdf",
        formato=FormatoDocumento.PDF,
        ruta_origen="/tmp/x/politica.pdf",
        ruta_copia_original="/proyecto/01_originales/abc_politica.pdf",
        hash_sha256=_HASH,
        tamano_bytes=1024,
    )


def test_documento_sin_revisiones_no_aporta_filas() -> None:
    writer = _FakeReportWriter()
    caso_de_uso = GenerarInformeRevision(_FakeDocumentRepository([_documento("doc-1")]), _FakeRevisionRepository(), writer)

    caso_de_uso.execute()

    assert writer.filas == []


def test_documento_con_varias_revisiones_aporta_una_fila_por_cada_una() -> None:
    writer = _FakeReportWriter()
    revision_1 = Revision(documento_id="doc-1", revisor="ana", comentario="ok", incidencias_detectadas=["inc-1"])
    revision_2 = Revision(documento_id="doc-1", revisor="luis", comentario="revisar tabla")
    caso_de_uso = GenerarInformeRevision(
        _FakeDocumentRepository([_documento("doc-1")]), _FakeRevisionRepository([revision_1, revision_2]), writer
    )

    caso_de_uso.execute()

    assert len(writer.filas) == 2
    assert writer.filas[0].revisor == "ana"
    assert writer.filas[0].incidencias_detectadas == 1
    assert writer.filas[1].comentario == "revisar tabla"
