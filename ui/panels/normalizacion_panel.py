"""Pantalla "Normalizacion" del menu funcional (Fase 11, Documento
Maestro seccion 4.11 y Modulo 9). El Modulo 9 se construyo como
backend puro ("sin GUI, mismo criterio que el Modulo 12") -- esta
pantalla es la primera vez que se puede disparar desde la interfaz."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.bootstrap import AppContext, ProjectContext
from domain.documents.entities import EstadoDocumento
from domain.projects.entities import Proyecto
from ui.theme import aplicar_color_estado
from ui.errores import mensaje_amigable


class NormalizacionPanel(QWidget):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self.pctx: ProjectContext | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Normalizacion</b>"))

        self.tabla = QTableWidget(0, 2)
        self.tabla.setHorizontalHeaderLabels(["Nombre", "Estado"])
        self.tabla.itemSelectionChanged.connect(self._on_seleccion_cambiada)
        layout.addWidget(self.tabla)

        barra = QHBoxLayout()
        self.boton_normalizar = QPushButton("Normalizar documento seleccionado")
        self.boton_normalizar.clicked.connect(self._on_normalizar)
        self.boton_normalizar.setEnabled(False)
        barra.addWidget(self.boton_normalizar)
        barra.addStretch()
        layout.addLayout(barra)

        layout.addWidget(QLabel("Contenido normalizado"))
        self.texto_normalizado = QPlainTextEdit()
        self.texto_normalizado.setReadOnly(True)
        layout.addWidget(self.texto_normalizado)

        layout.addWidget(QLabel("Cambios aplicados (transparencia, Documento Maestro seccion 4.6)"))
        self.lista_cambios = QListWidget()
        layout.addWidget(self.lista_cambios)

    def establecer_proyecto(self, pctx: ProjectContext | None, proyecto: Proyecto | None) -> None:
        self.pctx = pctx
        self._cargar_tabla()

    def _cargar_tabla(self, seleccionar_id: str | None = None) -> None:
        # Mismo criterio que procesamiento/incidencias/markdown: preserva
        # la seleccion a traves del recargue (seccion 4.11.1, baja
        # friccion).
        if seleccionar_id is None:
            seleccionar_id = self._documento_seleccionado_id()
        self.tabla.setRowCount(0)
        self.texto_normalizado.clear()
        self.lista_cambios.clear()
        if self.pctx is None:
            return
        documentos = self.pctx.documents.listar_documentos()
        self.tabla.setRowCount(len(documentos))
        fila_a_seleccionar = None
        for fila, documento in enumerate(documentos):
            item_nombre = QTableWidgetItem(documento.nombre_original)
            item_nombre.setData(256, documento.id)  # Qt.UserRole == 256
            self.tabla.setItem(fila, 0, item_nombre)
            item_estado = QTableWidgetItem(documento.estado.value)
            aplicar_color_estado(item_estado, documento.estado.value)
            self.tabla.setItem(fila, 1, item_estado)
            if seleccionar_id is not None and documento.id == seleccionar_id:
                fila_a_seleccionar = fila
        if fila_a_seleccionar is not None:
            self.tabla.selectRow(fila_a_seleccionar)

    def _documento_seleccionado_id(self) -> str | None:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return None
        item = self.tabla.item(filas[0].row(), 0)
        return item.data(256) if item is not None else None

    def _on_seleccion_cambiada(self) -> None:
        self.texto_normalizado.clear()
        self.lista_cambios.clear()
        documento_id = self._documento_seleccionado_id()
        if self.pctx is None or documento_id is None:
            self.boton_normalizar.setEnabled(False)
            return
        documento = self.pctx.documents.obtener_documento(documento_id)
        if documento is None:
            self.boton_normalizar.setEnabled(False)
            return
        # normalizar_documento() exige REVISADO (Modulo 9) -- UX
        # proactiva, mismo criterio que el resto de esta capa.
        self.boton_normalizar.setEnabled(documento.estado == EstadoDocumento.REVISADO)
        if documento.ruta_normalizado is not None:
            try:
                contenido = Path(documento.ruta_normalizado).read_text(encoding="utf-8")
                self.texto_normalizado.setPlainText(contenido)
            except OSError as exc:
                self.texto_normalizado.setPlainText(f"No se pudo leer '{documento.ruta_normalizado}': {mensaje_amigable(exc)}")
            self.lista_cambios.addItems(documento.cambios_normalizacion or ["Sin cambios registrados."])

    def _on_normalizar(self) -> None:
        documento_id = self._documento_seleccionado_id()
        if self.pctx is None or documento_id is None:
            return
        try:
            self.pctx.documents.normalizar_documento(documento_id)
        except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(self, "No se pudo normalizar", mensaje_amigable(exc))
            return
        self._cargar_tabla(seleccionar_id=documento_id)
