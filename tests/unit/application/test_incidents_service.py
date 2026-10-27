"""IncidentsService y sus casos de uso (Modulo 10). El ciclo de vida en
si (que transiciones admite Incidencia) ya se prueba a fondo en
tests/unit/domain/test_entities_incidencia.py -- aqui se prueba el
cableado: que RegistrarIncidencia valide que el documento exista, que
cada caso de uso registre auditoria, y la consulta
existen_criticas_abiertas() usada a futuro por el Modulo 13.
"""
from __future__ import annotations

import pytest

from application.incidents.service import IncidentsService
from domain.documents.entities import Criticidad, Documento, FormatoDocumento, Prioridad
from domain.documents.exceptions import DocumentNotFoundError
from domain.incidents.entities import EstadoIncidencia, EtapaIncidencia, Incidencia, SeveridadIncidencia
from domain.incidents.exceptions import IncidentNotFoundError
from domain.incidents.ports import IncidentRepository
from tests.unit.application._fakes import _FakeAuditLogger, _FakeDocumentRepository

_HASH_VALIDO = "d" * 64


class _FakeIncidentRepository(IncidentRepository):
    def __init__(self) -> None:
        self._por_id: dict[str, Incidencia] = {}

    def save(self, incidencia: Incidencia) -> None:
        self._por_id[incidencia.id] = incidencia

    def get(self, incidencia_id: str):
        return self._por_id.get(incidencia_id)

    def list_by_document(self, documento_id: str) -> list[Incidencia]:
        return [i for i in self._por_id.values() if i.documento_id == documento_id]

    def list(self) -> list[Incidencia]:
        return list(self._por_id.values())


def _documento(repo: _FakeDocumentRepository, **overrides) -> Documento:
    datos = {
        "proyecto_id": "PROY-0001",
        "nombre_original": "politica.pdf",
        "formato": FormatoDocumento.PDF,
        "ruta_origen": "/tmp/x/politica.pdf",
        "ruta_copia_original": "/proyecto/01_originales/abc_politica.pdf",
        "hash_sha256": _HASH_VALIDO,
        "tamano_bytes": 1024,
        "prioridad": Prioridad.NORMAL,
        "criticidad": Criticidad.NO_CRITICO,
    }
    datos.update(overrides)
    documento = Documento(**datos)
    repo.save(documento)
    return documento


def _servicio() -> tuple[IncidentsService, _FakeDocumentRepository, _FakeIncidentRepository, _FakeAuditLogger]:
    documentos = _FakeDocumentRepository()
    incidencias = _FakeIncidentRepository()
    audit = _FakeAuditLogger()
    servicio = IncidentsService(incidencias, documentos, audit)
    return servicio, documentos, incidencias, audit


def test_registrar_incidencia_sobre_documento_inexistente_falla() -> None:
    servicio, _, _, _ = _servicio()
    with pytest.raises(DocumentNotFoundError):
        servicio.registrar_incidencia(
            proyecto_id="PROY-0001",
            documento_id="no-existe",
            etapa=EtapaIncidencia.REVISION,
            tipo="cifra_dudosa",
            severidad=SeveridadIncidencia.ALTA,
            evidencia="pagina 3",
            impacto="monto del contrato",
        )


def test_registrar_incidencia_exitoso_queda_abierta_y_audita() -> None:
    servicio, documentos, incidencias, audit = _servicio()
    documento = _documento(documentos)

    incidencia = servicio.registrar_incidencia(
        proyecto_id=documento.proyecto_id,
        documento_id=documento.id,
        etapa=EtapaIncidencia.REVISION,
        tipo="cifra_dudosa",
        severidad=SeveridadIncidencia.CRITICA,
        evidencia="La cifra de la pagina 3 no coincide con el original.",
        impacto="Podria invalidar el monto reportado.",
    )

    assert incidencia.estado == EstadoIncidencia.ABIERTA
    assert incidencias.get(incidencia.id) is not None
    assert [e.accion for e in audit.eventos] == ["registrar_incidencia"]


def test_ciclo_completo_a_traves_del_servicio_hasta_cerrada() -> None:
    servicio, documentos, _, audit = _servicio()
    documento = _documento(documentos)

    incidencia = servicio.registrar_incidencia(
        proyecto_id=documento.proyecto_id,
        documento_id=documento.id,
        etapa=EtapaIncidencia.OCR,
        tipo="confianza_baja",
        severidad=SeveridadIncidencia.MEDIA,
        evidencia="Confianza de reconocimiento por debajo del umbral en la pagina 2.",
        impacto="Riesgo de error de transcripcion en una cifra.",
    )

    asignada = servicio.asignar_incidencia(incidencia.id, "ana@nexom.mx")
    assert asignada.estado == EstadoIncidencia.ASIGNADA

    respondida = servicio.responder_incidencia(incidencia.id, "Se revisa la pagina 2 manualmente.")
    assert respondida.estado == EstadoIncidencia.RESPONDIDA

    resuelta = servicio.decidir_incidencia(incidencia.id, "Confirmado correcto, sin cambios.", resuelta=True)
    assert resuelta.estado == EstadoIncidencia.RESUELTA

    cerrada = servicio.cerrar_incidencia(incidencia.id, "Verificado y cerrado.")
    assert cerrada.estado == EstadoIncidencia.CERRADA

    assert servicio.obtener_incidencia(incidencia.id) is not None
    assert servicio.obtener_incidencia(incidencia.id).estado == EstadoIncidencia.CERRADA
    assert [e.accion for e in audit.eventos] == [
        "registrar_incidencia",
        "asignar_incidencia",
        "responder_incidencia",
        "decidir_incidencia",
        "cerrar_incidencia",
    ]


