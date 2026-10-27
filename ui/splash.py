"""Pantalla de bienvenida (splash) mostrada al arrancar la GUI, antes
de que la ventana principal este lista -- mismo patron ya usado y
probado en RAG STUDIO (`ui/app.py::_show_splash`, revisado
deliberadamente el 2026-07-28 antes de construir esta version): el
splash aparece de inmediato (antes de `app.bootstrap.bootstrap()`, que
corre migraciones y arma el contexto) y se cierra justo cuando la
ventana principal ya esta lista para mostrarse.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen, QWidget

_LOGO_PATH = Path(__file__).resolve().parent / "LOGO.png"
_SPLASH_WIDTH = 480

MIN_SPLASH_SECONDS = 1.0
"""Un arranque de por si rapido (SQLite local) puede tardar menos de lo
que el ojo humano percibe -- sin este minimo, el splash llegaria a
cerrarse antes de pintarse una sola vez (mismo ajuste que RAG
STUDIO)."""


def mostrar_splash(app: QApplication) -> Optional[QSplashScreen]:
    """Muestra el logo del proyecto mientras la aplicacion termina de
    arrancar. Si el archivo del logo no existe o no se puede leer (por
    ejemplo, en una instalacion que no incluyo `ui/LOGO.png`), se omite
    la pantalla de bienvenida sin interrumpir el arranque -- nunca debe
    ser un requisito para que la aplicacion abra."""
    if not _LOGO_PATH.exists():
        return None
    pixmap = QPixmap(str(_LOGO_PATH))
    if pixmap.isNull():
        return None
    pixmap = pixmap.scaledToWidth(_SPLASH_WIDTH, Qt.TransformationMode.SmoothTransformation)
    splash = QSplashScreen(pixmap)
    splash.show()
    # El centrado debe pedirse DESPUES de mostrar la ventana: varios
    # gestores de ventanas en Linux ignoran move() sobre una ventana
    # que todavia no ha sido mapeada, y la dejan en la esquina superior
    # izquierda por defecto (mismo hallazgo ya documentado en RAG
    # STUDIO).
    app.processEvents()
    _centrar_en_pantalla_principal(splash)
    app.processEvents()
    return splash


def _centrar_en_pantalla_principal(widget: QWidget) -> None:
    """Centra una ventana top-level (como el splash) en la pantalla
    principal."""
    screen = widget.screen() or QApplication.primaryScreen()
    if screen is None:
        return
    screen_geometry = screen.availableGeometry()
    widget_geometry = widget.frameGeometry()
    widget_geometry.moveCenter(screen_geometry.center())
    widget.move(widget_geometry.topLeft())
