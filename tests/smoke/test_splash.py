"""Prueba de humo de ui.splash -- mismo patron ya validado en RAG
STUDIO (ui/app.py::_show_splash), ver ui/splash.py."""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

import ui.splash as splash_module  # noqa: E402


def test_mostrar_splash_con_logo_presente_devuelve_pantalla_valida(qtbot) -> None:
    app = QApplication.instance() or QApplication([])
    splash = splash_module.mostrar_splash(app)
    assert splash is not None
    assert not splash.pixmap().isNull()
    splash.close()


def test_mostrar_splash_sin_logo_devuelve_none_sin_fallar(qtbot, monkeypatch, tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(splash_module, "_LOGO_PATH", tmp_path / "no_existe.png")
    assert splash_module.mostrar_splash(app) is None