@pytest.mark.parametrize(
    "metodo,args",
    [
        ("asignar_incidencia", ("ana@nexom.mx",)),
        ("responder_incidencia", ("respuesta",)),
        ("decidir_incidencia", ("decision", True)),
        ("cerrar_incidencia", ("cierre",)),
    ],
)
def test_operar_sobre_incidencia_inexistente_falla(metodo: str, args: tuple) -> None:
    servicio, _, _, _ = _servicio()
    with pytest.raises(IncidentNotFoundError):
        getattr(servicio, metodo)("no-existe", *args)


def test_listar_incidencias_de_documento_filtra_por_documento() -> None:
    servicio, documentos, _, _ = _servicio()
    doc_a = _documento(documentos, hash_sha256="a" * 64)
    doc_b = _documento(documentos, hash_sha256="b" * 64)

    servicio.registrar_incidencia(
        proyecto_id=doc_a.proyecto_id,
        documento_id=doc_a.id,
        etapa=EtapaIncidencia.EXTRACCION,
        tipo="contenido_faltante",
        severidad=SeveridadIncidencia.BAJA,
        evidencia="Falta un parrafo.",
        impacto="Menor.",
    )
    servicio.registrar_incidencia(
        proyecto_id=doc_b.proyecto_id,
        documento_id=doc_b.id,
        etapa=EtapaIncidencia.EXTRACCION,
        tipo="contenido_faltante",
        severidad=SeveridadIncidencia.BAJA,
        evidencia="Falta otro parrafo.",
        impacto="Menor.",
    )

    incidencias_a = servicio.listar_incidencias_de_documento(doc_a.id)
    assert len(incidencias_a) == 1
    assert incidencias_a[0].documento_id == doc_a.id
    assert len(servicio.listar_incidencias()) == 2


def test_existen_criticas_abiertas_false_sin_incidencias() -> None:
    servicio, documentos, _, _ = _servicio()
    documento = _documento(documentos)
    assert not servicio.existen_criticas_abiertas(documento.id)


def test_existen_criticas_abiertas_true_con_una_critica_abierta() -> None:
    servicio, documentos, _, _ = _servicio()
    documento = _documento(documentos)
    servicio.registrar_incidencia(
        proyecto_id=documento.proyecto_id,
        documento_id=documento.id,
        etapa=EtapaIncidencia.VIGENCIA,
        tipo="vigencia_desconocida",
        severidad=SeveridadIncidencia.CRITICA,
        evidencia="No se encuentra fecha de vigencia en el documento.",
        impacto="No se puede confirmar si sigue vigente.",
    )
    assert servicio.existen_criticas_abiertas(documento.id)


def test_existen_criticas_abiertas_false_una_vez_cerrada() -> None:
    servicio, documentos, _, _ = _servicio()
    documento = _documento(documentos)
    incidencia = servicio.registrar_incidencia(
        proyecto_id=documento.proyecto_id,
        documento_id=documento.id,
        etapa=EtapaIncidencia.VIGENCIA,
        tipo="vigencia_desconocida",
        severidad=SeveridadIncidencia.CRITICA,
        evidencia="No se encuentra fecha de vigencia en el documento.",
        impacto="No se puede confirmar si sigue vigente.",
    )
    servicio.asignar_incidencia(incidencia.id, "ana@nexom.mx")
    servicio.responder_incidencia(incidencia.id, "Se localiza la vigencia en el anexo.")
    servicio.decidir_incidencia(incidencia.id, "Vigencia confirmada, sin bloqueo.", resuelta=True)
    servicio.cerrar_incidencia(incidencia.id, "Cerrado, vigencia confirmada.")

    assert not servicio.existen_criticas_abiertas(documento.id)


def test_existen_criticas_abiertas_false_si_la_critica_esta_bloqueada_pero_cerrada() -> None:
    """Una incidencia critica BLOQUEADA sigue contando como abierta
    hasta que se cierra formalmente -- bloquear no es lo mismo que
    resolver, pero tampoco es lo mismo que dejarla sin decidir."""
    servicio, documentos, _, _ = _servicio()
    documento = _documento(documentos)
    incidencia = servicio.registrar_incidencia(
        proyecto_id=documento.proyecto_id,
        documento_id=documento.id,
        etapa=EtapaIncidencia.VIGENCIA,
        tipo="vigencia_desconocida",
        severidad=SeveridadIncidencia.CRITICA,
        evidencia="No se encuentra fecha de vigencia en el documento.",
        impacto="No se puede confirmar si sigue vigente.",
    )
    servicio.asignar_incidencia(incidencia.id, "ana@nexom.mx")
    servicio.responder_incidencia(incidencia.id, "No se localiza la vigencia en ninguna fuente disponible.")
    servicio.decidir_incidencia(incidencia.id, "No se puede avanzar sin confirmar vigencia.", resuelta=False)

    assert servicio.existen_criticas_abiertas(documento.id)  # BLOQUEADA todavia cuenta como abierta

    servicio.cerrar_incidencia(incidencia.id, "Se cierra tras escalar; el documento sigue bloqueado aparte.")
    assert not servicio.existen_criticas_abiertas(documento.id)
