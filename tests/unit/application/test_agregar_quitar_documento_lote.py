"""AgregarDocumentoALote / QuitarDocumentoDeLote (Fase 7). Se agrupan
en un solo archivo porque comparten los mismos fakes y escenarios
complementarios -- mismo criterio de agrupacion que
test_ciclo_de_vida_trabajo.py."""
from __future__ import annotations

import pytest

from application.batches.commands.agregar_documento_a_lote import AgregarDocumentoALote
from application.batches.commands.quitar_documento_de_lote import QuitarDocumentoDeLote
from domain.batches.entities import Lote
from domain.batches.exceptions import BatchNotFoundError, LoteCerradoError
from domain.batches.ports import LoteRepository
from domain.documents.entities import Documento, FormatoDocumento
from domain.documents.exceptions import DocumentNotFoundError
from tests.unit.application._fakes import _FakeAuditLogger, _FakeDocumentRepository

_HASH_VALIDO = "8" * 64


class _FakeLoteRepository(LoteRepository):
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


def _documento(documento_id: str = "doc-1", **overrides) -> Documento:
    datos = {
        "id": documento_id,
        "proyecto_id": "PROY-0001",
        "nombre_original": "politica.pdf",
        "formato": FormatoDocumento.PDF,
        "ruta_origen": "/tmp/x/politica.pdf",
        "ruta_copia_original": "/proyecto/01_originales/abc_politica.pdf",
        "hash_sha256": _HASH_VALIDO,
        "tamano_bytes": 1024,
    }
    datos.update(overrides)
    return Documento(**datos)


def test_agregar_documento_a_lote_inexistente_falla() -> None:
    caso_de_uso = AgregarDocumentoALote(_FakeLoteRepository(), _FakeDocumentRepository([_documento()]), _FakeAuditLogger())
    with pytest.raises(BatchNotFoundError):
        caso_de_uso.execute("no-existe", "doc-1")


def test_agregar_documento_inexistente_falla() -> None:
    lote = Lote(proyecto_id="PROY-0001", nombre="Lote 1")
    caso_de_uso = AgregarDocumentoALote(_FakeLoteRepository([lote]), _FakeDocumentRepository(), _FakeAuditLogger())
    with pytest.raises(DocumentNotFoundError):
        caso_de_uso.execute(lote.id, "no-existe")


def test_agregar_documento_a_lote_cerrado_falla() -> None:
    lote = Lote(proyecto_id="PROY-0001", nombre="Lote 1").cerrar()
    documento = _documento()
    caso_de_uso = AgregarDocumentoALote(_FakeLoteRepository([lote]), _FakeDocumentRepository([documento]), _FakeAuditLogger())
    with pytest.raises(LoteCerradoError):
        caso_de_uso.execute(lote.id, documento.id)


def test_agregar_documento_exitoso() -> None:
    lote = Lote(proyecto_id="PROY-0001", nombre="Lote 1")
    documento = _documento()
    document_repo = _FakeDocumentRepository([documento])
    audit = _FakeAuditLogger()
    caso_de_uso = AgregarDocumentoALote(_FakeLoteRepository([lote]), document_repo, audit)

    resultado = caso_de_uso.execute(lote.id, documento.id)

    assert resultado.lote_id == lote.id
    assert document_repo.get(documento.id).lote_id == lote.id
    assert [e.accion for e in audit.eventos] == ["agregar_documento_a_lote"]


def test_agregar_documento_reemplaza_lote_anterior() -> None:
    lote_1 = Lote(proyecto_id="PROY-0001", nombre="Lote 1")
    lote_2 = Lote(proyecto_id="PROY-0001", nombre="Lote 2")
    documento = _documento(lote_id=lote_1.id)
    document_repo = _FakeDocumentRepository([documento])
    caso_de_uso = AgregarDocumentoALote(_FakeLoteRepository([lote_1, lote_2]), document_repo, _FakeAuditLogger())

    resultado = caso_de_uso.execute(lote_2.id, documento.id)

    assert resultado.lote_id == lote_2.id


