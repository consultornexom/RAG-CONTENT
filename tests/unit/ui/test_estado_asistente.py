"""Pruebas de ui.wizard.estado_asistente -- modulo puro (Path/json, sin
PySide6), por eso vive junto a test_errores.py en tests/unit/ui: ambos
pueden correr sin necesitar una instalacion real de Qt (a diferencia del
resto de tests/smoke, que si instancia widgets reales)."""
from __future__ import annotations

from pathlib import Path

from ui.wizard.estado_asistente import guardar_etapa, leer_etapa

_NOMBRE_ARCHIVO = ".asistente_estado.json"


def test_leer_etapa_sin_archivo_devuelve_cero(tmp_path: Path) -> None:
    assert leer_etapa(str(tmp_path)) == 0


def test_guardar_y_leer_etapa_hacen_ida_y_vuelta(tmp_path: Path) -> None:
    guardar_etapa(str(tmp_path), 3)
    assert leer_etapa(str(tmp_path)) == 3


def test_leer_etapa_con_json_corrupto_devuelve_cero(tmp_path: Path) -> None:
    (tmp_path / _NOMBRE_ARCHIVO).write_text("esto no es json valido {{{", encoding="utf-8")
    assert leer_etapa(str(tmp_path)) == 0


def test_leer_etapa_con_json_valido_pero_no_objeto_devuelve_cero(tmp_path: Path) -> None:
    """Bug real encontrado en la auditoria 2026-08-24: el docstring de
    leer_etapa promete "nunca lanza", pero solo capturaba
    (OSError, ValueError, TypeError) -- un archivo con JSON VALIDO que no
    es un objeto (una lista, un numero, `null`, plausible ante una
    escritura parcial/carrera o una edicion manual) hace que
    `json.loads` no lance, pero `datos.get(...)` si, con AttributeError
    (fuera de la tupla capturada), propagandose sin capturar hasta el
    slot de Qt que abre el proyecto."""
    for contenido in ("[1, 2, 3]", "42", "null", '"solo texto"'):
        (tmp_path / _NOMBRE_ARCHIVO).write_text(contenido, encoding="utf-8")
        assert leer_etapa(str(tmp_path)) == 0, f"fallo con contenido {contenido!r}"


def test_guardar_etapa_no_lanza_si_la_carpeta_no_existe() -> None:
    # Documentado en el modulo: el autoguardado es una comodidad, nunca
    # debe romper el flujo del asistente -- ni siquiera si la ruta del
    # proyecto ya no existe (carpeta borrada/movida externamente).
    guardar_etapa("/ruta/que/no/existe/para/nada", 2)
