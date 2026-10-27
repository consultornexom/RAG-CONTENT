"""Prueba de regresion deliberada: verifica que TODOS los campos de
Documento sobreviven un ciclo save() -> get() contra una base SQLite
real, no un doble en memoria. Un fallo aqui (por ejemplo, un campo
nuevo agregado a la entidad pero olvidado en
infrastructure.database.document_repository._to_row/_to_entity, como
paso realmente con tipo_procesamiento durante el desarrollo del
Modulo 4) es invisible para las pruebas que usan un repositorio falso
en memoria -- por eso existe esta prueba separada.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from domain.documents.entities import (
    Criticidad,
    Documento,
    EstadoDocumento,
    FormatoDocumento,
    Prioridad,
    TipoProcesamiento,
)
from infrastructure.database.document_repository import SqlAlchemyDocumentRepository
from infrastructure.database.engine import build_engine
from infrastructure.database.migrations import RUTA_LINEA_PROYECTO, upgrade_to_head

RAIZ_PRUEBA = Path("/tmp/rag_content_studio_document_repository_test")


@pytest.fixture()
def repo():
    if RAIZ_PRUEBA.exists():
        shutil.rmtree(RAIZ_PRUEBA)
    RAIZ_PRUEBA.mkdir(parents=True)
    db_path = RAIZ_PRUEBA / "proyecto.db"
    upgrade_to_head(db_path, RUTA_LINEA_PROYECTO)
    engine = build_engine(db_path)
    session = sessionmaker(bind=engine, future=True)()
    yield SqlAlchemyDocumentRepository(session)
    shutil.rmtree(RAIZ_PRUEBA, ignore_errors=True)


def _documento_completo() -> Documento:
    return Documento(
        proyecto_id="PROY-0001",
        nombre_original="politica.pdf",
        formato=FormatoDocumento.PDF,
        ruta_origen="/tmp/origen/politica.pdf",
        ruta_copia_original="/proyecto/01_originales/abc_politica.pdf",
        hash_sha256="a" * 64,
        tamano_bytes=2048,
        prioridad=Prioridad.ALTA,
        criticidad=Criticidad.CRITICO,
        metadatos={"area_propietaria": "rh"},
    )


def test_save_y_get_recuperan_todos_los_campos(repo: SqlAlchemyDocumentRepository) -> None:
    documento = _documento_completo()
    repo.save(documento)

    recuperado = repo.get(documento.id)
    assert recuperado is not None
    assert recuperado.model_dump() == documento.model_dump()


def test_tipo_procesamiento_sobrevive_el_ciclo_completo(repo: SqlAlchemyDocumentRepository) -> None:
    documento = (
        _documento_completo()
        .avanzar_a(EstadoDocumento.INVENTARIADO)
        .clasificar(TipoProcesamiento.EXTRACCION_DIRECTA)
    )
    repo.save(documento)

    recuperado = repo.get(documento.id)
    assert recuperado is not None
    assert recuperado.tipo_procesamiento == TipoProcesamiento.EXTRACCION_DIRECTA


def test_tipo_procesamiento_nulo_sobrevive_el_ciclo(repo: SqlAlchemyDocumentRepository) -> None:
    documento = _documento_completo()  # todavia sin clasificar
    repo.save(documento)

    recuperado = repo.get(documento.id)
    assert recuperado is not None
    assert recuperado.tipo_procesamiento is None


def test_ruta_extraccion_y_advertencias_sobreviven_el_ciclo_completo(
    repo: SqlAlchemyDocumentRepository,
) -> None:
    documento = (
        _documento_completo()
        .avanzar_a(EstadoDocumento.INVENTARIADO)
        .clasificar(TipoProcesamiento.EXTRACCION_DIRECTA)
        .avanzar_a(EstadoDocumento.EN_EXTRACCION)
        .completar_extraccion("/proyecto/03_extracciones/doc.md", ["la pagina 2 no produjo texto"])
    )
    repo.save(documento)

    recuperado = repo.get(documento.id)
    assert recuperado is not None
    assert recuperado.ruta_extraccion == "/proyecto/03_extracciones/doc.md"
    assert recuperado.advertencias_extraccion == ["la pagina 2 no produjo texto"]


def test_ruta_normalizado_y_cambios_sobreviven_el_ciclo_completo(
    repo: SqlAlchemyDocumentRepository,
) -> None:
    """Modulo 9: mismo tipo de fallo que la prueba anterior detecto para
    ruta_extraccion/advertencias_extraccion -- se agrego expresamente
    tras encontrar, con la prueba de humo de Modulo 9, que
    ruta_normalizado/cambios_normalizacion nunca se habian mapeado en
    _to_row/_to_entity ni en DocumentoModel (columnas faltantes)."""
    documento = (
        _documento_completo()
        .avanzar_a(EstadoDocumento.INVENTARIADO)
        .clasificar(TipoProcesamiento.EXTRACCION_DIRECTA)
        .avanzar_a(EstadoDocumento.EN_EXTRACCION)
        .completar_extraccion("/proyecto/03_extracciones/doc.md")
        .avanzar_a(EstadoDocumento.EN_REVISION)
        .avanzar_a(EstadoDocumento.REVISADO)
        .avanzar_a(EstadoDocumento.EN_NORMALIZACION)
        .completar_normalizacion("/proyecto/06_normalizados/doc.md", ["se elimino un pie de pagina"])
    )
    repo.save(documento)

    recuperado = repo.get(documento.id)
    assert recuperado is not None
    assert recuperado.ruta_normalizado == "/proyecto/06_normalizados/doc.md"
    assert recuperado.cambios_normalizacion == ["se elimino un pie de pagina"]


def test_mapa_paginas_y_ruta_revisado_sobreviven_el_ciclo_completo(
    repo: SqlAlchemyDocumentRepository,
) -> None:
    """Modulo 8: mismo tipo de fallo que ya detectaron las dos pruebas
    de arriba para ruta_extraccion/ruta_normalizado -- se agrega de
    entrada, sin esperar a que una prueba de humo lo descubra, ahora
    que ya se conoce el patron de la brecha."""
    documento = (
        _documento_completo()
        .avanzar_a(EstadoDocumento.INVENTARIADO)
        .clasificar(TipoProcesamiento.EXTRACCION_DIRECTA)
        .avanzar_a(EstadoDocumento.EN_EXTRACCION)
        .completar_extraccion("/proyecto/03_extracciones/doc.md", mapa_paginas=[0, 120, 340])
        .corregir("/proyecto/05_revisiones/doc.md")
    )
    repo.save(documento)

    recuperado = repo.get(documento.id)
    assert recuperado is not None
    assert recuperado.mapa_paginas == [0, 120, 340]
    assert recuperado.ruta_revisado == "/proyecto/05_revisiones/doc.md"


def test_rangos_baja_confianza_sobreviven_el_ciclo_completo(
    repo: SqlAlchemyDocumentRepository,
) -> None:
    """Nivel 1 (confianza de OCR, 2026-08-01): mismo tipo de fallo que
    ya detecto la prueba de arriba para mapa_paginas -- se agrega de
    entrada para rangos_baja_confianza (columna
    rangos_baja_confianza_json, migracion a1de6fc9583f)."""
    from domain.documents.ocr_table_reconstruction import RangoBajaConfianza

    documento = (
        _documento_completo()
        .avanzar_a(EstadoDocumento.INVENTARIADO)
        .clasificar(TipoProcesamiento.OCR)
        .avanzar_a(EstadoDocumento.EN_EXTRACCION)
        .completar_extraccion(
            "/proyecto/03_extracciones/doc.md",
            rangos_baja_confianza=[
                RangoBajaConfianza(inicio=10, fin=17, confianza=42.5, texto="dudosa")
            ],
        )
    )
    repo.save(documento)

    recuperado = repo.get(documento.id)
    assert recuperado is not None
    assert recuperado.rangos_baja_confianza == [
        RangoBajaConfianza(inicio=10, fin=17, confianza=42.5, texto="dudosa")
    ]


def test_ruta_markdown_hash_y_advertencias_sobreviven_el_ciclo_completo(
    repo: SqlAlchemyDocumentRepository,
) -> None:
    """Modulo 12: mismo tipo de fallo que las pruebas anteriores para
    ruta_extraccion/ruta_normalizado/mapa_paginas -- se agrega de
    entrada para ruta_markdown/hash_markdown/advertencias_markdown."""
    documento = (
        _documento_completo()
        .avanzar_a(EstadoDocumento.INVENTARIADO)
        .clasificar(TipoProcesamiento.EXTRACCION_DIRECTA)
        .avanzar_a(EstadoDocumento.EN_EXTRACCION)
        .completar_extraccion("/proyecto/03_extracciones/doc.md")
        .avanzar_a(EstadoDocumento.EN_REVISION)
        .avanzar_a(EstadoDocumento.REVISADO)
        .avanzar_a(EstadoDocumento.EN_NORMALIZACION)
        .completar_normalizacion("/proyecto/06_normalizados/doc.md")
        .aprobar_para_markdown()
        .generar_markdown("/proyecto/07_markdown/doc.md", "e" * 64)
        .validar_markdown(["sin encabezados ni tablas"])
    )
    repo.save(documento)

    recuperado = repo.get(documento.id)
    assert recuperado is not None
    assert recuperado.ruta_markdown == "/proyecto/07_markdown/doc.md"
    assert recuperado.hash_markdown == "e" * 64
    assert recuperado.advertencias_markdown == ["sin encabezados ni tablas"]


def test_lote_id_sobrevive_el_ciclo_completo(repo: SqlAlchemyDocumentRepository) -> None:
    """Fase 7 (Lotes): mismo tipo de fallo que las pruebas anteriores --
    se agrega de entrada para lote_id."""
    documento = _documento_completo().asignar_a_lote("LOTE-1")
    repo.save(documento)

    recuperado = repo.get(documento.id)
    assert recuperado is not None
    assert recuperado.lote_id == "LOTE-1"

    quitado = recuperado.quitar_de_lote()
    repo.save(quitado)

    assert repo.get(documento.id).lote_id is None


def test_actualizar_un_documento_existente_persiste_el_cambio(repo: SqlAlchemyDocumentRepository) -> None:
    documento = _documento_completo()
    repo.save(documento)

    actualizado = documento.avanzar_a(EstadoDocumento.INVENTARIADO)
    repo.save(actualizado)

    recuperado = repo.get(documento.id)
    assert recuperado is not None
    assert recuperado.estado == EstadoDocumento.INVENTARIADO


def test_list_by_estado_filtra_contra_una_base_real(repo: SqlAlchemyDocumentRepository) -> None:
    """Regresion contra una base SQLite real (no un doble en memoria) del
    metodo agregado 2026-07-29 para
    application.documents.commands.recuperar_documentos_interrumpidos.
    RecuperarDocumentosInterrumpidos -- mismo motivo que el resto de este
    archivo: un filtro por columna mal escrito (comparar contra el enum
    en vez de `.value`, por ejemplo) es invisible contra un repositorio
    falso en memoria."""
    en_extraccion = (
        _documento_completo()
        .avanzar_a(EstadoDocumento.INVENTARIADO)
        .clasificar(TipoProcesamiento.EXTRACCION_DIRECTA)
        .avanzar_a(EstadoDocumento.EN_EXTRACCION)
    )
    recibido = Documento(
        proyecto_id="PROY-0001",
        nombre_original="otro.pdf",
        formato=FormatoDocumento.PDF,
        ruta_origen="/tmp/origen/otro.pdf",
        ruta_copia_original="/proyecto/01_originales/otro.pdf",
        hash_sha256="b" * 64,
        tamano_bytes=1024,
        prioridad=Prioridad.NORMAL,
        criticidad=Criticidad.NO_CRITICO,
    )
    repo.save(en_extraccion)
    repo.save(recibido)

    encontrados = repo.list_by_estado(EstadoDocumento.EN_EXTRACCION)

    assert [d.id for d in encontrados] == [en_extraccion.id]
    assert repo.list_by_estado(EstadoDocumento.EN_NORMALIZACION) == []
