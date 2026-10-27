"""CerrarLote (Fase 7, Documento Maestro seccion 10.1, etapa 14):
libera los documentos VALIDADO que pasan la verificacion de
GovernanceService, bloquea el resto, y cierra el propio Lote."""
from __future__ import annotations

import pytest

from application.batches.commands.cerrar_lote import CerrarLote
from application.governance.service import GovernanceService
from domain.batches.entities import EstadoLote, Lote
from domain.batches.exceptions import BatchNotFoundError, LoteVacioError
from domain.documents.entities import Aprobacion, Documento, EstadoDocumento, FormatoDocumento, TipoProcesamiento
from domain.documents.ports import AprobacionRepository
from domain.incidents.ports import IncidentRepository
from domain.validity.entities import Fuente
from domain.validity.ports import FuenteRepository, VigenciaRepository
from tests.unit.application._fakes import _FakeAuditLogger, _FakeDocumentRepository

_HASH_VALIDO = "2" * 64


class _FakeLoteRepository:
    def __init__(self, lotes: list[Lote] | None = None) -> None:
        self._por_id: dict[str, Lote] = {lote.id: lote for lote in (lotes or [])}

    def save(self, lote: Lote) -> None:
        self._por_id[lote.id] = lote

    def get(self, lote_id: str):
        return self._por_id.get(lote_id)

    def list_by_proyecto(self, proyecto_id: str):
        return [lote for lote in self._por_id.values() if lote.proyecto_id == proyecto_id]

    def list(self):
        return list(self._por_id.values())


class _FakeIncidentRepository(IncidentRepository):
    def save(self, incidencia) -> None:
        pass

    def get(self, incidencia_id: str):
        return None

    def list_by_document(self, documento_id: str):
        return []

    def list(self):
        return []


class _FakeVigenciaRepository(VigenciaRepository):
    def save(self, vigencia) -> None:
        pass

    def get_by_document(self, documento_id: str):
        return None


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


def _governance(fuentes=None, aprobaciones=None, document_repository=None) -> GovernanceService:
    return GovernanceService(
        _FakeIncidentRepository(),
        _FakeVigenciaRepository(),
        document_repository or _FakeDocumentRepository(),
        _FakeFuenteRepository(fuentes),
        _FakeAprobacionRepository(aprobaciones),
    )


def _documento_validado(documento_id: str, lote_id: str, hash_sha256: str) -> Documento:
    documento = Documento(
        id=documento_id,
        proyecto_id="PROY-0001",
        nombre_original="politica.pdf",
        formato=FormatoDocumento.PDF,
        ruta_origen="/tmp/x/politica.pdf",
        ruta_copia_original="/proyecto/01_originales/abc_politica.pdf",
        hash_sha256=hash_sha256,
        tamano_bytes=1024,
        lote_id=lote_id,
    )
    return (
        documento.avanzar_a(EstadoDocumento.INVENTARIADO)
        .clasificar(TipoProcesamiento.EXTRACCION_DIRECTA)
        .avanzar_a(EstadoDocumento.EN_EXTRACCION)
        .completar_extraccion("/proyecto/03_extracciones/doc.md")
        .avanzar_a(EstadoDocumento.EN_REVISION)
        .avanzar_a(EstadoDocumento.REVISADO)
        .avanzar_a(EstadoDocumento.EN_NORMALIZACION)
        .completar_normalizacion("/proyecto/06_normalizados/doc.md")
        .aprobar_para_markdown()
        .generar_markdown(f"/proyecto/07_markdown/{documento_id}.md", "hash-markdown")
        .validar_markdown()
    )


def test_cerrar_lote_inexistente_falla() -> None:
    caso_de_uso = CerrarLote(_FakeLoteRepository(), _FakeDocumentRepository(), _governance(), _FakeAuditLogger())
    with pytest.raises(BatchNotFoundError):
        caso_de_uso.execute("no-existe")


def test_cerrar_lote_vacio_falla() -> None:
    lote = Lote(proyecto_id="PROY-0001", nombre="Lote vacio")
    caso_de_uso = CerrarLote(_FakeLoteRepository([lote]), _FakeDocumentRepository(), _governance(), _FakeAuditLogger())
    with pytest.raises(LoteVacioError):
        caso_de_uso.execute(lote.id)


