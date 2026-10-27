"""Renderiza paginas de un PDF a QPixmap para el visor dual del Modulo
8. Usa PyMuPDF (fitz) -- ya dependencia del nucleo (Modulo 6:
PdfOcrExtractor rasteriza paginas para OCR con la misma biblioteca);
esta es la unica pieza de `ui` que toca una biblioteca de terceros
directamente en vez de pasar por `application`, porque renderizar un
PDF a imagen es una necesidad puramente de presentacion, no un caso de
uso del nucleo."""
from __future__ import annotations

import fitz
from PySide6.QtGui import QPixmap

_DPI_VISTA_PREVIA = 100


def contar_paginas(ruta_pdf: str) -> int:
    with fitz.open(ruta_pdf) as documento:
        return documento.page_count


def render_pagina(ruta_pdf: str, indice_pagina: int) -> QPixmap:
    """indice_pagina: base 0. Devuelve un QPixmap en blanco (1x1) si la
    pagina no se puede renderizar -- quien llama decide como avisarlo,
    este modulo no lanza excepciones de UI."""
    try:
        with fitz.open(ruta_pdf) as documento:
            pagina = documento.load_page(indice_pagina)
            zoom = _DPI_VISTA_PREVIA / 72
            pixmap_fitz = pagina.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            imagen_png = pixmap_fitz.tobytes("png")
    except Exception:  # vista previa best-effort, nunca debe tumbar la ventana
        return QPixmap(1, 1)

    pixmap = QPixmap()
    # "PNG" como str, no bytes: en la version de PySide6/shiboken de
    # este proyecto, pasar el formato como bytes (b"PNG") hace que
    # loadFromData() falle con un ValueError de resolucion de overload
    # a pesar de que la firma publicada acepta bytes -- descubierto al
    # agregar la primera prueba de humo que renderiza un PDF real
    # dentro de la ventana principal (Modulo 8, navegacion sincronizada
    # real). Con str funciona de forma consistente.
    pixmap.loadFromData(imagen_png, "PNG")  # type: ignore[call-overload]  # ver comentario arriba: str, no bytes, a proposito.
    return pixmap
