"""Prueba de regresion deliberada: verifica que TODOS los campos de
Aprobacion sobreviven un ciclo save() -> list_by_document() contra una
base SQLite real, no un doble en memoria -- mismo motivo que
test_sqlalchemy_revision_repository.py.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from domain.documents.entities import Aprobacion
from infrastructure.database.approval_repository import SqlAlchemyAprobacionRepository
from infrastructure.database.engine import build_engine
from infrastructure.database.migrations import RUTA_LINEA_PROYECTO, upgrade_to_head

RAIZ_PRUEBA = Path("/tmp/rag_content_studio_approval_repository_test")


@pytest.fixture()
def repo():
    if RAIZ_PRUEBA.exists():
        shutil.rmtree(RAIZ_PRUEBA)
    RAIZ_PRUEBA.mkdir(parents=True)
    db_path = RAIZ_PRUEBA / "proyecto.db"
    upgrade_to_head(db_path, RUTA_LINEA_PROYECTO)
    engine = build_engine(db_path)
    session = sessionmaker(bind=engine, future=True)()
    yield SqlAlchemyAprobacionRepository(session)
    shutil.rmtree(RAIZ_PRUEBA, ignore_errors=True)


def test_save_y_list_by_document_recuperan_todos_los_campos(repo: SqlAlchemyAprobacionRepository) -> None:
    aprobacion = Aprobacion(documento_id="doc-1", aprobador="ana@nexom.mx", comentario="Todo en orden.")
    repo.save(aprobacion)

    recuperadas = repo.list_by_document("doc-1")
    assert len(recuperadas) == 1
    assert recuperadas[0].model_dump() == aprobacion.model_dump()


def test_save_no_sobrescribe_una_aprobacion_existente(repo: SqlAlchemyAprobacionRepository) -> None:
    # Igual que Revision, cada save() inserta una fila nueva --
    # Aprobacion es un registro inmutable (ver su docstring en
    # domain.documents.entities).
    primera = Aprobacion(documento_id="doc-1", aprobador="ana@nexom.mx")
    segunda = Aprobacion(documento_id="doc-1", aprobador="beto@nexom.mx")
    repo.save(primera)
    repo.save(segunda)

    recuperadas = repo.list_by_document("doc-1")
    assert len(recuperadas) == 2
    assert {a.aprobador for a in recuperadas} == {"ana@nexom.mx", "beto@nexom.mx"}


def test_list_by_document_filtra_por_documento(repo: SqlAlchemyAprobacionRepository) -> None:
    de_doc_1 = Aprobacion(documento_id="doc-1", aprobador="ana@nexom.mx")
    de_doc_2 = Aprobacion(documento_id="doc-2", aprobador="beto@nexom.mx")
    repo.save(de_doc_1)
    repo.save(de_doc_2)

    recuperadas = repo.list_by_document("doc-1")
    assert [a.id for a in recuperadas] == [de_doc_1.id]


def test_list_by_document_sin_aprobaciones_es_lista_vacia(repo: SqlAlchemyAprobacionRepository) -> None:
    assert repo.list_by_document("no-existe") == []
