"""app.configuration.cargar_rutas() -- resolucion multiplataforma de la
ruta raiz (bug real encontrado 2026-07-30, ver docstring del modulo
bajo prueba): antes de esta fecha la raiz por defecto era una cadena
Linux hardcodeada, que en Windows se resolvia de forma inesperada
(relativa a la unidad de trabajo actual) en vez de fallar de forma
obvia. Estas pruebas no existian todavia -- se agregan de entrada junto
con la correccion, no las descubrio una prueba de humo esta vez."""
from __future__ import annotations

from pathlib import Path

from app.configuration import _NOMBRE_CARPETA_POR_DEFECTO, _VARIABLE_ENTORNO_RAIZ, cargar_rutas


def test_raiz_explicita_tiene_prioridad_sobre_la_variable_de_entorno(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(_VARIABLE_ENTORNO_RAIZ, str(tmp_path / "desde_variable"))
    rutas = cargar_rutas(raiz=tmp_path / "explicita")

    assert rutas.raiz == tmp_path / "explicita"


def test_variable_de_entorno_tiene_prioridad_sobre_el_default_del_home(monkeypatch, tmp_path) -> None:
    destino = tmp_path / "raiz_desde_variable_de_entorno"
    monkeypatch.setenv(_VARIABLE_ENTORNO_RAIZ, str(destino))

    rutas = cargar_rutas()

    assert rutas.raiz == destino


def test_sin_raiz_explicita_ni_variable_de_entorno_usa_una_carpeta_del_home(monkeypatch, tmp_path) -> None:
    # Bug real 2026-07-30: este es el caso que antes resolvia a la ruta
    # Linux hardcodeada del consultor para CUALQUIER usuario, en
    # cualquier sistema operativo -- ahora depende del propio usuario
    # que corre la aplicacion (Path.home()), calculado en tiempo de
    # ejecucion, nunca de una cadena fija en el codigo fuente.
    monkeypatch.delenv(_VARIABLE_ENTORNO_RAIZ, raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    rutas = cargar_rutas()

    assert rutas.raiz == tmp_path / _NOMBRE_CARPETA_POR_DEFECTO
    assert rutas.raiz == tmp_path / "RAG Content Studio Desktop"


def test_rutas_derivadas_se_construyen_bajo_la_raiz_resuelta(tmp_path) -> None:
    rutas = cargar_rutas(raiz=tmp_path)

    assert rutas.aplicacion_db == tmp_path / "aplicacion.db"
    assert rutas.perfiles == tmp_path / "perfiles"
    assert rutas.proyectos == tmp_path / "proyectos"
    assert rutas.logs == tmp_path / "logs"
