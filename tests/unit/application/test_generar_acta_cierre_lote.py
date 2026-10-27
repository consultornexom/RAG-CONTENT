"""GenerarActaCierreLote (Fase 8, Documento Maestro seccion 7.1: "Acta
de cierre de lote"; seccion 10.1, etapa 14: "firmar acta y exportar")."""
from __future__ import annotations

import pytest

from application.governance.service import GovernanceService
from application.reports.commands.generar_acta_cierre_lote import GenerarActaCierreLote
from domain.batches.exceptions import BatchNotFoundError
from domain.batches.entities import Lote
from domain.documents.entities import Aprobacion, Documento, EstadoDocumento, FormatoDocumento
from domain.documents.ports import AprobacionRepository, DocumentRepository
from domain.incidents.ports import IncidentRepository
from domain.reports.exceptions import LoteNoCerradoParaActaError
from domain.reports.ports import ReportWriter
from domain.validity.entities import Fuente
from domain.validity.ports import FuenteRepository, VigenciaRepository
from tests.unit.application._fakes import _FakeDocumentRepository

_HASH = "4" * 64


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

    def list_by_document(self, documento_id: str):
        return [a for a in self._aprobaciones if a.documento_id == documento_id]


class _FakeReportWriter(ReportWriter):
    def __init__(self) -> None:
        self.acta = None

    def escribir_inventario(self, filas):
        raise NotImplementedError

    def escribir_procesamiento(self, filas):
        raise NotImplementedError

    def escribir_revision(self, filas):
        raise NotImplementedError

    def escribir_incidencias(self, filas):
        raise NotImplementedError

    def escribir_calidad(self, filas):
        raise NotImplementedError

    def escribir_trazabilidad(self, filas):
        raise NotImplementedError

    def escribir_acta_cierre_lote(self, acta):
        self.acta = acta
        return f"/tmp/acta_cierre_lote_{acta.lote_id}.md"


def _documento(
    documento_id: str, lote_id: str, estado: EstadoDocumento, ruta_markdown: str | None = None
) -> Documento:
    return Documento(
        id=documento_id,
        proyecto_id="PROY-0001",
        nombre_original="doc.pdf",
        formato=FormatoDocumento.PDF,
        ruta_origen="/tmp/x/doc.pdf",
        ruta_copia_original="/proyecto/01_originales/abc_doc.pdf",
        hash_sha256=_HASH,
        tamano_bytes=10,
        lote_id=lote_id,
        estado=estado,
        ruta_markdown=ruta_markdown,
    )


def _governance(
    fuentes: list[Fuente] | None = None,
    aprobaciones: list[Aprobacion] | None = None,
    document_repository: DocumentRepository | None = None,
    aprobacion_repository: AprobacionRepository | None = None,
) -> GovernanceService:
    return GovernanceService(
        _FakeIncidentRepository(),
        _FakeVigenciaRepository(),
        document_repository or _FakeDocumentRepository(),
        _FakeFuenteRepository(fuentes),
        aprobacion_repository if aprobacion_repository is not None else _FakeAprobacionRepository(aprobaciones),
    )


def test_lote_inexistente_falla() -> None:
    caso_de_uso = GenerarActaCierreLote(
        _FakeLoteRepository(), _FakeDocumentRepository(), _FakeAprobacionRepository(), _governance(), _FakeReportWriter()
    )
    with pytest.raises(BatchNotFoundError):
        caso_de_uso.execute("no-existe")


def test_lote_abierto_falla() -> None:
    lote = Lote(proyecto_id="PROY-0001", nombre="Lote 1")
    caso_de_uso = GenerarActaCierreLote(
        _FakeLoteRepository([lote]),
        _FakeDocumentRepository(),
        _FakeAprobacionRepository(),
        _governance(),
        _FakeReportWriter(),
    )
    with pytest.raises(LoteNoCerradoParaActaError):
        caso_de_uso.execute(lote.id)


def test_acta_clasifica_liberados_bloqueados_y_exclusiones() -> None:
    lote = Lote(proyecto_id="PROY-0001", nombre="Lote 1").cerrar()
    liberado = _documento("doc-1", lote.id, EstadoDocumento.LIBERADO)
    bloqueado = _documento("doc-2", lote.id, EstadoDocumento.BLOQUEADO)
    descartado = _documento("doc-3", lote.id, EstadoDocumento.DESCARTADO)
    document_repo = _FakeDocumentRepository([liberado, bloqueado, descartado])
    aprobacion_repo = _FakeAprobacionRepository([Aprobacion(documento_id="doc-1", aprobador="ana")])
    writer = _FakeReportWriter()
    governance = _governance(document_repository=document_repo, aprobacion_repository=aprobacion_repo)
    caso_de_uso = GenerarActaCierreLote(_FakeLoteRepository([lote]), document_repo, aprobacion_repo, governance, writer)

    ruta = caso_de_uso.execute(lote.id)

    assert ruta == f"/tmp/acta_cierre_lote_{lote.id}.md"
    assert writer.acta.liberados == ["doc-1"]
    assert writer.acta.bloqueados == ["doc-2"]
    assert writer.acta.exclusiones == ["doc-3"]
    assert writer.acta.aprobadores == ["ana"]
    assert len(writer.acta.riesgos) == 1
    # Sin Fuente ni Aprobacion registradas para "doc-2" -- el motivo real
    # es la falta de Fuente (se revisa primero, igual que
    # GovernanceService.verificar_documento_liberable()).
    assert "falta registrar la Fuente" in writer.acta.riesgos[0]
    assert writer.acta.fecha_cierre is not None
    assert writer.acta.version == "v1"


