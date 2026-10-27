"""Editor de texto para el panel "Normalizado" de la pantalla Revision
(Modulo 8), agregado a pedido explicito de un usuario real (2026-09-04):
"se puedan llevar a cabo acciones del tipo Edicion, similar a como lo
haria un editor de textos... Busquedas, reemplazos, activar numeros de
renglon, ir a un renglon, cortar, copiar, pegar". Cortar/copiar/pegar,
deshacer/rehacer y seleccionar todo ya los trae `QPlainTextEdit` de
fabrica (Ctrl+X/C/V/Z/Y/A y menu contextual con clic derecho) -- lo que
faltaba de verdad era numeros de renglon, buscar y reemplazar, e ir a un
renglon especifico, que es lo que agrega este modulo.

Decision de diseno (2026-09-04, confirmada con el consultor): todo se
integra en la MISMA ventana -- ver `_construir_pagina_revision()` en
`ui/main_window.py`, que ya tenia el patron de paneles plegables
("Ocultar documentos"/"Ocultar estado") para darle mas espacio al visor
central cuando hace falta. Se agrega un tercer boton simetrico
("Ocultar original") en vez de abrir una ventana aparte -- una ventana
independiente exige sincronizar su contenido cada vez que cambia el
documento o el proyecto abierto (o cerrarla a la fuerza si el proyecto
se archiva/elimina mientras esta abierta, ver el hallazgo de
`_on_proyecto_modificado_desde_panel` de la auditoria anterior), riesgo
que no se justifica frente a simplemente ocultar el panel opuesto en el
mismo splitter que ya existia.

Importante (verificado leyendo el codigo real de `main_window.py`,
`_resaltar_baja_confianza()`): `EditorConNumerosDeLinea` NO debe resaltar
la linea actual via `setExtraSelections()` -- ese metodo ya lo usa
`_resaltar_baja_confianza()` para el fondo ambar de las palabras de baja
confianza de OCR (Nivel 1), y `setExtraSelections()` reemplaza TODA la
lista de una sola vez; si este editor tambien la tocara en cada
movimiento del cursor, borraria el resaltado de baja confianza en
cuanto el usuario hiciera clic para editar. El gutter de numeros de
renglon se dibuja aparte, en su propio widget lateral (`_AreaNumerosDeLinea`),
sin tocar `setExtraSelections()` en ningun momento -- no hay conflicto
posible con ese mecanismo."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QTextCursor, QTextDocument
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

_COLOR_FONDO_GUTTER = QColor(238, 238, 238)
_COLOR_TEXTO_GUTTER = QColor(120, 120, 120)


class _AreaNumerosDeLinea(QWidget):
    """Widget lateral angosto que solo sabe pedirle su ancho y su pintado
    al editor duenio -- patron estandar de Qt para gutters de numero de
    renglon (el propio editor hace el calculo real, este widget solo
    delega, para no duplicar estado)."""

    def __init__(self, editor: "EditorConNumerosDeLinea") -> None:
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:  # noqa: N802 - nombre impuesto por Qt
        return QSize(self._editor.ancho_area_numeros_linea(), 0)

    def paintEvent(self, event) -> None:  # noqa: N802 - nombre impuesto por Qt
        self._editor.pintar_area_numeros_linea(event)


class EditorConNumerosDeLinea(QPlainTextEdit):
    """`QPlainTextEdit` con un gutter de numeros de renglon a la
    izquierda. Cortar/copiar/pegar/deshacer/rehacer/seleccionar todo son
    los que ya trae Qt de fabrica -- esta subclase solo agrega los
    numeros y el metodo `ir_a_linea()`; `BuscarReemplazarDialog` (mas
    abajo) opera sobre cualquier `QPlainTextEdit`, incluido este."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._area_numeros = _AreaNumerosDeLinea(self)
        self.blockCountChanged.connect(self._actualizar_ancho_area_numeros)
        self.updateRequest.connect(self._actualizar_area_numeros)
        self._actualizar_ancho_area_numeros(0)

    def ancho_area_numeros_linea(self) -> int:
        digitos = 1
        maximo = max(1, self.blockCount())
        while maximo >= 10:
            maximo //= 10
            digitos += 1
        return 10 + self.fontMetrics().horizontalAdvance("9") * digitos

    def _actualizar_ancho_area_numeros(self, _nuevo_conteo_bloques: int = 0) -> None:
        self.setViewportMargins(self.ancho_area_numeros_linea(), 0, 0, 0)

    def _actualizar_area_numeros(self, rect: QRect, dy: int) -> None:
        if dy:
            self._area_numeros.scroll(0, dy)
        else:
            self._area_numeros.update(0, rect.y(), self._area_numeros.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._actualizar_ancho_area_numeros()

    def resizeEvent(self, event) -> None:  # noqa: N802 - nombre impuesto por Qt
        super().resizeEvent(event)
        rect = self.contentsRect()
        self._area_numeros.setGeometry(QRect(rect.left(), rect.top(), self.ancho_area_numeros_linea(), rect.height()))

    def pintar_area_numeros_linea(self, event) -> None:
        painter = QPainter(self._area_numeros)
        painter.fillRect(event.rect(), _COLOR_FONDO_GUTTER)
        bloque = self.firstVisibleBlock()
        numero_bloque = bloque.blockNumber()
        top = round(self.blockBoundingGeometry(bloque).translated(self.contentOffset()).top())
        alto_bloque = round(self.blockBoundingRect(bloque).height())
        bottom = top + alto_bloque
        alto_fuente = self.fontMetrics().height()
        while bloque.isValid() and top <= event.rect().bottom():
            if bloque.isVisible() and bottom >= event.rect().top():
                painter.setPen(_COLOR_TEXTO_GUTTER)
                painter.drawText(
                    0,
                    top,
                    self._area_numeros.width() - 6,
                    alto_fuente,
                    Qt.AlignmentFlag.AlignRight,
                    str(numero_bloque + 1),
                )
            bloque = bloque.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(bloque).height())
            numero_bloque += 1

    def ir_a_linea(self, numero: int) -> bool:
        """Mueve el cursor al inicio del renglon `numero` (1-indexado) y
        lo centra en la vista. Devuelve False sin hacer nada si el
        numero esta fuera de rango -- nunca lanza."""
        if numero < 1 or numero > self.blockCount():
            return False
        bloque = self.document().findBlockByNumber(numero - 1)
        cursor = self.textCursor()
        cursor.setPosition(bloque.position())
        self.setTextCursor(cursor)
        self.centerCursor()
        self.setFocus()
        return True


