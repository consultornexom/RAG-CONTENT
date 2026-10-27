from __future__ import annotations

from domain.documents.estructura_markdown import tiene_estructura_markdown


def test_texto_sin_encabezados_ni_tablas_no_tiene_estructura() -> None:
    assert tiene_estructura_markdown("Un parrafo simple, sin nada especial.") is False


def test_texto_vacio_no_tiene_estructura() -> None:
    assert tiene_estructura_markdown("") is False


def test_encabezado_h1_cuenta_como_estructura() -> None:
    assert tiene_estructura_markdown("# Titulo\n\nContenido.") is True


def test_encabezado_h3_cuenta_como_estructura() -> None:
    assert tiene_estructura_markdown("### Subseccion\n\nContenido.") is True


def test_numeral_sin_espacio_no_cuenta_como_encabezado() -> None:
    # "#etiqueta" no es un encabezado Markdown real -- evita falsos
    # positivos con hashtags o referencias.
    assert tiene_estructura_markdown("Texto con #etiqueta suelta.") is False


def test_tabla_markdown_real_cuenta_como_estructura() -> None:
    markdown = "| Columna A | Columna B |\n| --- | --- |\n| 1 | 2 |\n"
    assert tiene_estructura_markdown(markdown) is True


def test_fila_con_pipes_sin_separadora_no_cuenta_como_tabla() -> None:
    # Una sola linea con "|" (por ejemplo, una ruta de archivo escrita
    # entre pipes por error) no es una tabla Markdown real sin su fila
    # separadora "---".
    assert tiene_estructura_markdown("| esto no es una tabla |") is False


def test_texto_con_encabezado_y_tabla_sigue_contando_como_estructura() -> None:
    markdown = "# Politica\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n"
    assert tiene_estructura_markdown(markdown) is True
