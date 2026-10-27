"""Punto de entrada de la interfaz grafica: `python -m ui`. Delgado a
proposito -- toda la logica real vive en `ui/app.py` (splash, arranque,
ventana principal maximizada); este modulo solo aplica el ajuste de
Wayland ANTES de importar PySide6 (ver comentario mas abajo) y delega.
Ver tambien `run_app.py` (raiz del repo), la otra forma soportada de
arrancar la aplicacion -- mismo patron que RAG STUDIO.
"""
from __future__ import annotations

import os
import sys

# Bajo una sesion Wayland (la sesion por defecto en Ubuntu reciente al
# iniciar sesion con GNOME), el propio protocolo prohibe que una
# aplicacion posicione o maximice sus ventanas top-level -- no es
# configurable desde Qt ni desde este codigo, es una restriccion de
# seguridad/UX del compositor. Ubuntu incluye XWayland por defecto, asi
# que se fuerza el backend X11 de Qt (solo cuando se detecta Wayland y
# el usuario no fijo ya QT_QPA_PLATFORM por su cuenta) para que el
# centrado del splash y el maximizado de la ventana principal si se
# respeten -- mismo ajuste ya confirmado y documentado en RAG STUDIO
# (`run_app.py`), revisado deliberadamente antes de construir esta GUI.
if "QT_QPA_PLATFORM" not in os.environ and os.environ.get("XDG_SESSION_TYPE") == "wayland":
    os.environ["QT_QPA_PLATFORM"] = "xcb"

from ui.app import main  # noqa: E402 -- despues del ajuste de QT_QPA_PLATFORM

if __name__ == "__main__":
    sys.exit(main())
