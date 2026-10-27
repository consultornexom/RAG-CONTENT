"""Pantalla "Vigencias" del menu funcional (Fase 11, Documento Maestro
seccion 4.11 y Modulo 11). Vista de solo lectura de TODO el proyecto --
registrar o corregir la vigencia de un documento puntual sigue viviendo
en "Revision" (Modulo 8, mismo dialogo `RegistrarVigenciaDialog`
reutilizado desde ahi); esta pantalla existe para ver de un vistazo
cuantos documentos criticos siguen con vigencia DESCONOCIDA sin tener
que abrirlos uno por uno."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from app.bootstrap import AppContext, ProjectContext
from domain.documents.entities import Criticidad
from domain.projects.entities import Proyecto
from domain.validity.entities import vigencia_desconocida


class VigenciasPanel(QWidget):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self.pctx: ProjectContext | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Vigencias</b>"))
        layout.addWidget(
            QLabel("Los documentos criticos con vigencia DESCONOCIDA no pueden aprobarse (Modulo 13).")
        )

        self.tabla = QTableWidget(0, 5)
        self.tabla.setHorizontalHeaderLabels(["Documento", "ID", "Critico", "Fuente", "Vigencia"])
        self.tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.tabla)

    def establecer_proyecto(self, pctx: ProjectContext | None, proyecto: Proyecto | None) -> None:
        self.pctx = pctx
        self._cargar_tabla()

    def _cargar_tabla(self) -> None:
        self.tabla.setRowCount(0)
        if self.pctx is None:
            return
        documentos = self.pctx.documents.listar_documentos()
        self.tabla.setRowCount(len(documentos))
        for fila, documento in enumerate(documentos):
            fuente = self.pctx.validity.obtener_fuente(documento.id)
            vigencia = self.pctx.validity.obtener_vigencia(documento.id)
            self.tabla.setItem(fila, 0, QTableWidgetItem(documento.nombre_original))
            item_id = QTableWidgetItem(documento.id)
            item_id.setFlags(item_id.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item_id.setToolTip("ID del documento -- usalo en el campo 'Sustituye a' al registrar una vigencia de reemplazo.")
            self.tabla.setItem(fila, 1, item_id)
            self.tabla.setItem(
                fila, 2, QTableWidgetItem("si" if documento.criticidad == Criticidad.CRITICO else "no")
            )
            self.tabla.setItem(fila, 3, QTableWidgetItem(fuente.sistema_origen if fuente else "sin registrar"))
            if vigencia is None:
                texto_vigencia = "sin registrar"
            elif vigencia_desconocida(vigencia):
                texto_vigencia = "DESCONOCIDA"
            elif vigencia.sin_vencimiento:
                texto_vigencia = "vigente, sin vencimiento"
            else:
                texto_vigencia = f"vigente hasta {vigencia.vigente_hasta}"
            self.tabla.setItem(fila, 4, QTableWidgetItem(texto_vigencia))
