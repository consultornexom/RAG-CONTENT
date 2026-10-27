"""Prueba de humo de `ui/editor_texto.py` (Modulo 8, editor de
"Normalizado" con numeros de renglon, ir-a-renglon y buscar/reemplazar),
agregado a pedido explicito de un usuario real -- ver el docstring del
modulo bajo prueba para el detalle de la decision de diseno. Mismo
patron que el resto de tests/smoke/test_*.py: `pytest.importorskip`
para no exigir PySide6/Qt a quien no vaya a tocar la GUI."""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from ui.editor_texto import BuscarReemplazarDialog, EditorConNumerosDeLinea  # noqa: E402


def test_ir_a_linea_valida_mueve_el_cursor(qtbot) -> None:
    editor = EditorConNumerosDeLinea()
    qtbot.addWidget(editor)
    editor.setPlainText("uno\ndos\ntres\ncuatro")

    assert editor.ir_a_linea(3) is True
    assert editor.textCursor().blockNumber() == 2  # renglon 3, 0-indexado


def test_ir_a_linea_fuera_de_rango_no_lanza_y_devuelve_false(qtbot) -> None:
    editor = EditorConNumerosDeLinea()
    qtbot.addWidget(editor)
    editor.setPlainText("uno\ndos")

    assert editor.ir_a_linea(0) is False
    assert editor.ir_a_linea(99) is False


def test_ancho_area_numeros_crece_con_mas_renglones(qtbot) -> None:
    editor = EditorConNumerosDeLinea()
    qtbot.addWidget(editor)
    editor.setPlainText("solo un renglon")
    ancho_pocos_digitos = editor.ancho_area_numeros_linea()

    editor.setPlainText("\n".join(str(n) for n in range(200)))  # 200 renglones -> 3 digitos
    ancho_muchos_digitos = editor.ancho_area_numeros_linea()

    assert ancho_muchos_digitos > ancho_pocos_digitos


def test_buscar_siguiente_encuentra_texto(qtbot) -> None:
    editor = EditorConNumerosDeLinea()
    qtbot.addWidget(editor)
    editor.setPlainText("el rapido zorro salta el charco")

    dialogo = BuscarReemplazarDialog(None, editor, permitir_reemplazar=True)
    qtbot.addWidget(dialogo)
    dialogo.campo_buscar.setText("zorro")

    assert dialogo._buscar_siguiente() is True
    assert editor.textCursor().selectedText() == "zorro"


def test_buscar_texto_inexistente_deja_el_cursor_sin_cambios(qtbot) -> None:
    editor = EditorConNumerosDeLinea()
    qtbot.addWidget(editor)
    editor.setPlainText("contenido sin la palabra buscada")
    posicion_inicial = editor.textCursor().position()

    dialogo = BuscarReemplazarDialog(None, editor, permitir_reemplazar=True)
    qtbot.addWidget(dialogo)
    dialogo.campo_buscar.setText("no-existe-esto")

    assert dialogo._buscar_siguiente() is False
    assert editor.textCursor().position() == posicion_inicial
    assert "No se encontro" in dialogo.etiqueta_resultado.text()


def test_reemplazar_todo_cuenta_y_aplica_los_reemplazos(qtbot) -> None:
    editor = EditorConNumerosDeLinea()
    qtbot.addWidget(editor)
    editor.setPlainText("gato gato gato")

    dialogo = BuscarReemplazarDialog(None, editor, permitir_reemplazar=True)
    qtbot.addWidget(dialogo)
    dialogo.campo_buscar.setText("gato")
    dialogo.campo_reemplazar.setText("perro")
    dialogo._reemplazar_todo()

    assert editor.toPlainText() == "perro perro perro"
    assert "3 reemplazo" in dialogo.etiqueta_resultado.text()


def test_permitir_reemplazar_falso_deshabilita_controles_de_reemplazo(qtbot) -> None:
    editor = EditorConNumerosDeLinea()
    qtbot.addWidget(editor)
    editor.setPlainText("texto de solo lectura")
    editor.setReadOnly(True)

    dialogo = BuscarReemplazarDialog(None, editor, permitir_reemplazar=False)
    qtbot.addWidget(dialogo)

    assert dialogo.campo_reemplazar.isEnabled() is False
    assert dialogo.boton_reemplazar.isEnabled() is False
    assert dialogo.boton_reemplazar_todo.isEnabled() is False
    # Buscar debe seguir funcionando aunque no se pueda reemplazar.
    dialogo.campo_buscar.setText("lectura")
    assert dialogo._buscar_siguiente() is True
