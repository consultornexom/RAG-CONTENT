"""Prueba de humo de la Fase 11.3 (Pantalla principal / dashboard,
Documento Maestro seccion 4.11): bootstrap()/abrir_proyecto() reales,
sin fakes, mismo patron que
tests/smoke/test_asistente_por_etapas_extremo_a_extremo.py (Fase
11.2)."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from app.bootstrap import bootstrap  # noqa: E402
from domain.incidents.entities import EtapaIncidencia, SeveridadIncidencia  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402

RAIZ_PRUEBA = Path("/tmp/rag_content_studio_smoke_test_pantalla_principal")


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


def test_pantalla_principal_es_la_vista_de_entrada(qtbot, raiz_temporal) -> None:
    raiz, _origenes_dir = raiz_temporal
    ctx = bootstrap(raiz=str(raiz))
    ventana = MainWindow(ctx)
    qtbot.addWidget(ventana)
    assert ventana.modo_stack.currentIndex() == 0
    assert ventana.modo_stack.currentWidget() is ventana.pantalla_principal
    assert ventana.radio_inicio.isChecked()


def test_abrir_un_proyecto_pasa_automaticamente_al_asistente(qtbot, raiz_temporal) -> None:
    raiz, _origenes_dir = raiz_temporal
    ctx = bootstrap(raiz=str(raiz))
    proyecto = ctx.projects.crear_proyecto(nombre="Auto asistente", perfil_id="perfil_generico")

    ventana = MainWindow(ctx)
    qtbot.addWidget(ventana)
    assert ventana.radio_inicio.isChecked()

    ventana.combo_proyectos.setCurrentIndex(ventana.combo_proyectos.findData(proyecto.id))
    ventana._on_abrir_proyecto()

    assert ventana.radio_asistente.isChecked()
    assert ventana.modo_stack.currentIndex() == 1


def test_abrir_un_proyecto_no_saca_al_operador_del_modo_avanzado(qtbot, raiz_temporal) -> None:
    raiz, _origenes_dir = raiz_temporal
    ctx = bootstrap(raiz=str(raiz))
    proyecto = ctx.projects.crear_proyecto(nombre="Se queda en avanzado", perfil_id="perfil_generico")

    ventana = MainWindow(ctx)
    qtbot.addWidget(ventana)
    ventana.radio_modo_avanzado.setChecked(True)
    ventana._on_cambiar_modo(-1)
    assert ventana.modo_stack.currentIndex() == 2

    ventana.combo_proyectos.setCurrentIndex(ventana.combo_proyectos.findData(proyecto.id))
    ventana._on_abrir_proyecto()

    assert ventana.radio_modo_avanzado.isChecked()
    assert ventana.modo_stack.currentIndex() == 2


def test_doble_clic_en_proyecto_reciente_lo_abre(qtbot, raiz_temporal) -> None:
    raiz, _origenes_dir = raiz_temporal
    ctx = bootstrap(raiz=str(raiz))
    proyecto = ctx.projects.crear_proyecto(nombre="Doble clic", perfil_id="perfil_generico")

    ventana = MainWindow(ctx)
    qtbot.addWidget(ventana)
    assert ventana.pantalla_principal.lista_recientes.count() == 1
    item = ventana.pantalla_principal.lista_recientes.item(0)
    assert proyecto.nombre in item.text()

    ventana.pantalla_principal.abrir_proyecto_id.emit(item.data(256))
    assert ventana.proyecto_actual is not None
    assert ventana.proyecto_actual.id == proyecto.id
    assert ventana.modo_stack.currentIndex() == 1  # auto-avanza al asistente.


def test_abrir_otro_proyecto_cierra_la_sesion_del_proyecto_anterior(qtbot, raiz_temporal, monkeypatch) -> None:
    """Fuga de recursos real encontrada en la segunda auditoria
    2026-07-31: `_on_abrir_proyecto()` reemplazaba `self.pctx` sin
    cerrar la `Session` de SQLAlchemy anterior -- cada apertura de un
    proyecto (incluyendo reabrir el mismo mas de una vez en la misma
    corrida) dejaba una conexion SQLite abierta indefinidamente, sin
    liberarse hasta que terminara el proceso. Corregido cerrando la
    sesion vieja antes de reemplazarla."""
    raiz, _origenes_dir = raiz_temporal
    ctx = bootstrap(raiz=str(raiz))
    proyecto_1 = ctx.projects.crear_proyecto(nombre="Proyecto uno", perfil_id="perfil_generico")
    proyecto_2 = ctx.projects.crear_proyecto(nombre="Proyecto dos", perfil_id="perfil_generico")

    ventana = MainWindow(ctx)
    qtbot.addWidget(ventana)
    ventana.combo_proyectos.setCurrentIndex(ventana.combo_proyectos.findData(proyecto_1.id))
    ventana._on_abrir_proyecto()
    assert ventana.pctx is not None
    sesion_1 = ventana.pctx.session

    llamadas_close: list[object] = []
    monkeypatch.setattr(sesion_1, "close", lambda: llamadas_close.append(sesion_1))

    ventana.combo_proyectos.setCurrentIndex(ventana.combo_proyectos.findData(proyecto_2.id))
    ventana._on_abrir_proyecto()

    assert llamadas_close == [sesion_1]
    assert ventana.pctx is not None
    assert ventana.pctx.session is not sesion_1


def test_cerrar_la_ventana_cierra_las_sesiones_abiertas(qtbot, raiz_temporal, monkeypatch) -> None:
    """Mismo hallazgo que la prueba anterior, pero para el cierre de la
    aplicacion en si: ni `MainWindow` ni `ui.app.main()` cerraban nunca
    la sesion del proyecto abierto ni la sesion global de `AppContext`
    al salir. Corregido con `MainWindow.closeEvent()`."""
    raiz, _origenes_dir = raiz_temporal
    ctx = bootstrap(raiz=str(raiz))
    proyecto = ctx.projects.crear_proyecto(nombre="Cierre de sesion", perfil_id="perfil_generico")

    ventana = MainWindow(ctx)
    qtbot.addWidget(ventana)
    ventana.combo_proyectos.setCurrentIndex(ventana.combo_proyectos.findData(proyecto.id))
    ventana._on_abrir_proyecto()
    assert ventana.pctx is not None

    llamadas_close: list[str] = []
    monkeypatch.setattr(ventana.pctx.session, "close", lambda: llamadas_close.append("pctx"))
    monkeypatch.setattr(ventana.ctx.session, "close", lambda: llamadas_close.append("ctx"))

    ventana.close()

    assert "pctx" in llamadas_close
    assert "ctx" in llamadas_close


def test_resumen_del_proyecto_refleja_datos_reales(qtbot, raiz_temporal) -> None:
    raiz, origenes_dir = raiz_temporal
    ctx = bootstrap(raiz=str(raiz))
    proyecto = ctx.projects.crear_proyecto(nombre="Resumen real", perfil_id="perfil_generico")

    archivo = origenes_dir / "memo.txt"
    archivo.write_text("Contenido real para el dashboard.", encoding="utf-8")

    ventana = MainWindow(ctx)
    qtbot.addWidget(ventana)
    ventana.combo_proyectos.setCurrentIndex(ventana.combo_proyectos.findData(proyecto.id))
    ventana._on_abrir_proyecto()

    documento = ventana.pctx.documents.registrar_documento(proyecto_id=proyecto.id, ruta_origen=str(archivo))
    ventana.pctx.incidents.registrar_incidencia(
        proyecto_id=proyecto.id,
        documento_id=documento.id,
        etapa=EtapaIncidencia.INVENTARIO,
        tipo="dato_faltante",
        severidad=SeveridadIncidencia.CRITICA,
        evidencia="falta el area propietaria",
        impacto="bloquea la clasificacion",
    )
    lote = ventana.pctx.batches.crear_lote(proyecto.id, "Lote de prueba")
    ventana.pctx.batches.agregar_documento(lote.id, documento.id)

    ventana.radio_inicio.setChecked(True)
    ventana._on_cambiar_modo(-1)

    assert "inventariado: 1" in ventana.pantalla_principal.etiqueta_documentos.text()
    assert "dato_faltante" in ventana.pantalla_principal.etiqueta_incidencias.text()
    assert ventana.pantalla_principal.lista_lotes.count() == 1
    assert "0/1 liberado(s)" in ventana.pantalla_principal.lista_lotes.item(0).text()
    assert ventana.pantalla_principal.lista_actividad.count() > 0
    assert "GB libres" in ventana.pantalla_principal.etiqueta_almacenamiento.text()
