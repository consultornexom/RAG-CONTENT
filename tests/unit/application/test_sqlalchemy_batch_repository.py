"""Prueba de regresion deliberada (mismo principio que
test_sqlalchemy_document_repository.py/test_sqlalchemy_job_repository.py):
verifica que todos los campos de Lote sobreviven un ciclo save() ->
get() contra una base SQLite real, y que list_by_proyecto() filtra
correctamente."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from domain.batches.entities import EstadoLote, Lote
from infrastructure.database.batch_repository import SqlAlchemyLoteRepository
from infrastructure.database.engine import build_engine
from infrastructure.database.migrations import RUTA_LINEA_PROYECTO, upgrade_to_head

RAIZ_PRUEBA = Path("/tmp/rag_content_studio_batch_repository_test")


@pytest.fixture()
def repo():
    if RAIZ_PRUEBA.exists():
        shutil.rmtree(RAIZ_PRUEBA)
    RAIZ_PRUEBA.mkdir(parents=True)
    db_path = RAIZ_PRUEBA / "proyecto.db"
    upgrade_to_head(db_path, RUTA_LINEA_PROYECTO)
    engine = build_engine(db_path)
    session = sessionmaker(bind=engine, future=True)()
    yield SqlAlchemyLoteRepository(session)
    shutil.rmtree(RAIZ_PRUEBA, ignore_errors=True)


def _lote(**overrides) -> Lote:
    datos = {"proyecto_id": "PROY-0001", "nombre": "Lote de prueba"}
    datos.update(overrides)
    return Lote(**datos)


def test_save_y_get_recuperan_todos_los_campos(repo: SqlAlchemyLoteRepository) -> None:
    lote = _lote().cerrar()
    repo.save(lote)

    recuperado = repo.get(lote.id)
    assert recuperado is not None
    assert recuperado.model_dump() == lote.model_dump()


def test_actualizar_un_lote_existente_persiste_el_cambio(repo: SqlAlchemyLoteRepository) -> None:
    lote = _lote()
    repo.save(lote)

    cerrado = lote.cerrar()
    repo.save(cerrado)

    recuperado = repo.get(lote.id)
    assert recuperado is not None
    assert recuperado.estado == EstadoLote.CERRADO


def test_list_by_proyecto_filtra_correctamente(repo: SqlAlchemyLoteRepository) -> None:
    del_proyecto_1 = _lote(proyecto_id="PROY-0001")
    tambien_proyecto_1 = _lote(proyecto_id="PROY-0001", nombre="Otro lote")
    del_proyecto_2 = _lote(proyecto_id="PROY-0002")
    for lote in (del_proyecto_1, tambien_proyecto_1, del_proyecto_2):
        repo.save(lote)

    resultado = repo.list_by_proyecto("PROY-0001")
    assert {lote.id for lote in resultado} == {del_proyecto_1.id, tambien_proyecto_1.id}


def test_list_devuelve_todos_los_lotes(repo: SqlAlchemyLoteRepository) -> None:
    repo.save(_lote(proyecto_id="PROY-0001"))
    repo.save(_lote(proyecto_id="PROY-0002"))

    assert len(repo.list()) == 2
