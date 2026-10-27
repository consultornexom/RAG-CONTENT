"""GovernanceService (Modulo 13, Documento Maestro seccion 4.6:
"Estados y dependencias" -- "impedir transiciones indebidas"). Tres
reglas reales: no aprobar un documento con incidencias criticas
todavia abiertas (secciones 4.7 y 8.2), ni un documento critico con
vigencia desconocida (seccion 4.7), ni liberar contenido sin fuente y
aprobacion (seccion 4.7, 2026-07-28). El bloqueo real dentro de
RevisarDocumento/AprobarParaMarkdown/LiberarDocumento ya se prueba en
test_revisar_documento.py y test_aprobar_para_markdown.py/
test_liberar_documento.py; aqui se prueba el servicio en si, aislado de
Documento."""
from __future__ import annotations

from datetime import date

import pytest

from application.governance.service import GovernanceService
from domain.documents.entities import Aprobacion, Criticidad, Documento, FormatoDocumento
from domain.documents.ports import AprobacionRepository
from domain.governance.exceptions import (
    AprobacionFaltanteError,
    FuenteFaltanteError,
    IncidenciasCriticasAbiertasError,
    VigenciaDesconocidaError,
)
from domain.incidents.entities import EstadoIncidencia, EtapaIncidencia, Incidencia, SeveridadIncidencia
from domain.incidents.ports import IncidentRepository
from domain.validity.entities import Fuente, Vigencia
from domain.validity.ports import FuenteRepository, VigenciaRepository
from tests.unit.application._fakes import _FakeDocumentRepository

_HASH_VALIDO = "d" * 64


class _FakeIncidentRepository(IncidentRepository):
    def __init__(self, incidencias: list[Incidencia] | None = None) -> None:
        self._incidencias = list(incidencias or [])

    def save(self, incidencia: Incidencia) -> None:
        self._incidencias.append(incidencia)

    def get(self, incidencia_id: str):
        return next((i for i in self._incidencias if i.id == incidencia_id), None)

    def list_by_document(self, documento_id: str) -> list[Incidencia]:
        return [i for i in self._incidencias if i.documento_id == documento_id]

    def list(self) -> list[Incidencia]:
        return list(self._incidencias)


class _FakeVigenciaRepository(VigenciaRepository):
    def __init__(self, vigencias: list[Vigencia] | None = None) -> None:
        self._por_documento: dict[str, Vigencia] = {v.documento_id: v for v in (vigencias or [])}

    def save(self, vigencia: Vigencia) -> None:
        self._por_documento[vigencia.documento_id] = vigencia

    def get_by_document(self, documento_id: str):
        return self._por_documento.get(documento_id)


class _FakeFuenteRepository(FuenteRepository):
    def __init__(self, fuentes: list[Fuente] | None = None) -> None:
        self._por_documento: dict[str, Fuente] = {f.documento_id: f for f in (fuentes or [])}

    def save(self, fuente: Fuente) -> None:
        self._por_documento[fuente.documento_id] = fuente

    def get_by_document(self, documento_id: str):
        return self._por_documento.get(documento_id)


class _FakeAprobacionRepository(AprobacionRepository):
    def __init__(self, aprobaciones: list[Aprobacion] | None = None) -> None:
        self._aprobaciones = list(aprobaciones or [])

    def save(self, aprobacion: Aprobacion) -> None:
        self._aprobaciones.append(aprobacion)

    def list_by_document(self, documento_id: str) -> list[Aprobacion]:
        return [a for a in self._aprobaciones if a.documento_id == documento_id]


def _incidencia(severidad: SeveridadIncidencia, estado: EstadoIncidencia, documento_id: str = "doc-1") -> Incidencia:
    return Incidencia(
        proyecto_id="PROY-0001",
        documento_id=documento_id,
        etapa=EtapaIncidencia.REVISION,
        tipo="cifra_dudosa",
        severidad=severidad,
        evidencia="Evidencia de prueba.",
        impacto="Impacto de prueba.",
        estado=estado,
    )


