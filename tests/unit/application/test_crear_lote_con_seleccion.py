"""CrearLoteConSeleccionYCerrar y PrevisualizarSeleccionLote (2026-10-03,
NEXOM, Solicitud_Ajustes_RAG_Content_Lotes_y_Portabilidad.pdf, seccion 2):
cubre los criterios de aceptacion de la seleccion de documentos al cerrar
un lote -- seleccion vacia bloqueada, documentos no seleccionados
preservados intactos, un documento ya resuelto en un lote CERRADO
anterior no se puede reasignar (la proteccion de AgregarDocumentoALote
ya existente se mantiene), y la previsualizacion nunca diverge de lo que
el cierre real produce."""
from __future__ import annotations

import pytest

from application.batches.commands.agregar_documento_a_lote import AgregarDocumentoALote
from application.batches.commands.cerrar_lote import CerrarLote
from application.batches.commands.crear_lote import CrearLote
from application.batches.commands.crear_lote_con_seleccion import CrearLoteConSeleccionYCerrar
from application.batches.queries.previsualizar_seleccion_lote import PrevisualizarSeleccionLote
from application.governance.service import GovernanceService
from domain.batches.entities import EstadoLote, Lote
from domain.batches.exceptions import BatchNotFoundError, SeleccionLoteVaciaError
from domain.documents.entities import Aprobacion, Documento, EstadoDocumento, FormatoDocumento, TipoProcesamiento
from domain.documents.exceptions import DocumentNotFoundError
from domain.documents.ports import AprobacionRepository
from domain.incidents.ports import IncidentRepository
from domain.validity.entities import Fuente
from domain.validity.ports import FuenteRepository, VigenciaRepository
from tests.unit.application._fakes import _FakeAuditLogger, _FakeDocumentRepository

_HASH_VALIDO = "1" * 64


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


