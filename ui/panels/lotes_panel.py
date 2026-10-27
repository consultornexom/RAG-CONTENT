"""Pantalla "Lotes" del menu funcional (hallazgo real de la cuarta
auditoria general, 2026-08-01): Modo Avanzado no tenia ninguna forma de
crear o cerrar un lote fuera del asistente por etapas
(`ui.wizard.etapas.EtapaCerrarLote` solo cierra, y ni siquiera crea).
Un operador que quisiera trabajar por lotes sin pasar por el asistente
completo -- por ejemplo, para agrupar documentos ya inventariados antes
de decidir como procesarlos -- no tenia donde hacerlo. Panel minimo,
consistente con el resto de `ui.panels.*`: solo expone
`BatchesService.crear_lote()`/`cerrar_lote()` (mas listar, para ver el
estado actual), sin duplicar nada de lo que ya hace el asistente."""
from __future__ import annotations

from PySide6.QtWidgets import (
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
from domain.batches.entities import EstadoLote
from domain.projects.entities import Proyecto
from ui.dialogs import TextoSimpleDialog
from ui.errores import mensaje_amigable
from ui.theme import aplicar_color_estado


class LotesPanel(QWidget):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self.pctx: ProjectContext | None = None
        self.proyecto: Proyecto | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Lotes</b>"))

        self.tabla = QTableWidget(0, 3)
        self.tabla.setHorizontalHeaderLabels(["Nombre", "Estado", "Documentos"])
        layout.addWidget(self.tabla)

        barra = QHBoxLayout()
        self.boton_nuevo = QPushButton("Nuevo lote")
        self.boton_nuevo.clicked.connect(self._on_nuevo)
        barra.addWidget(self.boton_nuevo)
        self.boton_cerrar = QPushButton("Cerrar lote")
        self.boton_cerrar.clicked.connect(self._on_cerrar)
        barra.addWidget(self.boton_cerrar)
        # Agregado 2026-10-03 (NEXOM, Solicitud_Ajustes_RAG_Content_Lotes_y_
        # Portabilidad.pdf, seccion 3: "informar por separado el resultado
        # del cierre y de la exportacion... permitir reintentar la entrega
        # sin crear otro lote"): independiente de _on_cerrar -- un lote ya
        # CERRADO puede volver a exportar su entrega (por ejemplo, si la
        # primera exportacion fallo por permisos de escritura) sin tocar su
        # estado ni crear ningun lote nuevo. Cada corrida usa una carpeta de
        # version propia (ver LocalEntregaRagStudioStore.preparar()), asi
        # que nunca sobrescribe una entrega anterior de este mismo lote.
        self.boton_exportar = QPushButton("Exportar entrega de este lote...")
        self.boton_exportar.clicked.connect(self._on_exportar_entrega)
        barra.addWidget(self.boton_exportar)
        barra.addStretch()
        layout.addLayout(barra)

    def establecer_proyecto(self, pctx: ProjectContext | None, proyecto: Proyecto | None) -> None:
        self.pctx = pctx
        self.proyecto = proyecto
        self._cargar_tabla()

    def _cargar_tabla(self, seleccionar_id: str | None = None) -> None:
        # Preserva la seleccion a traves del recargue -- mismo criterio
        # que el resto de paneles (seccion 4.11.1, baja friccion): sin
        # esto, cerrar un lote recien creado exigiria volver a
        # seleccionarlo despues de cada refresco.
        if seleccionar_id is None:
            seleccionar_id = self._lote_id_seleccionado()
        self.tabla.setRowCount(0)
        if self.pctx is None or self.proyecto is None:
            return
        lotes = self.pctx.batches.listar_lotes(self.proyecto.id)
        self.tabla.setRowCount(len(lotes))
        fila_a_seleccionar = None
        for fila, lote in enumerate(lotes):
            item_nombre = QTableWidgetItem(lote.nombre)
            item_nombre.setData(256, lote.id)  # Qt.UserRole == 256
            self.tabla.setItem(fila, 0, item_nombre)
            item_estado = QTableWidgetItem(lote.estado.value)
            aplicar_color_estado(item_estado, lote.estado.value)
            self.tabla.setItem(fila, 1, item_estado)
            num_documentos = len(self.pctx.batches.listar_documentos_del_lote(lote.id))
            self.tabla.setItem(fila, 2, QTableWidgetItem(str(num_documentos)))
            if seleccionar_id is not None and lote.id == seleccionar_id:
                fila_a_seleccionar = fila
        if fila_a_seleccionar is not None:
            self.tabla.selectRow(fila_a_seleccionar)

    def _lote_id_seleccionado(self) -> str | None:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return None
        item = self.tabla.item(filas[0].row(), 0)
        return item.data(256) if item is not None else None

    def _on_nuevo(self) -> None:
        if self.pctx is None or self.proyecto is None:
            return
        dialogo = TextoSimpleDialog(self, "Nuevo lote", "Nombre:", una_linea=True)
        if not dialogo.exec():
            return  # cancelado -- no hace falta avisar nada, fue una eleccion del operador.
        if not dialogo.valor():
            QMessageBox.warning(self, "Campo requerido", "Debe indicar un nombre para el lote.")
            return
        try:
            lote = self.pctx.batches.crear_lote(self.proyecto.id, dialogo.valor())
        except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(self, "No se pudo crear el lote", mensaje_amigable(exc))
            return
        self._cargar_tabla(seleccionar_id=lote.id)

    def _on_cerrar(self) -> None:
        lote_id = self._lote_id_seleccionado()
        if self.pctx is None or lote_id is None:
            return
        respuesta = QMessageBox.question(
            self,
            "Cerrar lote",
            "Al cerrar el lote se liberaran los documentos aprobados y se bloquearan "
            "los pendientes (Documento Maestro, seccion 10.1, etapa 14). Esta accion "
            "no se puede deshacer. ¿Continuar?",
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return
        try:
            self.pctx.batches.cerrar_lote(lote_id)
        except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(self, "No se pudo cerrar el lote", mensaje_amigable(exc))
            return
        self._cargar_tabla(seleccionar_id=lote_id)

    def _on_exportar_entrega(self) -> None:
        lote_id = self._lote_id_seleccionado()
        if self.pctx is None or lote_id is None:
            QMessageBox.warning(self, "Ningun lote seleccionado", "Selecciona un lote en la tabla primero.")
            return
        lote = self.pctx.batches.obtener_lote(lote_id)
        if lote is None:
            return
        if lote.estado != EstadoLote.CERRADO:
            # La entrega solo tiene sentido para los documentos ya
            # resueltos (LIBERADO/BLOQUEADO) de un lote cerrado -- un lote
            # ABIERTO todavia no tiene esa resolucion (ticket, seccion 3:
            # "reportar el cierre y la exportacion por separado", lo que
            # presupone que el cierre ya ocurrio).
            QMessageBox.warning(
                self,
                "Lote no cerrado",
                f"El lote '{lote.nombre}' todavia esta ABIERTO -- cierralo primero con "
                "'Cerrar lote' antes de exportar su entrega para RAG Studio.",
            )
            return
        try:
            ruta_entrega = self.pctx.documents.preparar_entrega_rag_studio(lote_id=lote.id)
        except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(
                self, "No se pudo preparar la entrega", mensaje_amigable(exc)
            )
            return
        QMessageBox.information(
            self,
            "Entrega lista",
            f"Entrega del lote '{lote.nombre}' para RAG Studio lista en:\n{ruta_entrega}",
        )
