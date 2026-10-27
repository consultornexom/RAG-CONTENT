"""SqlAlchemyAuditLogger (Fase 11: list_by_project, el primer metodo de
LECTURA de este adaptador -- record() existe desde la Fase 1, pero
hasta ahora nada necesitaba leer los eventos de vuelta). Prueba real
contra SQLite, no un doble en memoria -- mismo criterio que
test_sqlalchemy_document_repository.py."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from infrastructure.database.audit_logger import SqlAlchemyAuditLogger
from infrastructure.database.engine import build_engine
from infrastructure.database.migrations import RUTA_LINEA_GLOBAL, upgrade_to_head

RAIZ_PRUEBA = Path("/tmp/rag_content_studio_audit_logger_test")


@pytest.fixture()
def audit_logger():
    if RAIZ_PRUEBA.exists():
        shutil.rmtree(RAIZ_PRUEBA)
    RAIZ_PRUEBA.mkdir(parents=True)
    db_path = RAIZ_PRUEBA / "aplicacion.db"
    upgrade_to_head(db_path, RUTA_LINEA_GLOBAL)
    engine = build_engine(db_path)
    session = sessionmaker(bind=engine, future=True)()
    yield SqlAlchemyAuditLogger(session)
    shutil.rmtree(RAIZ_PRUEBA, ignore_errors=True)


def test_list_by_project_devuelve_solo_los_eventos_de_ese_proyecto(audit_logger: SqlAlchemyAuditLogger) -> None:
    audit_logger.record("PROY-0001", "crear_proyecto", None, "PROY-0001", "alta inicial")
    audit_logger.record("PROY-0001", "aprobar_para_markdown", "normalizado", "aprobado_para_markdown", "revisado ok")
    audit_logger.record("PROY-0002", "crear_proyecto", None, "PROY-0002", "otro proyecto")

    eventos = audit_logger.list_by_project("PROY-0001")

    assert len(eventos) == 2
    assert all(evento.proyecto_id == "PROY-0001" for evento in eventos)
    acciones = {evento.accion for evento in eventos}
    assert acciones == {"crear_proyecto", "aprobar_para_markdown"}


def test_list_by_project_mas_reciente_primero(audit_logger: SqlAlchemyAuditLogger) -> None:
    audit_logger.record("PROY-0001", "primero", None, "a", "motivo 1")
    audit_logger.record("PROY-0001", "segundo", "a", "b", "motivo 2")

    eventos = audit_logger.list_by_project("PROY-0001")

    assert [evento.accion for evento in eventos] == ["segundo", "primero"]


def test_list_by_project_sin_eventos_devuelve_lista_vacia(audit_logger: SqlAlchemyAuditLogger) -> None:
    assert audit_logger.list_by_project("PROY-9999") == []


def test_list_by_project_con_limite_aplica_un_limit_real_en_sql(audit_logger: SqlAlchemyAuditLogger) -> None:
    """Hallazgo real de la cuarta auditoria general (2026-08-01): antes
    no existia forma de acotar esta consulta -- los consumidores
    (auditoria_panel.py, pantalla_principal_widget.py) traian TODAS las
    filas del proyecto y recien ahi truncaban en Python. Ahora `limite`
    aplica un LIMIT real en la consulta SQL, manteniendo el orden "mas
    reciente primero"."""
    for i in range(5):
        audit_logger.record("PROY-0001", f"accion-{i}", None, None, "motivo")

    eventos = audit_logger.list_by_project("PROY-0001", limite=2)

    assert len(eventos) == 2
    assert [e.accion for e in eventos] == ["accion-4", "accion-3"]


def test_list_by_project_sin_limite_devuelve_todos_los_eventos(audit_logger: SqlAlchemyAuditLogger) -> None:
    """`limite=None` (predeterminado) preserva el comportamiento anterior
    sin cambios -- sin limite, todas las filas del proyecto."""
    for i in range(5):
        audit_logger.record("PROY-0001", f"accion-{i}", None, None, "motivo")

    assert len(audit_logger.list_by_project("PROY-0001")) == 5
    assert len(audit_logger.list_by_project("PROY-0001", limite=None)) == 5
