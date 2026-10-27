"""Prueba de regresion deliberada: verifica que TODOS los campos de
Vigencia sobreviven un ciclo save() -> get_by_document() contra una
base SQLite real -- mismo motivo que
test_sqlalchemy_incident_repository.py. Incluye explicitamente el caso
de fechas en None (vigencia incompleta) y el flag `sin_vencimiento`,
que son los dos campos con mas riesgo de mapearse mal."""
from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from domain.validity.entities import Vigencia
from infrastructure.database.engine import build_engine
from infrastructure.database.migrations import RUTA_LINEA_PROYECTO, upgrade_to_head
from infrastructure.database.validity_repository import SqlAlchemyVigenciaRepository

RAIZ_PRUEBA = Path("/tmp/rag_content_studio_validity_repository_test")


@pytest.fixture()
def repo():
    if RAIZ_PRUEBA.exists():
        shutil.rmtree(RAIZ_PRUEBA)
    RAIZ_PRUEBA.mkdir(parents=True)
    db_path = RAIZ_PRUEBA / "proyecto.db"
    upgrade_to_head(db_path, RUTA_LINEA_PROYECTO)
    engine = build_engine(db_path)
    session = sessionmaker(bind=engine, future=True)()
    yield SqlAlchemyVigenciaRepository(session)
    shutil.rmtree(RAIZ_PRUEBA, ignore_errors=True)


def _vigencia_completa() -> Vigencia:
    return Vigencia(
        documento_id="doc-1",
        fecha_emision=date(2025, 12, 1),
        vigente_desde=date(2026, 1, 1),
        vigente_hasta=date(2026, 12, 31),
        sin_vencimiento=False,
        autoridad="Direccion Juridica",
        sustituye_a="doc-0",
    )


def test_save_y_get_by_document_recuperan_todos_los_campos(repo: SqlAlchemyVigenciaRepository) -> None:
    vigencia = _vigencia_completa()
    repo.save(vigencia)

    recuperada = repo.get_by_document(vigencia.documento_id)
    assert recuperada is not None
    assert recuperada.model_dump() == vigencia.model_dump()


def test_vigencia_incompleta_con_fechas_none_sobrevive_el_ciclo(repo: SqlAlchemyVigenciaRepository) -> None:
    vigencia = Vigencia(documento_id="doc-2")
    repo.save(vigencia)

    recuperada = repo.get_by_document("doc-2")
    assert recuperada is not None
    assert recuperada.fecha_emision is None
    assert recuperada.vigente_desde is None
    assert recuperada.vigente_hasta is None
    assert recuperada.sin_vencimiento is False
    assert recuperada.sustituye_a is None
    assert recuperada.esta_completa() is False


def test_vigencia_sin_vencimiento_sobrevive_el_ciclo(repo: SqlAlchemyVigenciaRepository) -> None:
    vigencia = Vigencia(
        documento_id="doc-3", vigente_desde=date(2026, 1, 1), sin_vencimiento=True, autoridad="Direccion Juridica"
    )
    repo.save(vigencia)

    recuperada = repo.get_by_document("doc-3")
    assert recuperada is not None
    assert recuperada.sin_vencimiento is True
    assert recuperada.vigente_hasta is None
    assert recuperada.esta_completa() is True


def test_get_by_document_sin_registro_es_none(repo: SqlAlchemyVigenciaRepository) -> None:
    assert repo.get_by_document("no-existe") is None


def test_save_de_un_documento_existente_actualiza_en_vez_de_duplicar(repo: SqlAlchemyVigenciaRepository) -> None:
    vigencia = _vigencia_completa()
    repo.save(vigencia)

    actualizada = vigencia.actualizar(
        fecha_emision=vigencia.fecha_emision,
        vigente_desde=date(2027, 1, 1),
        vigente_hasta=date(2027, 12, 31),
        sin_vencimiento=False,
        autoridad="Otra autoridad",
        sustituye_a=None,
    )
    repo.save(actualizada)

    recuperada = repo.get_by_document(vigencia.documento_id)
    assert recuperada is not None
    assert recuperada.vigente_desde == date(2027, 1, 1)
    assert recuperada.autoridad == "Otra autoridad"
    assert recuperada.sustituye_a is None