class BuscarReemplazarDialog(QDialog):
    """Buscar/reemplazar sobre cualquier `QPlainTextEdit` (no solo
    `EditorConNumerosDeLinea`) -- reutiliza `QTextDocument.find()`, que
    Qt ya implementa de forma correcta y eficiente, en vez de reescribir
    una busqueda de texto a mano.

    Si `permitir_reemplazar` es False (documento de solo lectura, fuera
    del estado EXTRAIDO -- ver `Documento.corregir()`), los controles de
    reemplazo quedan deshabilitados pero la busqueda sigue funcionando
    normalmente: buscar nunca modifica el documento, asi que no hay
    ninguna razon para bloquearla solo porque no se puede editar."""

    def __init__(self, parent: Optional[QWidget], editor: QPlainTextEdit, permitir_reemplazar: bool) -> None:
        super().__init__(parent)
        self.setWindowTitle("Buscar y reemplazar")
        self._editor = editor

        self.campo_buscar = QLineEdit()
        self.campo_reemplazar = QLineEdit()
        self.casilla_mayus_minus = QCheckBox("Coincidir mayusculas/minusculas")
        self.casilla_palabra_completa = QCheckBox("Solo palabra completa")

        formulario = QFormLayout()
        formulario.addRow("Buscar:", self.campo_buscar)
        formulario.addRow("Reemplazar por:", self.campo_reemplazar)
        formulario.addRow("", self.casilla_mayus_minus)
        formulario.addRow("", self.casilla_palabra_completa)

        boton_anterior = QPushButton("Buscar anterior")
        boton_anterior.clicked.connect(self._buscar_anterior)
        boton_siguiente = QPushButton("Buscar siguiente")
        boton_siguiente.clicked.connect(self._buscar_siguiente)
        boton_siguiente.setDefault(True)
        self.boton_reemplazar = QPushButton("Reemplazar")
        self.boton_reemplazar.clicked.connect(self._reemplazar_actual)
        self.boton_reemplazar_todo = QPushButton("Reemplazar todo")
        self.boton_reemplazar_todo.clicked.connect(self._reemplazar_todo)
        boton_cerrar = QPushButton("Cerrar")
        boton_cerrar.clicked.connect(self.close)

        fila_botones = QHBoxLayout()
        fila_botones.addWidget(boton_anterior)
        fila_botones.addWidget(boton_siguiente)
        fila_botones.addWidget(self.boton_reemplazar)
        fila_botones.addWidget(self.boton_reemplazar_todo)
        fila_botones.addStretch()
        fila_botones.addWidget(boton_cerrar)

        self.etiqueta_resultado = QLabel("")
        self.etiqueta_resultado.setWordWrap(True)

        if not permitir_reemplazar:
            self.campo_reemplazar.setEnabled(False)
            self.boton_reemplazar.setEnabled(False)
            self.boton_reemplazar_todo.setEnabled(False)
            self.etiqueta_resultado.setText(
                "Este documento es de solo lectura (no esta en estado EXTRAIDO) -- puede buscar, pero no reemplazar."
            )

        layout = QVBoxLayout(self)
        layout.addLayout(formulario)
        layout.addLayout(fila_botones)
        layout.addWidget(self.etiqueta_resultado)

    def _flags(self, hacia_atras: bool = False) -> QTextDocument.FindFlag:
        flags = QTextDocument.FindFlag(0)
        if self.casilla_mayus_minus.isChecked():
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        if self.casilla_palabra_completa.isChecked():
            flags |= QTextDocument.FindFlag.FindWholeWords
        if hacia_atras:
            flags |= QTextDocument.FindFlag.FindBackward
        return flags

    def _buscar(self, hacia_atras: bool) -> bool:
        """Busca desde la posicion actual del cursor; si no encuentra
        nada hasta el final (o el principio, buscando hacia atras),
        reintenta una vez desde el extremo opuesto -- busqueda
        "circular", el comportamiento esperado de cualquier editor de
        texto comun. Si tampoco encuentra nada asi, deja el cursor
        exactamente donde estaba."""
        texto = self.campo_buscar.text()
        if not texto:
            return False
        cursor_antes = self._editor.textCursor()
        if self._editor.find(texto, self._flags(hacia_atras)):
            self.etiqueta_resultado.setText("")
            return True
        cursor_extremo = self._editor.textCursor()
        operacion = QTextCursor.MoveOperation.Start if hacia_atras else QTextCursor.MoveOperation.End
        cursor_extremo.movePosition(operacion)
        self._editor.setTextCursor(cursor_extremo)
        if self._editor.find(texto, self._flags(hacia_atras)):
            self.etiqueta_resultado.setText("")
            return True
        self._editor.setTextCursor(cursor_antes)
        self.etiqueta_resultado.setText(f"No se encontro \"{texto}\".")
        return False

    def _buscar_siguiente(self) -> bool:
        return self._buscar(hacia_atras=False)

    def _buscar_anterior(self) -> bool:
        return self._buscar(hacia_atras=True)

    def _seleccion_coincide_con_busqueda(self) -> bool:
        seleccion = self._editor.textCursor().selectedText()
        texto = self.campo_buscar.text()
        if self.casilla_mayus_minus.isChecked():
            return seleccion == texto
        return seleccion.lower() == texto.lower()

    def _reemplazar_actual(self) -> None:
        if not self.campo_buscar.text():
            return
        cursor = self._editor.textCursor()
        if cursor.hasSelection() and self._seleccion_coincide_con_busqueda():
            cursor.insertText(self.campo_reemplazar.text())
            self._editor.setTextCursor(cursor)
        self._buscar_siguiente()

    def _reemplazar_todo(self) -> None:
        texto_buscar = self.campo_buscar.text()
        if not texto_buscar:
            return
        cursor_original = self._editor.textCursor()
        cursor_inicio = self._editor.textCursor()
        cursor_inicio.movePosition(QTextCursor.MoveOperation.Start)
        self._editor.setTextCursor(cursor_inicio)
        reemplazos = 0
        while self._editor.find(texto_buscar, self._flags()):
            cursor_encontrado = self._editor.textCursor()
            cursor_encontrado.insertText(self.campo_reemplazar.text())
            self._editor.setTextCursor(cursor_encontrado)
            reemplazos += 1
        if reemplazos == 0:
            self._editor.setTextCursor(cursor_original)
            self.etiqueta_resultado.setText(f"No se encontro \"{texto_buscar}\".")
        else:
            self.etiqueta_resultado.setText(f"{reemplazos} reemplazo(s) realizado(s).")
