"""Prueba de regresion deliberada (mismo principio que
test_sqlalchemy_document_repository.py): verifica que todos los campos
de Trabajo sobreviven un ciclo save() -> get() contra una base SQLite
real, y que list_by_estado/list_by_document/list_pendientes_por_prioridad
devuelven el orden esperado -- nada de esto es visible con un
repositorio falso en memoria."""
from __future__ import annotations

import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from domain.jobs.entities import EstadoTrabajo, Prioridad, Trabajo, TipoTrabajo
from infrastructure.database.engine import build_engine
from infrastructure.database.job_repository import SqlAlchemyTrabajoRepository
from infrastructure.database.migrations import RUTA_LINEA_PROYECTO, upgrade_to_head

RAIZ_PRUEBA = Path("/tmp/rag_content_studio_job_repository_test")


@pytest.fixture()
def repo():
    if RAIZ_PRUEBA.exists():
        shutil.rmtree(RAIZ_PRUEBA)
    RAIZ_PRUEBA.mkdir(parents=True)
    db_path = RAIZ_PRUEBA / "proyecto.db"
    upgrade_to_head(db_path, RUTA_LINEA_PROYECTO)
    engine = build_engine(db_path)
    session = sessionmaker(bind=engine, future=True)()
    yield SqlAlchemyTrabajoRepository(session)
    shutil.rmtree(RAIZ_PRUEBA, ignore_errors=True)


def _trabajo(**overrides) -> Trabajo:
    datos = {"proyecto_id": "PROY-0001", "tipo": TipoTrabajo.EXTRACCION, "documento_id": "doc-1"}
    datos.update(overrides)
    return Trabajo(**datos)


def test_save_y_get_recuperan_todos_los_campos(repo: SqlAlchemyTrabajoRepository) -> None:
    trabajo = _trabajo().iniciar_preparacion().iniciar_ejecucion().fallar("fallo de prueba")
    repo.save(trabajo)

    recuperado = repo.get(trabajo.id)
    assert recuperado is not None
    assert recuperado.model_dump() == trabajo.model_dump()


def test_actualizar_un_trabajo_existente_persiste_el_cambio(repo: SqlAlchemyTrabajoRepository) -> None:
    trabajo = _trabajo()
    repo.save(trabajo)

    actualizado = trabajo.pausar()
    repo.save(actualizado)

    recuperado = repo.get(trabajo.id)
    assert recuperado is not None
    assert recuperado.estado == EstadoTrabajo.PAUSADO


def test_list_by_estado_filtra_correctamente(repo: SqlAlchemyTrabajoRepository) -> None:
    pendiente = _trabajo(documento_id="doc-1")
    preparando = _trabajo(documento_id="doc-2").iniciar_preparacion()
    repo.save(pendiente)
    repo.save(preparando)

    assert [t.id for t in repo.list_by_estado(EstadoTrabajo.PENDIENTE)] == [pendiente.id]
    assert [t.id for t in repo.list_by_estado(EstadoTrabajo.PREPARANDO)] == [preparando.id]


def test_list_by_document_devuelve_solo_los_del_documento(repo: SqlAlchemyTrabajoRepository) -> None:
    del_doc_1 = _trabajo(documento_id="doc-1")
    tambien_doc_1 = _trabajo(documento_id="doc-1", tipo=TipoTrabajo.NORMALIZACION)
    del_doc_2 = _trabajo(documento_id="doc-2")
    for t in (del_doc_1, tambien_doc_1, del_doc_2):
        repo.save(t)

    resultado = repo.list_by_document("doc-1")
    assert {t.id for t in resultado} == {del_doc_1.id, tambien_doc_1.id}


def test_list_pendientes_por_prioridad_ordena_urgente_primero(repo: SqlAlchemyTrabajoRepository) -> None:
    normal = _trabajo(documento_id="doc-1", prioridad=Prioridad.NORMAL)
    urgente = _trabajo(documento_id="doc-2", prioridad=Prioridad.URGENTE)
    baja = _trabajo(documento_id="doc-3", prioridad=Prioridad.BAJA)
    for t in (normal, urgente, baja):
        repo.save(t)

    orden = [t.id for t in repo.list_pendientes_por_prioridad()]
    assert orden == [urgente.id, normal.id, baja.id]


def test_list_pendientes_por_prioridad_desempata_por_antiguedad(repo: SqlAlchemyTrabajoRepository) -> None:
    ahora = datetime.now(timezone.utc)
    mas_viejo = _trabajo(documento_id="doc-1", creado_en=ahora - timedelta(minutes=5))
    mas_nuevo = _trabajo(documento_id="doc-2", creado_en=ahora)
    repo.save(mas_nuevo)
    repo.save(mas_viejo)

    orden = [t.id for t in repo.list_pendientes_por_prioridad()]
    assert orden == [mas_viejo.id, mas_nuevo.id]


def test_list_pendientes_por_prioridad_excluye_otros_estados(repo: SqlAlchemyTrabajoRepository) -> None:
    pendiente = _trabajo(documento_id="doc-1")
    completado = _trabajo(documento_id="doc-2").iniciar_preparacion().iniciar_ejecucion().completar()
    repo.save(pendiente)
    repo.save(completado)

    assert [t.id for t in repo.list_pendientes_por_prioridad()] == [pendiente.id]