def test_motivo_de_riesgo_distingue_los_tres_casos_reales_de_bloqueo() -> None:
    """Bug real encontrado en la segunda auditoria 2026-07-31 (el acta
    daba el mismo motivo para cualquier bloqueado) y CORREGIDO DE NUEVO
    en la tercera auditoria, mismo dia: el primer arreglo usaba
    `ruta_markdown is not None` como señal de "goberanza fallo", pero
    eso da un falso positivo real -- un documento puede llegar a
    MARKDOWN_GENERADO (que ya fija `ruta_markdown`) sin haber pasado
    todavia por `validar_markdown()`, sin que Fuente/Aprobacion tengan
    nada que ver. La version definitiva pregunta por el PRESENTE (si
    Fuente/Aprobacion faltan de verdad, ahora mismo, via
    GovernanceService), no por una señal indirecta del pasado. Se
    prueban los tres casos reales por separado."""
    lote = Lote(proyecto_id="PROY-0001", nombre="Lote 1").cerrar()
    sin_fuente = _documento("doc-sin-fuente", lote.id, EstadoDocumento.BLOQUEADO)
    sin_aprobacion = _documento("doc-sin-aprobacion", lote.id, EstadoDocumento.BLOQUEADO)
    # Caso que rompia el primer arreglo: llego a MARKDOWN_GENERADO (tiene
    # ruta_markdown) pero nunca se valido -- y YA tiene Fuente y
    # Aprobacion registradas, asi que el motivo real no puede ser
    # "revisar Fuente/Aprobacion".
    validado_a_medias = _documento(
        "doc-sin-validar", lote.id, EstadoDocumento.BLOQUEADO, ruta_markdown="/proyecto/07_markdown/doc.md"
    )
    document_repo = _FakeDocumentRepository([sin_fuente, sin_aprobacion, validado_a_medias])
    fuentes = [
        Fuente(documento_id="doc-sin-aprobacion", sistema_origen="x", autoridad="y", evidencia_consulta="z"),
        Fuente(documento_id="doc-sin-validar", sistema_origen="x", autoridad="y", evidencia_consulta="z"),
    ]
    aprobaciones = [
        Aprobacion(documento_id="doc-sin-validar", aprobador="ana@nexom.mx"),
    ]
    fuente_repo = _FakeFuenteRepository(fuentes)
    aprobacion_repo = _FakeAprobacionRepository(aprobaciones)
    governance = GovernanceService(
        _FakeIncidentRepository(), _FakeVigenciaRepository(), document_repo, fuente_repo, aprobacion_repo
    )
    writer = _FakeReportWriter()
    caso_de_uso = GenerarActaCierreLote(_FakeLoteRepository([lote]), document_repo, aprobacion_repo, governance, writer)

    caso_de_uso.execute(lote.id)

    riesgos_por_id = {riesgo.split(":")[0]: riesgo for riesgo in writer.acta.riesgos}
    assert "falta registrar la Fuente" in riesgos_por_id["doc-sin-fuente"]
    assert "falta registrar la Aprobacion" in riesgos_por_id["doc-sin-aprobacion"]
    assert "ya tiene Fuente y Aprobacion registradas" in riesgos_por_id["doc-sin-validar"]
    assert "no llego a completarse la validacion" in riesgos_por_id["doc-sin-validar"]


def test_acta_ignora_documentos_de_otro_lote() -> None:
    lote_1 = Lote(proyecto_id="PROY-0001", nombre="Lote 1").cerrar()
    lote_2 = Lote(proyecto_id="PROY-0001", nombre="Lote 2")
    del_otro_lote = _documento("doc-1", lote_2.id, EstadoDocumento.LIBERADO)
    document_repo = _FakeDocumentRepository([del_otro_lote])
    caso_de_uso = GenerarActaCierreLote(
        _FakeLoteRepository([lote_1, lote_2]),
        document_repo,
        _FakeAprobacionRepository(),
        _governance(document_repository=document_repo),
        _FakeReportWriter(),
    )

    ruta_writer = caso_de_uso.execute(lote_1.id)
    assert ruta_writer  # se genero un acta, aunque vacia
