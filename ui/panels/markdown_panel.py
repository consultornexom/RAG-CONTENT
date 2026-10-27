"""Pantalla "Markdown" del menu funcional (Fase 11, Documento Maestro
seccion 4.11 y Modulo 12). El Modulo 12 llegaba completo hasta LIBERADO
en el backend ("sin GUI, mismo criterio que el Modulo 9") -- esta
pantalla conecta los cuatro pasos que faltaban: aprobar para Markdown,
generar, validar y liberar, mas la entrega hacia RAG STUDIO.

El boton de entrega ya no solo genera el manifiesto (2026-07-31,
comentario real del consultor): ahora tambien consolida, en
14_entrega_rag_studio/, una copia de ese manifiesto y de cada Markdown
liberado que referencia -- ver DocumentsService.
preparar_entrega_rag_studio() y domain.documents.ports.
EntregaRagStudioStore."""
from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.bootstrap import AppContext, ProjectContext
from domain.projects.entities import Proyecto
from ui.dialogs import AprobadorDialog
from ui.theme import aplicar_color_estado
from ui.errores import mensaje_amigable


class MarkdownPanel(QWidget):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self.pctx: ProjectContext | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Markdown</b>"))

        self.tabla = QTableWidget(0, 2)
        self.tabla.setHorizontalHeaderLabels(["Documento", "Estado"])
        self.tabla.itemSelectionChanged.connect(self._on_seleccion_cambiada)
        layout.addWidget(self.tabla)

        barra = QHBoxLayout()
        self.boton_aprobar = QPushButton("Aprobar para Markdown")
        self.boton_aprobar.clicked.connect(self._on_aprobar)
        barra.addWidget(self.boton_aprobar)
        self.boton_generar = QPushButton("Generar Markdown")
        self.boton_generar.clicked.connect(self._on_generar)
        barra.addWidget(self.boton_generar)
        self.boton_validar = QPushButton("Validar Markdown")
        self.boton_validar.clicked.connect(self._on_validar)
        barra.addWidget(self.boton_validar)
        self.boton_liberar = QPushButton("Liberar documento")
        self.boton_liberar.clicked.connect(self._on_liberar)
        barra.addWidget(self.boton_liberar)
        barra.addStretch()
        layout.addLayout(barra)

        barra_entrega = QHBoxLayout()
        self.boton_preparar_entrega = QPushButton("Preparar entrega para RAG Studio (todo el proyecto)")
        self.boton_preparar_entrega.setToolTip(
            "Genera el manifiesto de entrega y ademas consolida una copia de ese "
            "manifiesto y de cada Markdown liberado en una sola carpeta "
            "(14_entrega_rag_studio), para no tener que ir a buscarlos por "
            "separado a 07_markdown y 12_exportaciones."
        )
        self.boton_preparar_entrega.clicked.connect(self._on_preparar_entrega_rag_studio)
        barra_entrega.addWidget(self.boton_preparar_entrega)
        barra_entrega.addStretch()
        layout.addLayout(barra_entrega)

        layout.addWidget(QLabel("Aprobaciones del documento seleccionado"))
        self.lista_aprobaciones = QListWidget()
        layout.addWidget(self.lista_aprobaciones)

    def establecer_proyecto(self, pctx: ProjectContext | None, proyecto: Proyecto | None) -> None:
        self.pctx = pctx
        self._cargar_tabla()

    def _cargar_tabla(self, seleccionar_id: str | None = None) -> None:
        # Preserva la seleccion a traves del recargue: aprobar -> generar
        # -> validar -> liberar es una cadena de pasos sobre el MISMO
        # documento (seccion 4.11.1, baja friccion); sin esto, cada paso
        # despues del primero exigiria reseleccionar el documento.
        if seleccionar_id is None:
            seleccionar_id = self._documento_id_seleccionado()
        self.tabla.setRowCount(0)
        self.lista_aprobaciones.clear()
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

    def _documento_id_seleccionado(self) -> str | None:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return None
        item = self.tabla.item(filas[0].row(), 0)
        return item.data(256) if item is not None else None

    def _on_seleccion_cambiada(self) -> None:
        self.lista_aprobaciones.clear()
        documento_id = self._documento_id_seleccionado()
        if self.pctx is None or documento_id is None:
            return
        try:
            aprobaciones = self.pctx.documents.listar_aprobaciones(documento_id)
        except RuntimeError:
            return  # Modulo 12 no configurado en este proyecto -- ver DocumentsService
        for aprobacion in aprobaciones:
            self.lista_aprobaciones.addItem(f"{aprobacion.aprobador} -- {aprobacion.comentario or 'sin comentario'}")

    def _on_aprobar(self) -> None:
        documento_id = self._documento_id_seleccionado()
        if self.pctx is None or documento_id is None:
            return
        dialogo = AprobadorDialog(self, "Aprobar para Markdown")
        if not dialogo.exec():
            return
        if not dialogo.aprobador():
            QMessageBox.warning(self, "Campo requerido", "Debe indicar quien aprueba.")
            return
        try:
            self.pctx.documents.aprobar_para_markdown(documento_id, dialogo.aprobador(), dialogo.comentario())
        except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(self, "No se pudo aprobar", mensaje_amigable(exc))
            return
        self._cargar_tabla(seleccionar_id=documento_id)

    def _on_generar(self) -> None:
        documento_id = self._documento_id_seleccionado()
        if self.pctx is None or documento_id is None:
            return
        try:
            self.pctx.documents.generar_markdown(documento_id)
        except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(self, "No se pudo generar el Markdown", mensaje_amigable(exc))
            return
        self._cargar_tabla(seleccionar_id=documento_id)

    def _on_validar(self) -> None:
        documento_id = self._documento_id_seleccionado()
        if self.pctx is None or documento_id is None:
            return
        try:
            self.pctx.documents.validar_markdown(documento_id)
        except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(self, "No se pudo validar", mensaje_amigable(exc))
            return
        self._cargar_tabla(seleccionar_id=documento_id)

    def _on_liberar(self) -> None:
        documento_id = self._documento_id_seleccionado()
        if self.pctx is None or documento_id is None:
            return
        try:
            self.pctx.documents.liberar_documento(documento_id)
        except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(self, "No se pudo liberar", mensaje_amigable(exc))
            return
        self._cargar_tabla(seleccionar_id=documento_id)

    def _on_preparar_entrega_rag_studio(self) -> None:
        if self.pctx is None:
            return
        try:
            ruta_carpeta = self.pctx.documents.preparar_entrega_rag_studio()
        except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(self, "No se pudo preparar la entrega", mensaje_amigable(exc))
            return
        QMessageBox.information(
            self,
            "Entrega preparada",
            f"Manifiesto y Markdown liberados listos para entregar en:\n{ruta_carpeta}",
        )
        QDesktopServices.openUrl(QUrl.fromLocalFile(ruta_carpeta))
