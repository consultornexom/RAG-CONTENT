"""Prueba de humo de la Fase 6 (Colas de trabajo y workers aislados).
Usa una raiz temporal, nunca la ruta real de datos -- mismo patron que
el resto de tests/smoke/test_*_extremo_a_extremo.py: bootstrap()/
abrir_proyecto() reales, sin fakes, para probar el cableado completo de
app.bootstrap (JobsService + ColaDeTrabajos sobre TrabajoRepository y
DocumentsService reales)."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.bootstrap import abrir_proyecto, bootstrap
from domain.documents.entities import EstadoDocumento
from domain.jobs.entities import EstadoTrabajo, TipoTrabajo
from infrastructure.database.job_repository import SqlAlchemyTrabajoRepository

RAIZ_PRUEBA = Path("/tmp/rag_content_studio_smoke_test_cola_de_trabajos")


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


def test_encolar_y_procesar_un_trabajo_de_extraccion_real(raiz_temporal) -> None:
    raiz, origenes_dir = raiz_temporal
    ctx = bootstrap(raiz=str(raiz))
    proyecto = ctx.projects.crear_proyecto(nombre="Fase 6", perfil_id="perfil_generico")
    pctx = abrir_proyecto(ctx, proyecto)

    archivo = origenes_dir / "memo.txt"
    archivo.write_text("Contenido real del memo para la cola de trabajos.", encoding="utf-8")

    documento = pctx.documents.registrar_documento(proyecto_id=proyecto.id, ruta_origen=str(archivo))
    clasificado = pctx.documents.clasificar_documento(documento.id)
    assert clasificado.estado == EstadoDocumento.CLASIFICADO

    trabajo = pctx.jobs.encolar_trabajo(proyecto.id, TipoTrabajo.EXTRACCION, clasificado.id)
    assert trabajo.estado == EstadoTrabajo.PENDIENTE

    resultado = pctx.cola_trabajos.procesar_siguiente()

    assert resultado.estado == EstadoTrabajo.COMPLETADO
    assert resultado.id == trabajo.id
    documento_extraido = pctx.documents.obtener_documento(clasificado.id)
    assert documento_extraido.estado == EstadoDocumento.EXTRAIDO
    assert documento_extraido.ruta_extraccion is not None


def test_trabajo_huerfano_se_recupera_al_reabrir_el_proyecto(raiz_temporal) -> None:
    """Simula un cierre no controlado de la aplicacion: un trabajo queda
    en EJECUTANDO en proyecto.db sin ningun hilo real corriendolo (nadie
    llamo a completar_trabajo/fallar_trabajo). Reabrir el proyecto debe
    recuperarlo automaticamente (Documento Maestro, seccion 4.1:
    "recuperacion") -- ver RecuperarTrabajosInterrumpidos, invocado desde
    app.bootstrap.abrir_proyecto()."""
    raiz, origenes_dir = raiz_temporal
    ctx = bootstrap(raiz=str(raiz))
    proyecto = ctx.projects.crear_proyecto(nombre="Fase 6 recuperacion", perfil_id="perfil_generico")
    pctx = abrir_proyecto(ctx, proyecto)

    archivo = origenes_dir / "memo.txt"
    archivo.write_text("Contenido real del memo.", encoding="utf-8")
    documento = pctx.documents.registrar_documento(proyecto_id=proyecto.id, ruta_origen=str(archivo))
    clasificado = pctx.documents.clasificar_documento(documento.id)

    trabajo = pctx.jobs.encolar_trabajo(proyecto.id, TipoTrabajo.EXTRACCION, clasificado.id)
    trabajo = pctx.jobs.iniciar_preparacion(trabajo.id)
    trabajo = pctx.jobs.iniciar_ejecucion(trabajo.id)
    assert trabajo.estado == EstadoTrabajo.EJECUTANDO

    # "Cierre no controlado": ningun hilo real va a completar este
    # trabajo -- se abandona en EJECUTANDO, tal cual quedaria si la
    # aplicacion se hubiera cerrado en este instante.

    pctx_reabierto = abrir_proyecto(ctx, proyecto)
    recuperado = pctx_reabierto.jobs.obtener_trabajo(trabajo.id)

    assert recuperado.estado == EstadoTrabajo.FALLIDO
    assert "interrumpido" in recuperado.mensaje_error.lower()
    assert recuperado.intentos == 1

    # Verificable tambien contra el repositorio real, sin pasar por la
    # fachada -- misma base proyecto.db.
    repo = SqlAlchemyTrabajoRepository(pctx_reabierto.session)
    assert repo.get(trabajo.id).estado == EstadoTrabajo.FALLIDO
