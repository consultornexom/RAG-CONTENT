"""GenerarMarkdown (Modulo 12, Documento Maestro seccion 4.6.1):
APROBADO_PARA_MARKDOWN -> MARKDOWN_GENERADO, copia el Markdown vigente
hacia 07_markdown/ y calcula su hash de entrega."""
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import pytest

from application.documents.commands.generar_markdown import GenerarMarkdown
from domain.documents.entities import Documento, EstadoDocumento, FormatoDocumento, TipoProcesamiento
from domain.documents.exceptions import DocumentNotFoundError, InvalidDocumentStateTransitionError
from domain.documents.ports import ExtractionOutputStore
from tests.unit.application._fakes import _FakeAuditLogger, _FakeDocumentRepository

_HASH_VALIDO = "1" * 64


class _FakeOutputStore(ExtractionOutputStore):
    """Escribe de verdad en una carpeta temporal: GenerarMarkdown calcula
    `hash_markdown` sobre los bytes del archivo escrito (incidencia
    2026-09-30), asi que la ruta devuelta tiene que existir."""

    def __init__(self, fin_de_linea: str = "\n") -> None:
        self.guardados: dict[str, str] = {}
        self.carpeta = Path(tempfile.mkdtemp(prefix="fake_07_markdown_"))
        self._fin_de_linea = fin_de_linea

    def guardar(self, documento_id: str, markdown: str) -> str:
        ruta = self.carpeta / f"{documento_id}.md"
        # `fin_de_linea="\r\n"` reproduce lo que hacia en Windows el
        # adaptador anterior (`write_text` en modo texto).
        ruta.write_bytes(markdown.replace("\n", self._fin_de_linea).encode("utf-8"))
        self.guardados[str(ruta)] = markdown
        return str(ruta)


def _documento_aprobado(repo: _FakeDocumentRepository, tmp_path, contenido: str = "# Politica\n\nContenido.") -> Documento:
    ruta_normalizado = tmp_path / "doc.md"
    ruta_normalizado.write_text(contenido, encoding="utf-8")
    documento = Documento(
        proyecto_id="PROY-0001",
        nombre_original="politica.pdf",
        formato=FormatoDocumento.PDF,
        ruta_origen="/tmp/x/politica.pdf",
        ruta_copia_original="/proyecto/01_originales/abc_politica.pdf",
        hash_sha256=_HASH_VALIDO,
        tamano_bytes=1024,
    )
    documento = (
        documento.avanzar_a(EstadoDocumento.INVENTARIADO)
        .clasificar(TipoProcesamiento.EXTRACCION_DIRECTA)
        .avanzar_a(EstadoDocumento.EN_EXTRACCION)
        .completar_extraccion(str(ruta_normalizado))
        .avanzar_a(EstadoDocumento.EN_REVISION)
        .avanzar_a(EstadoDocumento.REVISADO)
        .avanzar_a(EstadoDocumento.EN_NORMALIZACION)
        .completar_normalizacion(str(ruta_normalizado))
        .aprobar_para_markdown()
    )
    repo.save(documento)
    return documento


def test_generar_markdown_documento_inexistente_falla() -> None:
    repo = _FakeDocumentRepository()
    caso_de_uso = GenerarMarkdown(repo, _FakeOutputStore(), _FakeAuditLogger())
    with pytest.raises(DocumentNotFoundError):
        caso_de_uso.execute("no-existe")


def test_generar_markdown_requiere_estado_aprobado_para_markdown() -> None:
    repo = _FakeDocumentRepository()
    documento = Documento(
        proyecto_id="PROY-0001",
        nombre_original="politica.pdf",
        formato=FormatoDocumento.PDF,
        ruta_origen="/tmp/x/politica.pdf",
        ruta_copia_original="/proyecto/01_originales/abc_politica.pdf",
        hash_sha256=_HASH_VALIDO,
        tamano_bytes=1024,
    )  # todavia en RECIBIDO
    repo.save(documento)
    caso_de_uso = GenerarMarkdown(repo, _FakeOutputStore(), _FakeAuditLogger())
    with pytest.raises(InvalidDocumentStateTransitionError):
        caso_de_uso.execute(documento.id)


def test_generar_markdown_exitoso_copia_contenido_y_calcula_hash(tmp_path) -> None:
    repo = _FakeDocumentRepository()
    documento = _documento_aprobado(repo, tmp_path, "# Politica\n\nContenido de prueba.")
    output_store = _FakeOutputStore()
    audit = _FakeAuditLogger()
    caso_de_uso = GenerarMarkdown(repo, output_store, audit)

    generado = caso_de_uso.execute(documento.id)

    assert generado.estado == EstadoDocumento.MARKDOWN_GENERADO
    assert generado.ruta_markdown == str(output_store.carpeta / f"{documento.id}.md")
    assert output_store.guardados[generado.ruta_markdown] == "# Politica\n\nContenido de prueba."
    assert generado.hash_markdown == hashlib.sha256("# Politica\n\nContenido de prueba.".encode("utf-8")).hexdigest()
    assert [e.accion for e in audit.eventos] == ["generar_markdown"]


def test_generar_markdown_no_escribe_nada_si_el_estado_es_incorrecto(tmp_path) -> None:
    # El estado se valida ANTES de leer/escribir -- no debe quedar
    # ningun archivo escrito en el store si la transicion es invalida.
    repo = _FakeDocumentRepository()
    documento = Documento(
        proyecto_id="PROY-0001",
        nombre_original="politica.pdf",
        formato=FormatoDocumento.PDF,
        ruta_origen="/tmp/x/politica.pdf",
        ruta_copia_original="/proyecto/01_originales/abc_politica.pdf",
        hash_sha256=_HASH_VALIDO,
        tamano_bytes=1024,
    )
    repo.save(documento)
    output_store = _FakeOutputStore()
    caso_de_uso = GenerarMarkdown(repo, output_store, _FakeAuditLogger())

    with pytest.raises(InvalidDocumentStateTransitionError):
        caso_de_uso.execute(documento.id)

    assert output_store.guardados == {}


def test_generar_markdown_calcula_el_hash_sobre_los_bytes_realmente_escritos(tmp_path) -> None:
    """Regresion de la incidencia 2026-09-30: lote generado en Windows,
    rechazado entero por RAG STUDIO ("su contenido no coincide con el
    hash declarado"). El adaptador anterior escribia con `write_text` en
    modo texto (Windows traduce "\n" a "\r\n") y el hash se calculaba
    sobre el texto en memoria. Aunque un adaptador transforme los bytes,
    `hash_markdown` debe describir el archivo que se entrega."""
    repo = _FakeDocumentRepository()
    documento = _documento_aprobado(repo, tmp_path, "# Politica\n\nLinea 1.\nLinea 2.\n")
    output_store = _FakeOutputStore(fin_de_linea="\r\n")

    generado = GenerarMarkdown(repo, output_store, _FakeAuditLogger()).execute(documento.id)

    bytes_en_disco = Path(generado.ruta_markdown).read_bytes()
    assert b"\r\n" in bytes_en_disco  # el fake realmente reprodujo la traduccion de Windows
    assert generado.hash_markdown == hashlib.sha256(bytes_en_disco).hexdigest()
