"""Prueba de regresion deliberada: verifica que TODOS los campos de
Incidencia sobreviven un ciclo save() -> get() contra una base SQLite
real, no un doble en memoria -- mismo motivo que
test_sqlalchemy_document_repository.py (un campo nuevo olvidado en
_to_row/_to_entity es invisible para las pruebas con un repositorio
falso en memoria).
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from domain.incidents.entities import EstadoIncidencia, EtapaIncidencia, Incidencia, SeveridadIncidencia
from infrastructure.database.engine import build_engine
from infrastructure.database.incident_repository import SqlAlchemyIncidentRepository
from infrastructure.database.migrations import RUTA_LINEA_PROYECTO, upgrade_to_head

RAIZ_PRUEBA = Path("/tmp/rag_content_studio_incident_repository_test")


@pytest.fixture()
def repo():
    if RAIZ_PRUEBA.exists():
        shutil.rmtree(RAIZ_PRUEBA)
    RAIZ_PRUEBA.mkdir(parents=True)
    db_path = RAIZ_PRUEBA / "proyecto.db"
    upgrade_to_head(db_path, RUTA_LINEA_PROYECTO)
    engine = build_engine(db_path)
    session = sessionmaker(bind=engine, future=True)()
    yield SqlAlchemyIncidentRepository(session)
    shutil.rmtree(RAIZ_PRUEBA, ignore_errors=True)


def _incidencia_abierta() -> Incidencia:
    return Incidencia(
        proyecto_id="PROY-0001",
        documento_id="doc-1",
        etapa=EtapaIncidencia.REVISION,
        tipo="cifra_dudosa",
        severidad=SeveridadIncidencia.CRITICA,
        evidencia="La cifra de la pagina 3 no coincide con el original.",
        impacto="Podria invalidar el monto reportado.",
    )


def test_save_y_get_recuperan_todos_los_campos_de_una_incidencia_abierta(
    repo: SqlAlchemyIncidentRepository,
) -> None:
    incidencia = _incidencia_abierta()
    repo.save(incidencia)

    recuperada = repo.get(incidencia.id)
    assert recuperada is not None
    assert recuperada.model_dump() == incidencia.model_dump()


def test_save_y_get_recuperan_el_ciclo_de_vida_completo_hasta_cerrada(
    repo: SqlAlchemyIncidentRepository,
) -> None:
    incidencia = (
        _incidencia_abierta()
        .asignar("ana@nexom.mx")
        .responder("Se confirma la discrepancia contra el original.")
        .decidir("Se corrige en la siguiente extraccion.", resuelta=True)
        .cerrar("Corregido y verificado.")
    )
    repo.save(incidencia)

    recuperada = repo.get(incidencia.id)
    assert recuperada is not None
    assert recuperada.estado == EstadoIncidencia.CERRADA
    assert recuperada.responsable == "ana@nexom.mx"
    assert recuperada.respuesta == "Se confirma la discrepancia contra el original."
    assert recuperada.decision == "Se corrige en la siguiente extraccion."
    assert recuperada.cierre == "Corregido y verificado."


def test_actualizar_una_incidencia_existente_persiste_el_cambio(repo: SqlAlchemyIncidentRepository) -> None:
    incidencia = _incidencia_abierta()
    repo.save(incidencia)

    asignada = incidencia.asignar("ana@nexom.mx")
    repo.save(asignada)

    recuperada = repo.get(incidencia.id)
    assert recuperada is not None
    assert recuperada.estado == EstadoIncidencia.ASIGNADA
    assert recuperada.responsable == "ana@nexom.mx"


def test_list_by_document_filtra_por_documento(repo: SqlAlchemyIncidentRepository) -> None:
    incidencia_a = _incidencia_abierta()
    incidencia_b = Incidencia(
        proyecto_id="PROY-0001",
        documento_id="doc-2",
        etapa=EtapaIncidencia.OCR,
        tipo="confianza_baja",
        severidad=SeveridadIncidencia.MEDIA,
        evidencia="Confianza baja en la pagina 1.",
        impacto="Riesgo menor.",
    )
    repo.save(incidencia_a)
    repo.save(incidencia_b)

    de_doc_1 = repo.list_by_document("doc-1")
    assert [i.id for i in de_doc_1] == [incidencia_a.id]
    assert len(repo.list()) == 2