def test_cerrar_lote_libera_documentos_con_fuente_y_aprobacion() -> None:
    lote = Lote(proyecto_id="PROY-0001", nombre="Lote 1")
    documento = _documento_validado("doc-1", lote.id, _HASH_VALIDO)
    document_repo = _FakeDocumentRepository([documento])
    fuente = Fuente(
        documento_id=documento.id, sistema_origen="portal interno", autoridad="RH", evidencia_consulta="Confirmado."
    )
    aprobacion = Aprobacion(documento_id=documento.id, aprobador="ana@nexom.mx")
    governance = _governance(fuentes=[fuente], aprobaciones=[aprobacion], document_repository=document_repo)
    audit = _FakeAuditLogger()
    caso_de_uso = CerrarLote(_FakeLoteRepository([lote]), document_repo, governance, audit)

    resultado = caso_de_uso.execute(lote.id)

    assert resultado.estado == EstadoLote.CERRADO
    assert document_repo.get(documento.id).estado == EstadoDocumento.LIBERADO
    # Bug real corregido 2026-07-31 (segunda auditoria): antes solo
    # quedaba el resumen agregado ("cerrar_lote"); ahora tambien se
    # audita la resolucion de CADA documento individualmente, con su
    # transicion de estado real -- ver
    # test_cerrar_lote_audita_la_resolucion_de_cada_documento_individualmente
    # para el detalle completo de ambos casos (liberado y bloqueado).
    assert [e.accion for e in audit.eventos] == ["cerrar_lote_documento", "cerrar_lote"]
    assert "1 liberados" in audit.eventos[-1].valor_nuevo


def test_cerrar_lote_bloquea_documentos_sin_fuente_ni_aprobacion() -> None:
    lote = Lote(proyecto_id="PROY-0001", nombre="Lote 1")
    documento = _documento_validado("doc-1", lote.id, _HASH_VALIDO)
    document_repo = _FakeDocumentRepository([documento])
    governance = _governance(document_repository=document_repo)  # sin fuente ni aprobacion
    caso_de_uso = CerrarLote(_FakeLoteRepository([lote]), document_repo, governance, _FakeAuditLogger())

    caso_de_uso.execute(lote.id)

    assert document_repo.get(documento.id).estado == EstadoDocumento.BLOQUEADO


def test_cerrar_lote_audita_la_resolucion_de_cada_documento_individualmente() -> None:
    """Bug real encontrado en la segunda auditoria 2026-07-31: antes,
    CerrarLote solo dejaba un resumen agregado en la auditoria al final
    de execute() -- si document_repository.save() fallara a mitad del
    lote (disco lleno, lock de SQLite), los documentos ya resueltos en
    esa corrida quedaban sin ningun rastro individual. Se agrego un
    evento 'cerrar_lote_documento' por cada documento que SI cambia de
    estado, con su transicion real (valor_anterior -> valor_nuevo), sin
    quitar el resumen agregado final."""
    lote = Lote(proyecto_id="PROY-0001", nombre="Lote 1")
    liberable = _documento_validado("doc-1", lote.id, "8" * 64)
    bloqueable = _documento_validado("doc-2", lote.id, "9" * 64)
    document_repo = _FakeDocumentRepository([liberable, bloqueable])
    fuente = Fuente(
        documento_id=liberable.id, sistema_origen="portal interno", autoridad="RH", evidencia_consulta="Confirmado."
    )
    aprobacion = Aprobacion(documento_id=liberable.id, aprobador="ana@nexom.mx")
    governance = _governance(fuentes=[fuente], aprobaciones=[aprobacion], document_repository=document_repo)
    audit = _FakeAuditLogger()
    caso_de_uso = CerrarLote(_FakeLoteRepository([lote]), document_repo, governance, audit)

    caso_de_uso.execute(lote.id)

    eventos_por_documento = {e.valor_nuevo: e for e in audit.eventos if e.accion == "cerrar_lote_documento"}
    assert len(eventos_por_documento) == 2
    assert eventos_por_documento["liberado"].valor_anterior == "validado"
    assert eventos_por_documento["bloqueado"].valor_anterior == "validado"
    assert [e.accion for e in audit.eventos][-1] == "cerrar_lote"  # el resumen agregado sigue al final.


