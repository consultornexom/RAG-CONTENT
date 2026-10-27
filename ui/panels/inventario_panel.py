"""Pantalla "Inventario" del menu funcional (Fase 11, Documento Maestro
seccion 4.11 y Modulo 3). Solo cubre "agregar y ver" -- la clasificacion
y extraccion viven en la pantalla "Procesamiento", y la revision en
"Revision" (Modulo 8, ya existente), para no duplicar acciones entre
pantallas."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.bootstrap import AppContext, ProjectContext
from domain.documents.exceptions import DuplicateDocumentHashError
from domain.projects.entities import Proyecto
from ui.theme import aplicar_color_estado
from ui.errores import mensaje_amigable


class InventarioPanel(QWidget):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self.pctx: ProjectContext | None = None
        self.proyecto: Proyecto | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Inventario</b>"))

        barra = QHBoxLayout()
        self.boton_agregar = QPushButton("Agregar documento(s)...")
        self.boton_agregar.clicked.connect(self._on_agregar_documentos)
        self.boton_agregar.setEnabled(False)
        barra.addWidget(self.boton_agregar)
        barra.addStretch()
        # Boton nuevo (2026-09-04, pedido explicito de un usuario real: para
        # sustituir un documento con error hace falta su ID, y hasta ahora
        # solo se podia obtener abriendo el archivo fuera de la herramienta.
        # La columna "ID" de abajo ya lo muestra; este boton evita tener que
        # editar la celda a mano para copiarlo.
        self.boton_copiar_id = QPushButton("Copiar ID")
        self.boton_copiar_id.setToolTip("Copia al portapapeles el ID del documento seleccionado (para usarlo en 'Sustituye a').")
        self.boton_copiar_id.setEnabled(False)
        self.boton_copiar_id.clicked.connect(self._on_copiar_id)
        barra.addWidget(self.boton_copiar_id)
        layout.addLayout(barra)

        self.tabla = QTableWidget(0, 7)
        self.tabla.setHorizontalHeaderLabels(
            ["Nombre", "ID", "Formato", "Estado", "Prioridad", "Criticidad", "Hash (primeros 12)"]
        )
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.itemSelectionChanged.connect(self._actualizar_boton_copiar_id)
        layout.addWidget(self.tabla)

    def establecer_proyecto(self, pctx: ProjectContext | None, proyecto: Proyecto | None) -> None:
        self.pctx = pctx
        self.proyecto = proyecto
        self.boton_agregar.setEnabled(pctx is not None)
        self._cargar_tabla()

    def _cargar_tabla(self) -> None:
        self.tabla.setRowCount(0)
        self._actualizar_boton_copiar_id()
        if self.pctx is None:
            return
        documentos = self.pctx.documents.listar_documentos()
        self.tabla.setRowCount(len(documentos))
        for fila, documento in enumerate(documentos):
            self.tabla.setItem(fila, 0, QTableWidgetItem(documento.nombre_original))
            item_id = QTableWidgetItem(documento.id)
            item_id.setFlags(item_id.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item_id.setToolTip("ID del documento -- usalo en el campo 'Sustituye a' al registrar una vigencia de reemplazo.")
            self.tabla.setItem(fila, 1, item_id)
            self.tabla.setItem(fila, 2, QTableWidgetItem(documento.formato.value))
            item_estado = QTableWidgetItem(documento.estado.value)
            aplicar_color_estado(item_estado, documento.estado.value)
            self.tabla.setItem(fila, 3, item_estado)
            self.tabla.setItem(fila, 4, QTableWidgetItem(documento.prioridad.value))
            self.tabla.setItem(fila, 5, QTableWidgetItem(documento.criticidad.value))
            self.tabla.setItem(fila, 6, QTableWidgetItem(documento.hash_sha256[:12]))

    def _actualizar_boton_copiar_id(self) -> None:
        self.boton_copiar_id.setEnabled(bool(self.tabla.selectedItems()))

    def _on_copiar_id(self) -> None:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return
        item_id = self.tabla.item(filas[0].row(), 1)
        if item_id is None:
            return
        QGuiApplication.clipboard().setText(item_id.text())

    def _on_agregar_documentos(self) -> None:
        if self.pctx is None or self.proyecto is None:
            return
        rutas, _ = QFileDialog.getOpenFileNames(self, "Agregar documentos al inventario")
        if not rutas:
            return
        omitidos: list[str] = []
        errores: list[str] = []
        for ruta in rutas:
            try:
                self.pctx.documents.registrar_documento(proyecto_id=self.proyecto.id, ruta_origen=str(Path(ruta)))
            except DuplicateDocumentHashError:
                omitidos.append(Path(ruta).name)
            except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
                errores.append(f"{Path(ruta).name}: {mensaje_amigable(exc)}")
        self._cargar_tabla()
        if omitidos:
            QMessageBox.information(
                self,
                "Duplicados omitidos",
                "Ya existian en el inventario (mismo hash SHA-256), no se agregaron de nuevo:\n"
                + "\n".join(omitidos),
            )
        if errores:
            QMessageBox.critical(self, "Algunos documentos no se pudieron agregar", "\n".join(errores))
