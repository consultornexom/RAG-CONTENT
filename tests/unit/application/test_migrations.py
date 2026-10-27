"""Verifica que las dos lineas de Alembic (ADR-001, seccion 9) crean
exactamente el esquema esperado y que aplicarlas dos veces es
idempotente -- sin esto, un cambio futuro en los modelos sin su
migracion correspondiente pasaria desapercibido hasta produccion."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect

from infrastructure.database.migrations import RUTA_LINEA_GLOBAL, RUTA_LINEA_PROYECTO, upgrade_to_head

RAIZ_PRUEBA = Path("/tmp/rag_content_studio_migrations_test")


@pytest.fixture()
def raiz():
    if RAIZ_PRUEBA.exists():
        shutil.rmtree(RAIZ_PRUEBA)
    RAIZ_PRUEBA.mkdir(parents=True)
    yield RAIZ_PRUEBA
    shutil.rmtree(RAIZ_PRUEBA, ignore_errors=True)


def test_linea_global_crea_las_tablas_esperadas(raiz: Path) -> None:
    db_path = raiz / "aplicacion.db"
    upgrade_to_head(db_path, RUTA_LINEA_GLOBAL)

    assert db_path.is_file()
    engine = create_engine(f"sqlite:///{db_path}")
    tablas = set(inspect(engine).get_table_names())
    assert {"proyectos", "eventos_auditoria", "alembic_version"} <= tablas


def test_linea_global_crea_indice_en_proyecto_id_de_eventos_auditoria(raiz: Path) -> None:
    """Hallazgo de la tercera auditoria general (2026-07-31), corregido en
    la cuarta ronda: desde que `CerrarLote` audita cada documento por
    separado (ademas del evento agregado), el volumen de
    `eventos_auditoria` crece con la cantidad de documentos por lote, no
    solo con la cantidad de lotes -- cualquier consulta futura que
    filtre por proyecto necesita este indice para no hacer un table
    scan completo de la tabla global."""
    db_path = raiz / "aplicacion.db"
    upgrade_to_head(db_path, RUTA_LINEA_GLOBAL)

    engine = create_engine(f"sqlite:///{db_path}")
    indices = inspect(engine).get_indexes("eventos_auditoria")
    columnas_indexadas = {tuple(i["column_names"]) for i in indices}
    assert ("proyecto_id",) in columnas_indexadas


def test_linea_global_permite_dos_proyectos_con_el_mismo_nombre_si_uno_esta_archivado(raiz: Path) -> None:
    """Auditoria 2026-09-02 (hallazgo real de la auditoria independiente
    de la ronda de Archivar/Eliminar proyecto, RAG_CONTENT_01): la
    migracion inicial (6824add93305) definia `nombre` como UNIQUE a nivel
    de base de datos, lo que bloqueaba para siempre reutilizar el nombre
    de un proyecto ya archivado -- justo el escenario que "Archivar"
    existe para resolver. La migracion 'quita_restriccion_unica_de_
    nombre_en_proyectos' la remplaza por un indice no unico; la unicidad
    pasa a exigirse solo entre proyectos ACTIVOS, en
    infrastructure.database.repository.SqlAlchemyProjectRepository.
    get_by_name(). Esta prueba verifica el esquema de base directamente
    (sin pasar por el repositorio) para que una futura migracion que
    reintroduzca la restriccion unica por accidente falle aqui."""
    db_path = raiz / "aplicacion.db"
    upgrade_to_head(db_path, RUTA_LINEA_GLOBAL)

    engine = create_engine(f"sqlite:///{db_path}")
    restricciones_unicas = inspect(engine).get_unique_constraints("proyectos")
    assert restricciones_unicas == [], f"no deberia haber ninguna restriccion UNIQUE en 'proyectos': {restricciones_unicas}"

    with engine.connect() as conn:
        conn.exec_driver_sql(
            "INSERT INTO proyectos (id, nombre, perfil_id, objetivo, usuarios_objetivo_csv, alcance, "
            "jurisdiccion, idioma, confidencialidad, responsables_csv, estado, ruta_carpeta, created_at, "
            "updated_at) VALUES ('PROY-0001', 'Cliente ACME', 'perfil_generico', '', '', '', '', 'es', "
            "'interno', '', 'archivado', '/tmp/x', '2026-01-01', '2026-01-01')"
        )
        conn.exec_driver_sql(
            "INSERT INTO proyectos (id, nombre, perfil_id, objetivo, usuarios_objetivo_csv, alcance, "
            "jurisdiccion, idioma, confidencialidad, responsables_csv, estado, ruta_carpeta, created_at, "
            "updated_at) VALUES ('PROY-0002', 'Cliente ACME', 'perfil_generico', '', '', '', '', 'es', "
            "'interno', '', 'activo', '/tmp/y', '2026-01-02', '2026-01-02')"
        )
        conn.commit()
        filas = conn.exec_driver_sql("SELECT id, estado FROM proyectos WHERE nombre = 'Cliente ACME'").fetchall()
    assert {(r[0], r[1]) for r in filas} == {("PROY-0001", "archivado"), ("PROY-0002", "activo")}


def test_linea_proyecto_crea_las_tablas_esperadas(raiz: Path) -> None:
    db_path = raiz / "proyecto.db"
    upgrade_to_head(db_path, RUTA_LINEA_PROYECTO)

    assert db_path.is_file()
    engine = create_engine(f"sqlite:///{db_path}")
    tablas = set(inspect(engine).get_table_names())
    assert {"documentos", "alembic_version"} <= tablas


def test_aplicar_la_migracion_dos_veces_es_idempotente(raiz: Path) -> None:
    db_path = raiz / "aplicacion.db"
    upgrade_to_head(db_path, RUTA_LINEA_GLOBAL)
    upgrade_to_head(db_path, RUTA_LINEA_GLOBAL)  # no debe fallar ni duplicar nada

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        version = conn.exec_driver_sql("SELECT COUNT(*) FROM alembic_version").scalar()
    assert version == 1
