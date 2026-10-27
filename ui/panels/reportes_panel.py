"""Pantalla "Reportes" del menu funcional (Fase 11, Documento Maestro
seccion 4.11 y 7.1; Fase 8). `ReportsService` existia completo desde la
Fase 8 pero sin GUI -- esta pantalla es la primera forma de generar los
siete documentos de la seccion 7.1 sin usar la consola."""
from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.bootstrap import AppContext, ProjectContext
from domain.projects.entities import Proyecto
from ui.errores import mensaje_amigable

_INFORMES = (
    ("Inventario", "generar_informe_inventario"),
    ("Procesamiento", "generar_informe_procesamiento"),
    ("Revision", "generar_informe_revision"),
    ("Incidencias", "generar_informe_incidencias"),
    ("Calidad", "generar_informe_calidad"),
    ("Trazabilidad", "generar_informe_trazabilidad"),
)


class ReportesPanel(QWidget):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self.pctx: ProjectContext | None = None
        self.proyecto: Proyecto | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Reportes</b> (Documento Maestro, seccion 7.1)"))

        barra_informes = QHBoxLayout()
        self.boton_generar_todos = QPushButton("Generar los seis informes")
        self.boton_generar_todos.clicked.connect(self._on_generar_todos)
        barra_informes.addWidget(self.boton_generar_todos)
        for etiqueta, nombre_metodo in _INFORMES:
            boton = QPushButton(etiqueta)
            boton.clicked.connect(lambda _checked=False, m=nombre_metodo: self._on_generar_uno(m))
            barra_informes.addWidget(boton)
        barra_informes.addStretch()
        layout.addLayout(barra_informes)

        barra_acta = QHBoxLayout()
        barra_acta.addWidget(QLabel("Lote:"))
        self.combo_lotes = QComboBox()
        barra_acta.addWidget(self.combo_lotes)
        self.boton_acta = QPushButton("Generar acta de cierre del lote")
        self.boton_acta.clicked.connect(self._on_generar_acta)
        barra_acta.addWidget(self.boton_acta)
        barra_acta.addStretch()
        layout.addLayout(barra_acta)

        layout.addWidget(QLabel("Archivos generados (doble clic para abrir)"))
        self.lista_archivos = QListWidget()
        self.lista_archivos.itemDoubleClicked.connect(self._on_abrir_archivo)
        layout.addWidget(self.lista_archivos)

    def establecer_proyecto(self, pctx: ProjectContext | None, proyecto: Proyecto | None) -> None:
        self.pctx = pctx
        self.proyecto = proyecto
        self._cargar_lotes()

    def _cargar_lotes(self) -> None:
        self.combo_lotes.clear()
        if self.pctx is None or self.proyecto is None:
            return
        for lote in self.pctx.batches.listar_lotes(self.proyecto.id):
            self.combo_lotes.addItem(f"{lote.nombre} ({lote.estado.value})", lote.id)

    def _agregar_archivo_generado(self, ruta: str) -> None:
        item = QListWidgetItem(ruta)
        item.setData(256, ruta)  # Qt.UserRole == 256
        self.lista_archivos.addItem(item)

    def _on_generar_uno(self, nombre_metodo: str) -> None:
        if self.pctx is None:
            return
        try:
            ruta = getattr(self.pctx.reports, nombre_metodo)()
        except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(self, "No se pudo generar el informe", mensaje_amigable(exc))
            return
        self._agregar_archivo_generado(ruta)

    def _on_generar_todos(self) -> None:
        if self.pctx is None:
            return
        try:
            rutas = self.pctx.reports.generar_todos_los_informes()
        except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(self, "No se pudieron generar los informes", mensaje_amigable(exc))
            return
        for ruta in rutas.values():
            self._agregar_archivo_generado(ruta)

    def _on_generar_acta(self) -> None:
        lote_id = self.combo_lotes.currentData()
        if self.pctx is None or lote_id is None:
            return
        try:
            ruta = self.pctx.reports.generar_acta_cierre_lote(lote_id)
        except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(self, "No se pudo generar el acta", mensaje_amigable(exc))
            return
        self._agregar_archivo_generado(ruta)

    def _on_abrir_archivo(self, item: QListWidgetItem) -> None:
        ruta = item.data(256)
        if ruta:
            QDesktopServices.openUrl(QUrl.fromLocalFile(ruta))