def _documento(documento_id: str = "doc-1", criticidad: Criticidad = Criticidad.NO_CRITICO) -> Documento:
    return Documento(
        id=documento_id,
        proyecto_id="PROY-0001",
        nombre_original="politica.pdf",
        formato=FormatoDocumento.PDF,
        ruta_origen="/tmp/x/politica.pdf",
        ruta_copia_original="/proyecto/01_originales/abc_politica.pdf",
        hash_sha256=_HASH_VALIDO,
        tamano_bytes=1024,
        criticidad=criticidad,
    )


def _fuente(documento_id: str = "doc-1") -> Fuente:
    return Fuente(
        documento_id=documento_id,
        sistema_origen="portal interno",
        autoridad="Direccion Juridica",
        evidencia_consulta="Confirmado el 2026-07-28.",
    )


def _servicio(
    incidencias: list[Incidencia] | None = None,
    documentos: list[Documento] | None = None,
    vigencias: list[Vigencia] | None = None,
    fuentes: list[Fuente] | None = None,
    aprobaciones: list[Aprobacion] | None = None,
) -> GovernanceService:
    return GovernanceService(
        _FakeIncidentRepository(incidencias),
        _FakeVigenciaRepository(vigencias),
        _FakeDocumentRepository(documentos),
        _FakeFuenteRepository(fuentes),
        _FakeAprobacionRepository(aprobaciones),
    )


def test_documento_sin_incidencias_es_aprobable() -> None:
    servicio = _servicio()
    servicio.verificar_documento_aprobable("doc-1")  # no debe lanzar nada


def test_documento_con_incidencia_critica_abierta_no_es_aprobable() -> None:
    incidencia = _incidencia(SeveridadIncidencia.CRITICA, EstadoIncidencia.ABIERTA)
    servicio = _servicio([incidencia])

    with pytest.raises(IncidenciasCriticasAbiertasError) as excinfo:
        servicio.verificar_documento_aprobable("doc-1")
    assert excinfo.value.documento_id == "doc-1"
    assert excinfo.value.cantidad == 1
    assert "doc-1" in str(excinfo.value)


def test_documento_con_incidencia_critica_cerrada_es_aprobable() -> None:
    incidencia = _incidencia(SeveridadIncidencia.CRITICA, EstadoIncidencia.CERRADA)
    servicio = _servicio([incidencia])

    servicio.verificar_documento_aprobable("doc-1")  # no debe lanzar nada


def test_documento_con_incidencia_no_critica_abierta_es_aprobable() -> None:
    incidencia = _incidencia(SeveridadIncidencia.ALTA, EstadoIncidencia.ABIERTA)
    servicio = _servicio([incidencia])

    servicio.verificar_documento_aprobable("doc-1")  # no debe lanzar nada


def test_solo_cuenta_las_incidencias_del_documento_indicado() -> None:
    incidencia_otro_documento = _incidencia(SeveridadIncidencia.CRITICA, EstadoIncidencia.ABIERTA, documento_id="doc-2")
    servicio = _servicio([incidencia_otro_documento])

    servicio.verificar_documento_aprobable("doc-1")  # no debe lanzar nada


def test_cuenta_multiples_incidencias_criticas_abiertas() -> None:
    incidencias = [
        _incidencia(SeveridadIncidencia.CRITICA, EstadoIncidencia.ABIERTA),
        _incidencia(SeveridadIncidencia.CRITICA, EstadoIncidencia.ASIGNADA),
    ]
    servicio = _servicio(incidencias)

    with pytest.raises(IncidenciasCriticasAbiertasError) as excinfo:
        servicio.verificar_documento_aprobable("doc-1")
    assert excinfo.value.cantidad == 2


# -- Segunda regla: vigencia desconocida en documentos criticos ------


