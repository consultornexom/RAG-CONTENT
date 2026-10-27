"""Fix real de la tercera auditoria general (2026-07-31), aplicado en la
cuarta ronda de correcciones: `scripts/gestionar_respaldos.py` no
capturaba errores especificos del dominio (por ejemplo
`ClaveDeRespaldoNoEncontradaError` al restaurar un respaldo sin clave
guardada) -- un error de este tipo dejaba pasar un traceback completo de
Python en la terminal en vez de un mensaje corto y claro, con codigo de
salida 1. Estas pruebas monkeypatchean `_importar()` (el unico punto de
entrada al `app.bootstrap` real que tiene el script) para forzar cada
tipo de fallo sin necesitar una raiz de datos real ni una base de datos
SQLite -- mismo criterio de aislamiento que el resto de la suite."""
from __future__ import annotations

from typing import Any

import pytest

from domain.security.exceptions import ClaveDeRespaldoNoEncontradaError
from scripts import gestionar_respaldos


class _CtxQueFalla:
    """Simula `bootstrap()` habiendo funcionado, pero cualquier operacion
    de dominio posterior (listar, crear, restaurar) lanzando la
    excepcion indicada -- separado de `_BootstrapQueFalla` (mas abajo)
    para poder distinguir en las pruebas si el fallo ocurre antes o
    despues de tener un `ctx` real."""

    class _ProjectsQueFalla:
        def listar_proyectos(self) -> Any:
            raise ClaveDeRespaldoNoEncontradaError("PROY-0001")

        def obtener_proyecto(self, proyecto_id: str) -> Any:
            raise ClaveDeRespaldoNoEncontradaError(proyecto_id)

    def __init__(self) -> None:
        self.projects = self._ProjectsQueFalla()


def test_listar_con_error_de_dominio_no_deja_pasar_un_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gestionar_respaldos, "_importar", lambda: (lambda *a, **k: None, lambda: _CtxQueFalla()))
    monkeypatch.setattr("sys.argv", ["gestionar_respaldos.py", "listar"])

    codigo = gestionar_respaldos.main()

    assert codigo == 1
    salida = capsys.readouterr().out
    assert "No se encontro una clave de cifrado de respaldos para el proyecto 'PROY-0001'" in salida
    assert "Traceback" not in salida


def test_restaurar_con_clave_no_encontrada_no_deja_pasar_un_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gestionar_respaldos, "_importar", lambda: (lambda *a, **k: None, lambda: _CtxQueFalla()))
    monkeypatch.setattr(
        "sys.argv",
        ["gestionar_respaldos.py", "restaurar", "PROY-0002", "respaldo.zip.enc", "/tmp/destino"],
    )

    codigo = gestionar_respaldos.main()

    assert codigo == 1
    salida = capsys.readouterr().out
    assert "No se encontro una clave de cifrado de respaldos para el proyecto 'PROY-0002'" in salida
    assert "Traceback" not in salida


def test_bootstrap_que_falla_tambien_se_captura(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """El propio `bootstrap()` puede fallar (por ejemplo, una base de
    datos corrupta o una carpeta raiz sin permisos de escritura) antes
    de llegar a cualquier accion -- tambien debe quedar capturado."""

    def _bootstrap_que_falla() -> Any:
        raise RuntimeError("no se pudo abrir la base de datos global")

    monkeypatch.setattr(gestionar_respaldos, "_importar", lambda: (lambda *a, **k: None, _bootstrap_que_falla))
    monkeypatch.setattr("sys.argv", ["gestionar_respaldos.py", "listar"])

    codigo = gestionar_respaldos.main()

    assert codigo == 1
    salida = capsys.readouterr().out
    assert "no se pudo abrir la base de datos global" in salida
    assert "Traceback" not in salida
