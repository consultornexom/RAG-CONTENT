"""Punto de entrada real de la interfaz grafica (PySide6). Unico lugar
de `ui` que llama a `app.bootstrap.bootstrap()` -- el resto de la
ventana recibe el `AppContext` ya construido (ADR-001 seccion 4).

Quien ejecuta la aplicacion usa `run_app.py` (raiz del repo) o
`python -m ui` (`ui/__main__.py`, delgado, solo delega aqui) -- ambos
deben fijar la variable de entorno QT_QPA_PLATFORM (ver mas abajo)
ANTES de importar este modulo, porque PySide6 se importa aqui arriba,
en el cuerpo del modulo.
"""
from __future__ import annotations

import sys
import time
from typing import Optional

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMainWindow, QSplashScreen

from app.bootstrap import bootstrap
from ui.main_window import MainWindow
from ui.splash import MIN_SPLASH_SECONDS, mostrar_splash
from ui.theme import HOJA_DE_ESTILOS

RETRASO_MAXIMIZADO_MS = 300
"""Mismo hallazgo ya confirmado y documentado en RAG STUDIO
(`ui/app.py::main`, revisado deliberadamente antes de escribir esto):
pedir el maximizado antes del primer show(), o mostrar normal y
maximizar en la misma rafaga sincronica de arranque, deja la ventana
con isMaximized()=True pero geometry() del tamano natural de la
ventana (no el de la pantalla) bajo Mutter/XWayland -- el compositor
necesita una vuelta real del *event loop en ejecucion* para completar
el intercambio de protocolo de maximizado, no una serie de
app.processEvents() manuales antes de app.exec(). Por eso se muestra
la ventana normal y se difiere el maximizado con
QTimer.singleShot(): la peticion ocurre igual que si un usuario la
disparara ya con la aplicacion corriendo."""


def arrancar_ventana_maximizada(
    ventana: QMainWindow, splash: Optional[QSplashScreen], retraso_ms: int = RETRASO_MAXIMIZADO_MS
) -> None:
    """Muestra `ventana` normal y programa su maximizado (ver
    RETRASO_MAXIMIZADO_MS) -- extraido de `main()` para poder probarse
    de forma aislada con `qtbot` (sin instanciar un `QApplication`
    propio, que chocaria con el que ya provee pytest-qt)."""
    ventana.show()

    def _finalizar_arranque() -> None:
        ventana.showMaximized()
        if splash is not None:
            splash.finish(ventana)

    QTimer.singleShot(retraso_ms, _finalizar_arranque)


def main() -> int:
    app = QApplication(sys.argv)
    # Paleta de colores 2026-07-29 (ver ui.theme): una sola llamada,
    # antes de construir cualquier ventana, para que toda la interfaz
    # nazca ya con el tema aplicado -- sin impacto de rendimiento (ver
    # docstring de ui.theme y README de esta misma fecha).
    app.setStyleSheet(HOJA_DE_ESTILOS)
    splash = mostrar_splash(app)
    splash_iniciado_en = time.monotonic()

    ctx = bootstrap()
    ventana = MainWindow(ctx)

    if splash is not None:
        # Se garantiza un minimo de tiempo visible bombeando el loop de
        # eventos (sin bloquear la UI con un sleep ciego) -- ver
        # ui.splash.MIN_SPLASH_SECONDS.
        limite = time.monotonic() + (MIN_SPLASH_SECONDS - (time.monotonic() - splash_iniciado_en))
        while time.monotonic() < limite:
            app.processEvents()

    arrancar_ventana_maximizada(ventana, splash)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
