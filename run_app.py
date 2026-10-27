"""Punto de entrada conveniente para la interfaz de escritorio.

Uso:
    python run_app.py

Requiere haber instalado el paquete en modo editable (pip install -e ".[ui]")
y las dependencias de ui (pip install -r requirements-ui.txt) -- ver
README, seccion "Interfaz grafica (prototipo, Modulo 8)".
"""
import os
import sys
from pathlib import Path

# Bajo una sesion Wayland (la sesion por defecto en Ubuntu reciente al
# iniciar sesion con GNOME), el propio protocolo prohibe que una
# aplicacion posicione sus ventanas top-level -- no es configurable desde
# Qt ni desde este codigo: es una restriccion de seguridad/UX del
# compositor. Por eso el splash con el logo y la ventana principal
# ignorarian por completo cualquier intento de centrado o de tamano.
# Ubuntu incluye XWayland por defecto, asi que forzamos el backend X11 de
# Qt (solo cuando detectamos Wayland y el usuario no fijo ya
# QT_QPA_PLATFORM por su cuenta) para que el centrado del splash y el
# maximizado de la ventana principal si se respeten -- mismo ajuste ya
# confirmado y documentado en RAG STUDIO (`run_app.py`), revisado
# deliberadamente antes de construir esta GUI.
if "QT_QPA_PLATFORM" not in os.environ and os.environ.get("XDG_SESSION_TYPE") == "wayland":
    os.environ["QT_QPA_PLATFORM"] = "xcb"


def main() -> int:
    # A diferencia de RAG STUDIO, este proyecto no usa un layout `src/`
    # (`ui`, `app`, `application`, etc. viven en la raiz del repo, ver
    # `pyproject.toml::tool.setuptools.packages.find`) -- el fallback
    # solo agrega la raiz del repo a `sys.path` para que `python
    # run_app.py` funcione incluso sin `pip install -e .` primero.
    try:
        from ui.app import main as ui_main
    except ImportError:
        sys.path.insert(0, str(Path(__file__).parent))
        from ui.app import main as ui_main

    return ui_main()


if __name__ == "__main__":
    raise SystemExit(main())