def test_agregar_documento_con_lote_de_origen_cerrado_falla() -> None:
    """Hallazgo real de la cuarta auditoria general (2026-08-01):
    `QuitarDocumentoDeLote` ya bloqueaba modificar un lote CERRADO, pero
    `AgregarDocumentoALote` solo validaba el lote DESTINO -- un
    documento se podia sacar en silencio de un lote ya CERRADO con solo
    agregarlo a otro lote ABIERTO. Ahora debe fallar igual que
    `QuitarDocumentoDeLote` lo haria."""
    lote_cerrado = Lote(proyecto_id="PROY-0001", nombre="Lote cerrado").cerrar()
    lote_destino = Lote(proyecto_id="PROY-0001", nombre="Lote destino")
    documento = _documento(lote_id=lote_cerrado.id)
    document_repo = _FakeDocumentRepository([documento])
    caso_de_uso = AgregarDocumentoALote(_FakeLoteRepository([lote_cerrado, lote_destino]), document_repo, _FakeAuditLogger())

    with pytest.raises(LoteCerradoError):
        caso_de_uso.execute(lote_destino.id, documento.id)

    # No debe haber quedado reasignado a mitad de camino.
    assert document_repo.get(documento.id).lote_id == lote_cerrado.id


def test_agregar_documento_con_lote_de_origen_huerfano_no_falla() -> None:
    """El documento referencia un lote de origen que ya no existe (no
    deberia pasar en el flujo normal) -- agregarlo a un lote nuevo debe
    funcionar igual, mismo criterio que
    test_quitar_documento_sin_lote_referenciado_no_falla."""
    lote_destino = Lote(proyecto_id="PROY-0001", nombre="Lote destino")
    documento = _documento(lote_id="lote-inexistente")
    document_repo = _FakeDocumentRepository([documento])
    caso_de_uso = AgregarDocumentoALote(_FakeLoteRepository([lote_destino]), document_repo, _FakeAuditLogger())

    resultado = caso_de_uso.execute(lote_destino.id, documento.id)

    assert resultado.lote_id == lote_destino.id


def test_quitar_documento_inexistente_falla() -> None:
    caso_de_uso = QuitarDocumentoDeLote(_FakeLoteRepository(), _FakeDocumentRepository(), _FakeAuditLogger())
    with pytest.raises(DocumentNotFoundError):
        caso_de_uso.execute("no-existe")


def test_quitar_documento_de_lote_cerrado_falla() -> None:
    lote = Lote(proyecto_id="PROY-0001", nombre="Lote 1").cerrar()
    documento = _documento(lote_id=lote.id)
    caso_de_uso = QuitarDocumentoDeLote(_FakeLoteRepository([lote]), _FakeDocumentRepository([documento]), _FakeAuditLogger())
    with pytest.raises(LoteCerradoError):
        caso_de_uso.execute(documento.id)


def test_quitar_documento_exitoso() -> None:
    lote = Lote(proyecto_id="PROY-0001", nombre="Lote 1")
    documento = _documento(lote_id=lote.id)
    document_repo = _FakeDocumentRepository([documento])
    audit = _FakeAuditLogger()
    caso_de_uso = QuitarDocumentoDeLote(_FakeLoteRepository([lote]), document_repo, audit)

    resultado = caso_de_uso.execute(documento.id)

    assert resultado.lote_id is None
    assert document_repo.get(documento.id).lote_id is None
    assert [e.accion for e in audit.eventos] == ["quitar_documento_de_lote"]


def test_quitar_documento_sin_lote_referenciado_no_falla() -> None:
    """El documento referencia un lote que ya no existe (no deberia
    pasar en el flujo normal) -- quitarlo debe funcionar igual, no
    lanzar BatchNotFoundError."""
    documento = _documento(lote_id="lote-inexistente")
    document_repo = _FakeDocumentRepository([documento])
    caso_de_uso = QuitarDocumentoDeLote(_FakeLoteRepository(), document_repo, _FakeAuditLogger())

    resultado = caso_de_uso.execute(documento.id)

    assert resultado.lote_id is None
