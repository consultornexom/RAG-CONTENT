"""ValidarMarkdown (Modulo 12): MARKDOWN_GENERADO -> VALIDADO. Verifica
que el Markdown final no este vacio (bloqueante) y registra una
advertencia no bloqueante si no tiene ningun encabezado ni tabla real
(domain.documents.estructura_markdown.tiene_estructura_markdown())."""
from __future__ import annotations

import pytest

from application.documents.commands.validar_markdown import ValidarMarkdown
from domain.documents.entities import Documento, EstadoDocumento, FormatoDocumento, TipoProcesamiento
from domain.documents.exceptions import DocumentNotFoundError, MarkdownVacioError
from tests.unit.application._fakes import _FakeAuditLogger, _FakeDocumentRepository

_HASH_VALIDO = "2" * 64


def _documento_markdown_generado(repo: _FakeDocumentRepository, tmp_path, contenido: str) -> Documento:
    ruta_normalizado = tmp_path / "normalizado.md"
    ruta_normalizado.write_text(contenido, encoding="utf-8")
    ruta_markdown = tmp_path / "final.md"
    ruta_markdown.write_text(contenido, encoding="utf-8")
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
        .generar_markdown(str(ruta_markdown), "hash-de-prueba")
    )
    repo.save(documento)
    return documento


def test_validar_markdown_documento_inexistente_falla() -> None:
    repo = _FakeDocumentRepository()
    caso_de_uso = ValidarMarkdown(repo, _FakeAuditLogger())
    with pytest.raises(DocumentNotFoundError):
        caso_de_uso.execute("no-existe")


def test_validar_markdown_con_encabezado_no_genera_advertencias(tmp_path) -> None:
    repo = _FakeDocumentRepository()
    documento = _documento_markdown_generado(repo, tmp_path, "# Politica\n\nContenido con estructura real.")
    audit = _FakeAuditLogger()
    caso_de_uso = ValidarMarkdown(repo, audit)

    validado = caso_de_uso.execute(documento.id)

    assert validado.estado == EstadoDocumento.VALIDADO
    assert validado.advertencias_markdown == []
    assert [e.accion for e in audit.eventos] == ["validar_markdown"]


def test_validar_markdown_sin_estructura_genera_advertencia_no_bloqueante(tmp_path) -> None:
    repo = _FakeDocumentRepository()
    documento = _documento_markdown_generado(repo, tmp_path, "Un parrafo simple, sin encabezados ni tablas.")
    caso_de_uso = ValidarMarkdown(repo, _FakeAuditLogger())

    validado = caso_de_uso.execute(documento.id)

    assert validado.estado == EstadoDocumento.VALIDADO  # no bloquea
    assert len(validado.advertencias_markdown) == 1
    assert "encabezado" in validado.advertencias_markdown[0].lower()


def test_validar_markdown_vacio_falla(tmp_path) -> None:
    repo = _FakeDocumentRepository()
    documento = _documento_markdown_generado(repo, tmp_path, "   ")
    caso_de_uso = ValidarMarkdown(repo, _FakeAuditLogger())

    with pytest.raises(MarkdownVacioError):
        caso_de_uso.execute(documento.id)

    # No debe mutar el estado si el contenido esta vacio.
    assert repo.get(documento.id).estado == EstadoDocumento.MARKDOWN_GENERADO