def test_documento_critico_con_vigencia_desconocida_no_es_aprobable() -> None:
    documento = _documento(criticidad=Criticidad.CRITICO)
    servicio = _servicio(documentos=[documento])

    with pytest.raises(VigenciaDesconocidaError) as excinfo:
        servicio.verificar_documento_aprobable("doc-1")
    assert excinfo.value.documento_id == "doc-1"
    assert "doc-1" in str(excinfo.value)


def test_documento_critico_sin_vigencia_registrada_no_es_aprobable() -> None:
    # Ausencia total de registro (nunca se llamo a RegistrarVigencia) es
    # el mismo caso que un registro incompleto -- ambos son "desconocida".
    documento = _documento(criticidad=Criticidad.CRITICO)
    servicio = _servicio(documentos=[documento], vigencias=[])

    with pytest.raises(VigenciaDesconocidaError):
        servicio.verificar_documento_aprobable("doc-1")


def test_documento_critico_con_vigencia_completa_es_aprobable() -> None:
    documento = _documento(criticidad=Criticidad.CRITICO)
    vigencia = Vigencia(
        documento_id="doc-1",
        vigente_desde=date(2026, 1, 1),
        vigente_hasta=date(2026, 12, 31),
        autoridad="Direccion Juridica",
    )
    servicio = _servicio(documentos=[documento], vigencias=[vigencia])

    servicio.verificar_documento_aprobable("doc-1")  # no debe lanzar nada


def test_documento_no_critico_con_vigencia_desconocida_es_aprobable() -> None:
    documento = _documento(criticidad=Criticidad.NO_CRITICO)
    servicio = _servicio(documentos=[documento])

    servicio.verificar_documento_aprobable("doc-1")  # no debe lanzar nada


def test_documento_inexistente_no_bloquea_por_vigencia() -> None:
    # No es responsabilidad de esta verificacion reportar documentos
    # inexistentes -- quien llama ya valido su existencia antes.
    servicio = _servicio()

    servicio.verificar_documento_aprobable("no-existe")  # no debe lanzar nada


def test_incidencias_criticas_se_verifican_antes_que_vigencia() -> None:
    # Si un documento critico tiene AMBOS problemas, la excepcion de
    # incidencias criticas debe salir primero (mismo orden que el
    # docstring de VerificarDocumentoAprobable.verificar()).
    documento = _documento(criticidad=Criticidad.CRITICO)
    incidencia = _incidencia(SeveridadIncidencia.CRITICA, EstadoIncidencia.ABIERTA)
    servicio = _servicio(incidencias=[incidencia], documentos=[documento])

    with pytest.raises(IncidenciasCriticasAbiertasError):
        servicio.verificar_documento_aprobable("doc-1")


# -- Tercera regla: no liberar sin fuente y aprobacion ----------------


def test_documento_sin_fuente_no_es_liberable() -> None:
    servicio = _servicio(aprobaciones=[Aprobacion(documento_id="doc-1", aprobador="ana@nexom.mx")])

    with pytest.raises(FuenteFaltanteError) as excinfo:
        servicio.verificar_documento_liberable("doc-1")
    assert excinfo.value.documento_id == "doc-1"


def test_documento_sin_aprobacion_no_es_liberable() -> None:
    servicio = _servicio(fuentes=[_fuente("doc-1")])

    with pytest.raises(AprobacionFaltanteError) as excinfo:
        servicio.verificar_documento_liberable("doc-1")
    assert excinfo.value.documento_id == "doc-1"


def test_documento_con_fuente_y_aprobacion_es_liberable() -> None:
    servicio = _servicio(
        fuentes=[_fuente("doc-1")],
        aprobaciones=[Aprobacion(documento_id="doc-1", aprobador="ana@nexom.mx")],
    )

    servicio.verificar_documento_liberable("doc-1")  # no debe lanzar nada


def test_fuente_faltante_se_verifica_antes_que_aprobacion() -> None:
    # Sin ninguna de las dos, debe salir primero la de fuente -- mismo
    # orden que declara VerificarDocumentoLiberable.verificar().
    servicio = _servicio()

    with pytest.raises(FuenteFaltanteError):
        servicio.verificar_documento_liberable("doc-1")