def test_cerrar_lote_bloquea_documentos_en_etapas_tempranas() -> None:
    lote = Lote(proyecto_id="PROY-0001", nombre="Lote 1")
    documento = Documento(
        id="doc-1",
        proyecto_id="PROY-0001",
        nombre_original="memo.txt",
        formato=FormatoDocumento.TXT,
        ruta_origen="/tmp/x/memo.txt",
        ruta_copia_original="/proyecto/01_originales/abc_memo.txt",
        hash_sha256=_HASH_VALIDO,
        tamano_bytes=10,
        lote_id=lote.id,
    )  # RECIBIDO -- todavia no se toco
    document_repo = _FakeDocumentRepository([documento])
    caso_de_uso = CerrarLote(_FakeLoteRepository([lote]), document_repo, _governance(document_repository=document_repo), _FakeAuditLogger())

    caso_de_uso.execute(lote.id)

    assert document_repo.get(documento.id).estado == EstadoDocumento.BLOQUEADO


def test_cerrar_lote_bloquea_un_documento_observado() -> None:
    # Auditoria 2026-08-24: antes de agregar BLOQUEADO a las
    # transiciones permitidas desde OBSERVADO (domain.documents.
    # entities._transiciones_permitidas), este caso de uso abortaba a
    # mitad de camino con InvalidDocumentStateTransitionError sin
    # capturar en cuanto encontraba un documento en OBSERVADO -- un
    # estado alterno que, igual que BLOQUEADO/DESCARTADO, deberia poder
    # resolverse al cerrar el lote sin excepcion.
    lote = Lote(proyecto_id="PROY-0001", nombre="Lote 1")
    observado = _documento_validado("doc-1", lote.id, _HASH_VALIDO).avanzar_a(EstadoDocumento.OBSERVADO)
    document_repo = _FakeDocumentRepository([observado])
    caso_de_uso = CerrarLote(
        _FakeLoteRepository([lote]), document_repo, _governance(document_repository=document_repo), _FakeAuditLogger()
    )

    resultado = caso_de_uso.execute(lote.id)

    assert resultado.estado == EstadoLote.CERRADO
    assert document_repo.get(observado.id).estado == EstadoDocumento.BLOQUEADO


def test_cerrar_lote_no_toca_documentos_ya_liberados_bloqueados_descartados_u_obsoletos() -> None:
    lote = Lote(proyecto_id="PROY-0001", nombre="Lote 1")
    liberado = _documento_validado("doc-1", lote.id, "3" * 64).liberar()
    bloqueado = _documento_validado("doc-2", lote.id, "4" * 64).avanzar_a(EstadoDocumento.BLOQUEADO)
    descartado = _documento_validado("doc-3", lote.id, "5" * 64).avanzar_a(EstadoDocumento.DESCARTADO)
    document_repo = _FakeDocumentRepository([liberado, bloqueado, descartado])
    caso_de_uso = CerrarLote(
        _FakeLoteRepository([lote]), document_repo, _governance(document_repository=document_repo), _FakeAuditLogger()
    )

    caso_de_uso.execute(lote.id)

    assert document_repo.get(liberado.id).estado == EstadoDocumento.LIBERADO
    assert document_repo.get(bloqueado.id).estado == EstadoDocumento.BLOQUEADO
    assert document_repo.get(descartado.id).estado == EstadoDocumento.DESCARTADO


def test_cerrar_lote_ignora_documentos_de_otros_lotes() -> None:
    lote_1 = Lote(proyecto_id="PROY-0001", nombre="Lote 1")
    lote_2 = Lote(proyecto_id="PROY-0001", nombre="Lote 2")
    del_lote_1 = _documento_validado("doc-1", lote_1.id, "6" * 64)
    del_lote_2 = _documento_validado("doc-2", lote_2.id, "7" * 64)
    document_repo = _FakeDocumentRepository([del_lote_1, del_lote_2])
    caso_de_uso = CerrarLote(
        _FakeLoteRepository([lote_1, lote_2]),
        document_repo,
        _governance(document_repository=document_repo),
        _FakeAuditLogger(),
    )

    caso_de_uso.execute(lote_1.id)

    assert document_repo.get(del_lote_2.id).estado == EstadoDocumento.VALIDADO  # sin tocar
