"""Pantalla "Auditoria" del menu funcional (Fase 11, Documento Maestro
seccion 4.11 y 4.1). El registro de auditoria existe y se escribe desde
la Fase 1 (`ctx.audit.record()`, invocado por casi todos los casos de
uso) pero, hasta `AuditLogger.list_by_project()` (agregado en esta
misma fase), nada podia leerlo de vuelta -- esta pantalla es la primera
forma de verlo. Usa `ctx.audit` (la base global), no `pctx` -- la
auditoria vive en `aplicacion.db`, no en `proyecto.db` (ver el
comentario de `app.bootstrap.abrir_proyecto` sobre esta desviacion
conocida)."""
from __future__ import annotations

from PySide6.QtWidgets import QHeaderView, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from app.bootstrap import AppContext, ProjectContext
from domain.projects.entities import Proyecto

# Hallazgo real de la cuarta auditoria general (2026-08-01): esta tabla
# crece con CADA accion mutadora del sistema (mas de 30 comandos
# distintos la invocan, y desde que CerrarLote audita cada documento por
# separado, con la cantidad de documentos por lote) -- antes esta
# pantalla traia TODAS las filas del proyecto a memoria Python y las
# renderizaba sin ningun limite. 500 es un techo generoso para lo que un
# operador humano puede revisar linea por linea en una sola pantalla; una
# pagina de "cargar mas"/paginacion real queda fuera de alcance de este
# ajuste puntual (mismo criterio de "acotado deliberadamente" que el
# resto de esta fase) -- se avisa explicitamente en pantalla cuando se
# alcanza el limite, en vez de truncar en silencio.
_MAX_EVENTOS = 500


class AuditoriaPanel(QWidget):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self.proyecto: Proyecto | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Auditoria</b>"))

        boton_actualizar = QPushButton("Actualizar")
        boton_actualizar.clicked.connect(self._cargar_tabla)
        layout.addWidget(boton_actualizar)

        self.etiqueta_limite = QLabel("")
        layout.addWidget(self.etiqueta_limite)

        self.tabla = QTableWidget(0, 5)
        self.tabla.setHorizontalHeaderLabels(["Fecha", "Accion", "Valor anterior", "Valor nuevo", "Motivo"])
        self.tabla.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.tabla)

    def establecer_proyecto(self, pctx: ProjectContext | None, proyecto: Proyecto | None) -> None:
        self.proyecto = proyecto
        self._cargar_tabla()

    def _cargar_tabla(self) -> None:
        self.tabla.setRowCount(0)
        self.etiqueta_limite.setText("")
        if self.proyecto is None:
            return
        eventos = self.ctx.audit.list_by_project(self.proyecto.id, limite=_MAX_EVENTOS)
        if len(eventos) == _MAX_EVENTOS:
            self.etiqueta_limite.setText(
                f"Mostrando los {_MAX_EVENTOS} eventos mas recientes -- puede haber eventos "
                "anteriores no mostrados aqui."
            )
        self.tabla.setRowCount(len(eventos))
        for fila, evento in enumerate(eventos):
            self.tabla.setItem(fila, 0, QTableWidgetItem(evento.fecha.isoformat()))
            self.tabla.setItem(fila, 1, QTableWidgetItem(evento.accion))
            self.tabla.setItem(fila, 2, QTableWidgetItem(evento.valor_anterior or ""))
            self.tabla.setItem(fila, 3, QTableWidgetItem(evento.valor_nuevo or ""))
            self.tabla.setItem(fila, 4, QTableWidgetItem(evento.motivo))
