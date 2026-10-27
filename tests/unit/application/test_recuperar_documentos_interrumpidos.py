"""RecuperarDocumentosInterrumpidos (bug real 2026-07-29, ver
application.documents.commands.extraer_documento/normalizar_documento):
repara documentos que ya estaban atascados en EN_EXTRACCION o
EN_NORMALIZACION antes de que esos dos casos de uso ganaran su
try/except de rollback -- mismo criterio y mismo estilo de prueba que
tests/unit/application/test_ciclo_de_vida_trabajo.py usa para
RecuperarTrabajosInterrumpidos (Fase 6)."""
from __future__ import annotations

from application.documents.commands.recuperar_documentos_interrumpidos import RecuperarDocumentosInterrumpidos
from domain.documents.entities import Documento, EstadoDocumento, FormatoDocumento, TipoProcesamiento
from tests.unit.application._fakes import _FakeAuditLogger, _FakeDocumentRepository

_HASH = "d" * 64


def _documento(hash_sha256: str = _HASH, nombre: str = "politica.pdf") -> Documento:
    return Documento(
        proyecto_id="PROY-0001",
        nombre_original=nombre,
        formato=FormatoDocumento.PDF,
        ruta_origen=f"/tmp/origen/{nombre}",
        ruta_copia_original=f"/proyecto/01_originales/{nombre}",
        hash_sha256=hash_sha256,
        tamano_bytes=1024,
    )


def _en_extraccion() -> Documento:
    return (
        _documento(hash_sha256="e" * 64, nombre="a.pdf")
        .avanzar_a(EstadoDocumento.INVENTARIADO)
        .clasificar(TipoProcesamiento.EXTRACCION_DIRECTA)
        .avanzar_a(EstadoDocumento.EN_EXTRACCION)
    )


def _en_normalizacion() -> Documento:
    return (
        _documento(hash_sha256="f" * 64, nombre="b.pdf")
        .avanzar_a(EstadoDocumento.INVENTARIADO)
        .clasificar(TipoProcesamiento.EXTRACCION_DIRECTA)
        .avanzar_a(EstadoDocumento.EN_EXTRACCION)
        .completar_extraccion("/proyecto/03_extracciones/b.md")
        .avanzar_a(EstadoDocumento.EN_REVISION)
        .avanzar_a(EstadoDocumento.REVISADO)
        .avanzar_a(EstadoDocumento.EN_NORMALIZACION)
    )


def test_recupera_documentos_en_extraccion_y_en_normalizacion_a_la_vez() -> None:
    huerfano_extraccion = _en_extraccion()
    huerfano_normalizacion = _en_normalizacion()
    clasificado = _documento(hash_sha256="1" * 64, nombre="c.pdf").avanzar_a(EstadoDocumento.INVENTARIADO).clasificar(
        TipoProcesamiento.EXTRACCION_DIRECTA
    )
    repo = _FakeDocumentRepository([huerfano_extraccion, huerfano_normalizacion, clasificado])
    audit = _FakeAuditLogger()

    recuperados = RecuperarDocumentosInterrumpidos(repo, audit).execute()

    assert {d.id for d in recuperados} == {huerfano_extraccion.id, huerfano_normalizacion.id}
    assert repo.get(huerfano_extraccion.id).estado == EstadoDocumento.CLASIFICADO
    assert repo.get(huerfano_normalizacion.id).estado == EstadoDocumento.REVISADO
    assert repo.get(clasificado.id).estado == EstadoDocumento.CLASIFICADO  # no se toca, no estaba atascado
    assert len(audit.eventos) == 2
    assert all(e.accion == "recuperar_documento_interrumpido" for e in audit.eventos)


def test_no_hace_nada_si_no_hay_documentos_atascados() -> None:
    clasificado = _documento().avanzar_a(EstadoDocumento.INVENTARIADO).clasificar(TipoProcesamiento.EXTRACCION_DIRECTA)
    repo = _FakeDocumentRepository([clasificado])

    recuperados = RecuperarDocumentosInterrumpidos(repo, _FakeAuditLogger()).execute()

    assert recuperados == []
