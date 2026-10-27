"""Prueba de regresion deliberada: verifica que TODOS los campos de
Revision sobreviven un ciclo save() -> list_by_document() contra una
base SQLite real, no un doble en memoria -- mismo motivo que
test_sqlalchemy_incident_repository.py (un campo nuevo olvidado en
_to_row/_to_entity es invisible para las pruebas con un repositorio
falso en memoria).
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from domain.documents.entities import Revision
from infrastructure.database.engine import build_engine
from infrastructure.database.migrations import RUTA_LINEA_PROYECTO, upgrade_to_head
from infrastructure.database.revision_repository import SqlAlchemyRevisionRepository

RAIZ_PRUEBA = Path("/tmp/rag_content_studio_revision_repository_test")


@pytest.fixture()
def repo():
    if RAIZ_PRUEBA.exists():
        shutil.rmtree(RAIZ_PRUEBA)
    RAIZ_PRUEBA.mkdir(parents=True)
    db_path = RAIZ_PRUEBA / "proyecto.db"
    upgrade_to_head(db_path, RUTA_LINEA_PROYECTO)
    engine = build_engine(db_path)
    session = sessionmaker(bind=engine, future=True)()
    yield SqlAlchemyRevisionRepository(session)
    shutil.rmtree(RAIZ_PRUEBA, ignore_errors=True)


def test_save_y_list_by_document_recuperan_todos_los_campos(repo: SqlAlchemyRevisionRepository) -> None:
    revision = Revision(
        documento_id="doc-1",
        revisor="ana@nexom.mx",
        comentario="Se coteja contra el original, todo correcto salvo una cifra.",
        incidencias_detectadas=["inc-1", "inc-2"],
    )
    repo.save(revision)

    recuperadas = repo.list_by_document("doc-1")
    assert len(recuperadas) == 1
    assert recuperadas[0].model_dump() == revision.model_dump()


def test_save_no_sobrescribe_una_revision_existente(repo: SqlAlchemyRevisionRepository) -> None:
    # A diferencia de SqlAlchemyIncidentRepository/SqlAlchemyDocumentRepository
    # (upsert), aqui cada save() inserta una fila nueva -- Revision es
    # un registro inmutable (ver su docstring en domain.documents.entities).
    primera = Revision(documento_id="doc-1", revisor="ana@nexom.mx", comentario="Primera revision.")
    segunda = Revision(documento_id="doc-1", revisor="beto@nexom.mx", comentario="Segunda revision.")
    repo.save(primera)
    repo.save(segunda)

    recuperadas = repo.list_by_document("doc-1")
    assert len(recuperadas) == 2
    assert {r.revisor for r in recuperadas} == {"ana@nexom.mx", "beto@nexom.mx"}


def test_list_by_document_filtra_por_documento_y_ordena_por_fecha(repo: SqlAlchemyRevisionRepository) -> None:
    de_doc_1 = Revision(documento_id="doc-1", revisor="ana@nexom.mx")
    de_doc_2 = Revision(documento_id="doc-2", revisor="beto@nexom.mx")
    repo.save(de_doc_1)
    repo.save(de_doc_2)

    recuperadas = repo.list_by_document("doc-1")
    assert [r.id for r in recuperadas] == [de_doc_1.id]


def test_revision_sin_incidencias_detectadas_recupera_lista_vacia(repo: SqlAlchemyRevisionRepository) -> None:
    revision = Revision(documento_id="doc-1", revisor="ana@nexom.mx")
    repo.save(revision)

    recuperada = repo.list_by_document("doc-1")[0]
    assert recuperada.incidencias_detectadas == []
