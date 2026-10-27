"""Prueba de humo de `ui/app.py` (arranque real de la GUI, splash +
ventana principal maximizada) y de que `ui/__main__.py` siga siendo
importable con el ajuste de Wayland aplicado. No se ejercita
`ui.app.main()` completo aqui: construye su propio `QApplication`, lo
cual choca con el que ya provee `pytest-qt` para toda la sesion de
pruebas (`RuntimeError: Please destroy the QApplication singleton...`)
-- mismo motivo por el que `arrancar_ventana_maximizada()` se extrajo
de `main()` en `ui/app.py`: para poder probarse aislada con `qtbot`,
sin instanciar un `QApplication` propio."""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QMainWindow  # noqa: E402

import ui.__main__ as entrypoint_module  # noqa: E402
import ui.app as app_module  # noqa: E402
from ui.app import RETRASO_MAXIMIZADO_MS, arrancar_ventana_maximizada  # noqa: E402


def test_ui_app_y_ui_main_son_importables() -> None:
    # Solo importar ambos modulos (ya sucedio arriba, al tope del
    # archivo) no debe ejecutar main() -- esta linea confirma que el
    # import no lanzo excepciones y que main sigue siendo la funcion
    # esperada en los dos puntos de entrada (`python run_app.py` y
    # `python -m ui` delegan al mismo `ui.app.main`).
    assert entrypoint_module.main is app_module.main


def test_arrancar_ventana_maximizada_muestra_y_maximiza(qtbot) -> None:
    ventana = QMainWindow()
    qtbot.addWidget(ventana)

    arrancar_ventana_maximizada(ventana, splash=None, retraso_ms=10)

    assert ventana.isVisible()
    assert not ventana.isMaximized()  # todavia no -- el maximizado esta diferido

    qtbot.wait(100)  # más que retraso_ms, para que el QTimer.singleShot ya haya corrido

    assert ventana.isMaximized()


def test_arrancar_ventana_maximizada_cierra_el_splash(qtbot) -> None:
    ventana = QMainWindow()
    qtbot.addWidget(ventana)

    llamadas: list[QMainWindow] = []

    class _SplashFalso:
        def finish(self, ventana_terminada: QMainWindow) -> None:
            llamadas.append(ventana_terminada)

    splash = _SplashFalso()
    arrancar_ventana_maximizada(ventana, splash=splash, retraso_ms=10)  # type: ignore[arg-type]

    qtbot.wait(100)

    assert llamadas == [ventana]


def test_retraso_maximizado_por_defecto_es_positivo() -> None:
    # Documenta la constante en si (300ms, ver docstring en ui/app.py)
    # en vez de solo confiar en que `arrancar_ventana_maximizada` la usa
    # bien -- un valor de 0 o negativo perderia la vuelta real del event
    # loop que el maximizado necesita bajo Mutter/XWayland.
    assert RETRASO_MAXIMIZADO_MS > 0