def _documento_validado(documento_id: str, lote_id: str | None, hash_sha256: str) -> Documento:
    documento = Documento(
        id=documento_id,
        proyecto_id="PROY-0001",
        nombre_original=f"{documento_id}.pdf",
        formato=FormatoDocumento.PDF,
        ruta_origen=f"/tmp/x/{documento_id}.pdf",
        ruta_copia_original=f"/proyecto/01_originales/abc_{documento_id}.pdf",
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


def _caso_de_uso_compuesto(lote_repo, document_repo, governance, audit) -> CrearLoteConSeleccionYCerrar:
    crear = CrearLote(lote_repo, audit)
    agregar = AgregarDocumentoALote(lote_repo, document_repo, audit)
    cerrar = CerrarLote(lote_repo, document_repo, governance, audit)
    return CrearLoteConSeleccionYCerrar(crear, agregar, cerrar)


def test_seleccion_vacia_no_crea_ningun_lote() -> None:
    lote_repo = _FakeLoteRepository()
    document_repo = _FakeDocumentRepository()
    audit = _FakeAuditLogger()
    caso_de_uso = _caso_de_uso_compuesto(lote_repo, document_repo, _governance(document_repository=document_repo), audit)

    with pytest.raises(SeleccionLoteVaciaError):
        caso_de_uso.execute("PROY-0001", "Lote vacio", [])

    assert lote_repo.list() == []  # ningun lote huerfano quedo creado.


def test_crea_y_cierra_el_lote_solo_con_los_documentos_seleccionados() -> None:
    """Caso real del ticket: 25 licenciaturas ya liberadas y entregadas,
    10 diplomados pendientes en el mismo proyecto -- cerrar un lote nuevo
    para los diplomados no debe tocar las licenciaturas en absoluto (ni
    su estado, ni su lote_id, ni nada de su historial)."""
    licenciatura = _documento_validado("licenciatura-1", lote_id=None, hash_sha256="1" * 64).liberar()
    diplomado = _documento_validado("diplomado-1", lote_id=None, hash_sha256="2" * 64)
    document_repo = _FakeDocumentRepository([licenciatura, diplomado])
    fuente = Fuente(
        documento_id=diplomado.id, sistema_origen="portal interno", autoridad="RH", evidencia_consulta="Confirmado."
    )
    aprobacion = Aprobacion(documento_id=diplomado.id, aprobador="ana@nexom.mx")
    governance = _governance(fuentes=[fuente], aprobaciones=[aprobacion], document_repository=document_repo)
    lote_repo = _FakeLoteRepository()
    caso_de_uso = _caso_de_uso_compuesto(lote_repo, document_repo, governance, _FakeAuditLogger())

    lote = caso_de_uso.execute("PROY-0001", "LOTE-DIPLOMADOS", [diplomado.id])

    assert lote.estado == EstadoLote.CERRADO
    diplomado_final = document_repo.get(diplomado.id)
    assert diplomado_final.estado == EstadoDocumento.LIBERADO
    assert diplomado_final.lote_id == lote.id

    # La licenciatura, no seleccionada, queda exactamente igual: mismo
    # estado, mismo lote_id (ninguno -- no se toco), sin excepcion.
    licenciatura_final = document_repo.get(licenciatura.id)
    assert licenciatura_final.estado == EstadoDocumento.LIBERADO
    assert licenciatura_final.lote_id is None


def test_ids_duplicados_en_la_seleccion_se_deduplican() -> None:
    documento = _documento_validado("doc-1", lote_id=None, hash_sha256=_HASH_VALIDO)
    document_repo = _FakeDocumentRepository([documento])
    audit = _FakeAuditLogger()
    caso_de_uso = _caso_de_uso_compuesto(
        _FakeLoteRepository(), document_repo, _governance(document_repository=document_repo), audit
    )

    lote = caso_de_uso.execute("PROY-0001", "Lote 1", [documento.id, documento.id])

    eventos_agregar = [e for e in audit.eventos if e.accion == "agregar_documento_a_lote"]
    assert len(eventos_agregar) == 1  # no se agrega dos veces el mismo documento.
    assert lote.estado == EstadoLote.CERRADO


def test_incluir_un_documento_ya_cerrado_en_otro_lote_falla_sin_reasignarlo() -> None:
    """La proteccion YA EXISTENTE de AgregarDocumentoALote (hallazgo real
    de la cuarta auditoria general, 2026-08-01) se mantiene intacta: un
    documento cuyo lote_id apunta a un lote ya CERRADO no se puede
    arrastrar a un lote nuevo con solo seleccionarlo -- evita exactamente
    el escenario que el ticket quiere prevenir (reasignar sin querer un
    documento ya entregado)."""
    lote_anterior = Lote(proyecto_id="PROY-0001", nombre="Lote anterior", estado=EstadoLote.CERRADO)
    liberado = _documento_validado("doc-1", lote_id=lote_anterior.id, hash_sha256=_HASH_VALIDO).liberar()
    document_repo = _FakeDocumentRepository([liberado])
    lote_repo = _FakeLoteRepository([lote_anterior])
    caso_de_uso = _caso_de_uso_compuesto(
        lote_repo, document_repo, _governance(document_repository=document_repo), _FakeAuditLogger()
    )

    from domain.batches.exceptions import LoteCerradoError

    with pytest.raises(LoteCerradoError):
        caso_de_uso.execute("PROY-0001", "Lote nuevo", [liberado.id])

    # El documento sigue intacto, en su lote original -- la falla a mitad
    # de camino no reasigna nada parcialmente.
    assert document_repo.get(liberado.id).lote_id == lote_anterior.id
    assert document_repo.get(liberado.id).estado == EstadoDocumento.LIBERADO


def test_previsualizar_seleccion_id_inexistente_falla() -> None:
    previsualizar = PrevisualizarSeleccionLote(_FakeDocumentRepository(), _governance())
    with pytest.raises(DocumentNotFoundError):
        previsualizar.execute(["no-existe"])


def test_previsualizar_seleccion_coincide_con_el_cierre_real() -> None:
    """La vista previa reusa clasificar_para_cierre -- aqui se confirma
    que el resultado mostrado antes de confirmar es EXACTAMENTE el que
    CerrarLote produce despues, para los mismos documentos."""
    liberable = _documento_validado("doc-1", lote_id=None, hash_sha256="1" * 64)
    bloqueable = _documento_validado("doc-2", lote_id=None, hash_sha256="2" * 64)
    document_repo = _FakeDocumentRepository([liberable, bloqueable])
    fuente = Fuente(
        documento_id=liberable.id, sistema_origen="portal interno", autoridad="RH", evidencia_consulta="Confirmado."
    )
    aprobacion = Aprobacion(documento_id=liberable.id, aprobador="ana@nexom.mx")
    governance = _governance(fuentes=[fuente], aprobaciones=[aprobacion], document_repository=document_repo)
    previsualizar = PrevisualizarSeleccionLote(document_repo, governance)

    previsto = previsualizar.execute([liberable.id, bloqueable.id])
    assert previsto[0].cumple_requisitos is True
    assert previsto[0].estado_previsto == EstadoDocumento.LIBERADO
    assert previsto[1].cumple_requisitos is False
    assert previsto[1].estado_previsto == EstadoDocumento.BLOQUEADO

    lote_repo = _FakeLoteRepository()
    caso_de_uso = _caso_de_uso_compuesto(lote_repo, document_repo, governance, _FakeAuditLogger())
    caso_de_uso.execute("PROY-0001", "Lote 1", [liberable.id, bloqueable.id])

    assert document_repo.get(liberable.id).estado == previsto[0].estado_previsto
    assert document_repo.get(bloqueable.id).estado == previsto[1].estado_previsto


def test_lote_destino_inexistente_al_agregar_no_aplica_aqui_pero_proyecto_inexistente_no_bloquea_creacion() -> None:
    """CrearLote no valida que el proyecto exista (mismo comportamiento
    que el resto de application.batches.commands.crear_lote -- no se
    cambia aqui); lo que SI se confirma es que, si una seleccion no vacia
    referencia un documento inexistente, la falla es explicita
    (DocumentNotFoundError via AgregarDocumentoALote), nunca un lote
    cerrado con menos miembros de los pedidos sin avisar."""
    lote_repo = _FakeLoteRepository()
    document_repo = _FakeDocumentRepository()
    caso_de_uso = _caso_de_uso_compuesto(
        lote_repo, document_repo, _governance(document_repository=document_repo), _FakeAuditLogger()
    )

    with pytest.raises(DocumentNotFoundError):
        caso_de_uso.execute("PROY-0001", "Lote 1", ["no-existe"])

    # El lote SI quedo creado (la guardia de seleccion vacia ya paso) --
    # documentado en el docstring del caso de uso: sin rollback entre
    # pasos, quien llama puede reintentar sobre este mismo lote.
    lotes = lote_repo.list()
    assert len(lotes) == 1
    assert lotes[0].estado == EstadoLote.ABIERTO


def test_cerrar_lote_con_seleccion_falla_si_el_lote_desaparece_entre_crear_y_cerrar() -> None:
    """Caso extremo, para blindar el mensaje de error: si algo externo
    (otro proceso, un script de mantenimiento) borra el lote justo
    despues de crearlo, CerrarLote debe fallar con BatchNotFoundError, no
    con un error generico -- mismo contrato que ya tiene CerrarLote por
    si solo."""
    documento = _documento_validado("doc-1", lote_id=None, hash_sha256=_HASH_VALIDO)
    document_repo = _FakeDocumentRepository([documento])
    lote_repo = _FakeLoteRepository()

    crear = CrearLote(lote_repo, _FakeAuditLogger())

    class _AgregarYBorrarLote(AgregarDocumentoALote):
        """Envoltorio minimo para simular, en la propia prueba, que algo
        externo borra el lote justo despues de agregarle su unico
        documento -- sin tocar la implementacion real."""

        def execute(self, lote_id: str, documento_id: str) -> Documento:
            resultado = super().execute(lote_id, documento_id)
            lote_repo._por_id.pop(lote_id, None)  # simula el borrado externo
            return resultado

    agregar = _AgregarYBorrarLote(lote_repo, document_repo, _FakeAuditLogger())
    cerrar = CerrarLote(lote_repo, document_repo, _governance(document_repository=document_repo), _FakeAuditLogger())
    caso_de_uso = CrearLoteConSeleccionYCerrar(crear, agregar, cerrar)

    with pytest.raises(BatchNotFoundError):
        caso_de_uso.execute("PROY-0001", "Lote 1", [documento.id])
