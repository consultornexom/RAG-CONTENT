"""GenerarInformeIncidencias (Fase 8, Documento Maestro seccion 7.1)."""
from __future__ import annotations

from application.reports.commands.generar_informe_incidencias import GenerarInformeIncidencias
from domain.incidents.entities import EtapaIncidencia, Incidencia, SeveridadIncidencia
from domain.incidents.ports import IncidentRepository
from domain.reports.ports import ReportWriter


class _FakeIncidentRepository(IncidentRepository):
    def __init__(self, incidencias: list[Incidencia] | None = None) -> None:
        self._incidencias = list(incidencias or [])

    def save(self, incidencia: Incidencia) -> None:
        self._incidencias.append(incidencia)

    def get(self, incidencia_id: str):
        return next((i for i in self._incidencias if i.id == incidencia_id), None)

    def list_by_document(self, documento_id: str):
        return [i for i in self._incidencias if i.documento_id == documento_id]

    def list(self):
        return list(self._incidencias)


class _FakeReportWriter(ReportWriter):
    def __init__(self) -> None:
        self.filas = None

    def escribir_inventario(self, filas):
        raise NotImplementedError

    def escribir_procesamiento(self, filas):
        raise NotImplementedError

    def escribir_revision(self, filas):
        raise NotImplementedError

    def escribir_incidencias(self, filas):
        self.filas = filas
        return "/tmp/informe_incidencias.csv"

    def escribir_calidad(self, filas):
        raise NotImplementedError

    def escribir_trazabilidad(self, filas):
        raise NotImplementedError

    def escribir_acta_cierre_lote(self, acta):
        raise NotImplementedError


def _incidencia(**overrides) -> Incidencia:
    datos = {
        "proyecto_id": "PROY-0001",
        "documento_id": "doc-1",
        "etapa": EtapaIncidencia.REVISION,
        "tipo": "cifra_dudosa",
        "severidad": SeveridadIncidencia.ALTA,
        "evidencia": "pagina 3",
        "impacto": "posible dato incorrecto",
    }
    datos.update(overrides)
    return Incidencia(**datos)


def test_incidencia_sin_responsable_asignado() -> None:
    writer = _FakeReportWriter()
    caso_de_uso = GenerarInformeIncidencias(_FakeIncidentRepository([_incidencia()]), writer)

    caso_de_uso.execute()

    fila = writer.filas[0]
    assert fila.responsable == ""
    assert fila.abierta is True
    assert fila.vencida is None


def test_incidencia_con_responsable_y_cerrada() -> None:
    writer = _FakeReportWriter()
    incidencia = (
        _incidencia()
        .asignar("ana")
        .responder("se confirma el dato")
        .decidir("se corrige en la siguiente extraccion", resuelta=True)
        .cerrar("corregido")
    )
    caso_de_uso = GenerarInformeIncidencias(_FakeIncidentRepository([incidencia]), writer)

    caso_de_uso.execute()

    fila = writer.filas[0]
    assert fila.responsable == "ana"
    assert fila.abierta is False


def test_varias_incidencias_una_fila_cada_una() -> None:
    writer = _FakeReportWriter()
    caso_de_uso = GenerarInformeIncidencias(
        _FakeIncidentRepository([_incidencia(documento_id="doc-1"), _incidencia(documento_id="doc-2")]), writer
    )

    caso_de_uso.execute()

    assert len(writer.filas) == 2
