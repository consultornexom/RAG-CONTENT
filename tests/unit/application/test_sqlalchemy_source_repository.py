"""Prueba de regresion deliberada: verifica que TODOS los campos de
Fuente sobreviven un ciclo save() -> get_by_document() contra una base
SQLite real -- mismo motivo que test_sqlalchemy_incident_repository.py."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from domain.validity.entities import Fuente
from infrastructure.database.engine import build_engine
from infrastructure.database.migrations import RUTA_LINEA_PROYECTO, upgrade_to_head
from infrastructure.database.source_repository import SqlAlchemyFuenteRepository

RAIZ_PRUEBA = Path("/tmp/rag_content_studio_source_repository_test")


@pytest.fixture()
def repo():
    if RAIZ_PRUEBA.exists():
        shutil.rmtree(RAIZ_PRUEBA)
    RAIZ_PRUEBA.mkdir(parents=True)
    db_path = RAIZ_PRUEBA / "proyecto.db"
    upgrade_to_head(db_path, RUTA_LINEA_PROYECTO)
    engine = build_engine(db_path)
    session = sessionmaker(bind=engine, future=True)()
    yield SqlAlchemyFuenteRepository(session)
    shutil.rmtree(RAIZ_PRUEBA, ignore_errors=True)


def _fuente() -> Fuente:
    return Fuente(
        documento_id="doc-1",
        sistema_origen="portal de normatividad interna",
        autoridad="Direccion Juridica",
        evidencia_consulta="Consultado en https://intranet/normativa el 2026-07-28",
    )


def test_save_y_get_by_document_recuperan_todos_los_campos(repo: SqlAlchemyFuenteRepository) -> None:
    fuente = _fuente()
    repo.save(fuente)

    recuperada = repo.get_by_document(fuente.documento_id)
    assert recuperada is not None
    assert recuperada.model_dump() == fuente.model_dump()


def test_get_by_document_sin_registro_es_none(repo: SqlAlchemyFuenteRepository) -> None:
    assert repo.get_by_document("no-existe") is None


def test_save_de_un_documento_existente_actualiza_en_vez_de_duplicar(repo: SqlAlchemyFuenteRepository) -> None:
    fuente = _fuente()
    repo.save(fuente)

    actualizada = fuente.actualizar("otro sistema", "otra autoridad", "otra evidencia")
    repo.save(actualizada)

    recuperada = repo.get_by_document(fuente.documento_id)
    assert recuperada is not None
    assert recuperada.sistema_origen == "otro sistema"
