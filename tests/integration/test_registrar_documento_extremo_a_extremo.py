"""Prueba de humo del Modulo 3 (inventario documental con hash
SHA-256). Usa una raiz temporal, nunca la ruta real de datos -- igual
que la prueba de humo del Modulo 1.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.bootstrap import abrir_proyecto, bootstrap
from domain.documents.exceptions import DuplicateDocumentHashError
from infrastructure.database.project_models import DocumentoModel

RAIZ_PRUEBA = Path("/tmp/rag_content_studio_smoke_test_documentos")


@pytest.fixture()
def raiz_temporal():
    if RAIZ_PRUEBA.exists():
        shutil.rmtree(RAIZ_PRUEBA)
    RAIZ_PRUEBA.mkdir(parents=True)
    perfiles_dir = RAIZ_PRUEBA / "perfiles" / "perfil_generico"
    perfiles_dir.mkdir(parents=True)
    shutil.copy(
        Path(__file__).resolve().parents[2] / "perfiles" / "perfil_generico" / "0.1.yaml",
        perfiles_dir / "0.1.yaml",
    )
    origenes_dir = RAIZ_PRUEBA / "_origenes_de_prueba"
    origenes_dir.mkdir()
    yield RAIZ_PRUEBA, origenes_dir
    shutil.rmtree(RAIZ_PRUEBA, ignore_errors=True)


def test_registrar_documento_completo(raiz_temporal) -> None:
    raiz, origenes_dir = raiz_temporal
    ctx = bootstrap(raiz=str(raiz))

    proyecto = ctx.projects.crear_proyecto(nombre="Inventario de prueba", perfil_id="perfil_generico")
    pctx = abrir_proyecto(ctx, proyecto)

    archivo = origenes_dir / "politica_vacaciones.pdf"
    archivo.write_bytes(b"contenido simulado de un pdf")

    documento = pctx.documents.registrar_documento(
        proyecto_id=proyecto.id,
        ruta_origen=str(archivo),
        metadatos={"area_propietaria": "rh"},
    )

    # 1. Quedo inventariado.
    assert documento.estado.value == "inventariado"

    # 2. La copia inmutable existe fisicamente dentro de 01_originales/.
    ruta_copia = Path(documento.ruta_copia_original)
    assert ruta_copia.is_file()
    assert ruta_copia.parent == Path(proyecto.ruta_carpeta) / "01_originales"
    assert ruta_copia.read_bytes() == archivo.read_bytes()

    # 3. proyecto.db existe y tiene exactamente ese documento -- no en aplicacion.db.
    db_proyecto = Path(proyecto.ruta_carpeta) / "proyecto.db"
    assert db_proyecto.is_file()
    filas = pctx.session.query(DocumentoModel).all()
    assert len(filas) == 1
    assert filas[0].hash_sha256 == documento.hash_sha256

    # 4. Se puede recuperar por hash (deduplicacion).
    encontrado = pctx.documents.buscar_por_hash(documento.hash_sha256)
    assert encontrado is not None
    assert encontrado.id == documento.id

    # 5. Registrar el mismo contenido de nuevo falla (Modulo 3: dedup por hash).
    archivo_duplicado = origenes_dir / "politica_vacaciones_copia.pdf"
    archivo_duplicado.write_bytes(archivo.read_bytes())
    with pytest.raises(DuplicateDocumentHashError):
        pctx.documents.registrar_documento(proyecto_id=proyecto.id, ruta_origen=str(archivo_duplicado))

    # 5b. Bug real encontrado en auditoria 2026-07-31: el nombre de archivo
    # del duplicado es distinto al ya registrado ("_copia" agregado), asi
    # que LocalOriginalFileStore.copiar_original() no encuentra un destino
    # ya existente y completa una copia fisica nueva en 01_originales/ ANTES
    # de que RegistrarDocumento detecte el hash duplicado -- sin la limpieza
    # agregada en este fix, esa copia quedaba huerfana en disco para
    # siempre, sin que ningun Documento la referenciara. Se confirma que
    # 01_originales/ conserva solo la copia legitima (la del primer
    # registro), no una segunda copia huerfana del intento duplicado.
    copias_originales = list((Path(proyecto.ruta_carpeta) / "01_originales").iterdir())
    assert len(copias_originales) == 1
    assert copias_originales[0] == ruta_copia

    # 6. Quedo evento de auditoria en la base global (Documento Maestro, seccion 4.1).
    from infrastructure.database.models import EventoAuditoriaModel

    eventos = ctx.session.query(EventoAuditoriaModel).filter_by(proyecto_id=proyecto.id, accion="registrar_documento").all()
    assert len(eventos) == 1
