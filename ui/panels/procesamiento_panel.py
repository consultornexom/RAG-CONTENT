"""Pantalla "Procesamiento" del menu funcional (Fase 11, Documento
Maestro seccion 4.11 y Fase 6). Combina dos cosas deliberadamente en
una sola pantalla: clasificar/extraer un documento puntual (accion
directa, sincrona) y administrar la cola de trabajos en segundo plano
(Fase 6) -- es, en esta version, el "modo avanzado" que la seccion
4.11.1 describe como oculto detras de un interruptor: no se construyo
ese interruptor en esta pasada (ver bitacora de la Fase 11), asi que
todo vive visible en esta unica pantalla en vez de quedar inalcanzable."""
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
from domain.jobs.entities import TipoTrabajo
from domain.projects.entities import Proyecto
from ui.theme import aplicar_color_estado
from ui.errores import mensaje_amigable


class ProcesamientoPanel(QWidget):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self.pctx: ProjectContext | None = None
        self.proyecto: Proyecto | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Procesamiento</b>"))

        layout.addWidget(QLabel("Documentos"))
        self.tabla_documentos = QTableWidget(0, 3)
        self.tabla_documentos.setHorizontalHeaderLabels(["Nombre", "Estado", "Tipo de procesamiento"])
        layout.addWidget(self.tabla_documentos)

        barra_documento = QHBoxLayout()
        self.boton_clasificar = QPushButton("Clasificar seleccionado")
        self.boton_clasificar.clicked.connect(self._on_clasificar)
        barra_documento.addWidget(self.boton_clasificar)
        self.boton_extraer = QPushButton("Extraer ahora (sincrono)")
        self.boton_extraer.clicked.connect(self._on_extraer_sincrono)
        barra_documento.addWidget(self.boton_extraer)
        self.boton_encolar = QPushButton("Encolar extraccion (segundo plano)")
        self.boton_encolar.clicked.connect(self._on_encolar_extraccion)
        barra_documento.addWidget(self.boton_encolar)
        barra_documento.addStretch()
        layout.addLayout(barra_documento)

        layout.addWidget(QLabel("Cola de trabajos (Fase 6)"))
        self.tabla_trabajos = QTableWidget(0, 5)
        self.tabla_trabajos.setHorizontalHeaderLabels(["Tipo", "Documento", "Estado", "Intentos", "Prioridad"])
        layout.addWidget(self.tabla_trabajos)

        barra_trabajos = QHBoxLayout()
        self.boton_procesar_siguiente = QPushButton("Procesar siguiente pendiente")
        self.boton_procesar_siguiente.clicked.connect(self._on_procesar_siguiente)
        barra_trabajos.addWidget(self.boton_procesar_siguiente)
        self.boton_procesar_todos = QPushButton("Procesar todos los pendientes")
        self.boton_procesar_todos.clicked.connect(self._on_procesar_todos)
        barra_trabajos.addWidget(self.boton_procesar_todos)
        self.boton_pausar = QPushButton("Pausar")
        self.boton_pausar.clicked.connect(lambda: self._on_accion_trabajo("pausar_trabajo"))
        barra_trabajos.addWidget(self.boton_pausar)
        self.boton_reanudar = QPushButton("Reanudar")
        self.boton_reanudar.clicked.connect(lambda: self._on_accion_trabajo("reanudar_trabajo"))
        barra_trabajos.addWidget(self.boton_reanudar)
        self.boton_cancelar = QPushButton("Cancelar")
        self.boton_cancelar.clicked.connect(lambda: self._on_accion_trabajo("cancelar_trabajo"))
        barra_trabajos.addWidget(self.boton_cancelar)
        self.boton_reintentar = QPushButton("Reintentar")
        self.boton_reintentar.clicked.connect(lambda: self._on_accion_trabajo("reintentar_trabajo"))
        barra_trabajos.addWidget(self.boton_reintentar)
        barra_trabajos.addStretch()
        layout.addLayout(barra_trabajos)

        self._actualizar_habilitados()

    def establecer_proyecto(self, pctx: ProjectContext | None, proyecto: Proyecto | None) -> None:
        self.pctx = pctx
        self.proyecto = proyecto
        self._actualizar_habilitados()
        self._cargar_documentos()
        self._cargar_trabajos()

    def _actualizar_habilitados(self) -> None:
        habilitado = self.pctx is not None
        for boton in (
            self.boton_clasificar,
            self.boton_extraer,
            self.boton_encolar,
            self.boton_procesar_siguiente,
            self.boton_procesar_todos,
            self.boton_pausar,
            self.boton_reanudar,
            self.boton_cancelar,
            self.boton_reintentar,
        ):
            boton.setEnabled(habilitado)

    def _cargar_documentos(self, seleccionar_id: str | None = None) -> None:
        # Preserva la seleccion a traves del recargue: sin esto, cada
        # accion (clasificar, extraer...) deja la tabla sin fila
        # seleccionada y la siguiente accion sobre "el documento
        # seleccionado" no hace nada -- forzaria a reseleccionar entre
        # cada paso, justo lo que la seccion 4.11.1 (baja friccion) pide
        # evitar.
        if seleccionar_id is None:
            seleccionar_id = self._documento_id_seleccionado()
        self.tabla_documentos.setRowCount(0)
        if self.pctx is None:
            return
        documentos = self.pctx.documents.listar_documentos()
        self.tabla_documentos.setRowCount(len(documentos))
        fila_a_seleccionar = None
        for fila, documento in enumerate(documentos):
            item_nombre = QTableWidgetItem(documento.nombre_original)
            item_nombre.setData(256, documento.id)  # Qt.UserRole == 256
            self.tabla_documentos.setItem(fila, 0, item_nombre)
            item_estado = QTableWidgetItem(documento.estado.value)
            aplicar_color_estado(item_estado, documento.estado.value)
            self.tabla_documentos.setItem(fila, 1, item_estado)
            tipo = documento.tipo_procesamiento.value if documento.tipo_procesamiento else "--"
            self.tabla_documentos.setItem(fila, 2, QTableWidgetItem(tipo))
            if seleccionar_id is not None and documento.id == seleccionar_id:
                fila_a_seleccionar = fila
        if fila_a_seleccionar is not None:
            self.tabla_documentos.selectRow(fila_a_seleccionar)

    def _documento_id_seleccionado(self) -> str | None:
        filas = self.tabla_documentos.selectionModel().selectedRows()
        if not filas:
            return None
        item = self.tabla_documentos.item(filas[0].row(), 0)
        return item.data(256) if item is not None else None

    def _cargar_trabajos(self, seleccionar_id: str | None = None) -> None:
        # Mismo criterio que _cargar_documentos: preserva la seleccion
        # para poder encadenar pausar/reanudar/cancelar/reintentar sobre
        # el mismo trabajo sin tener que reseleccionarlo cada vez.
        if seleccionar_id is None:
            seleccionar_id = self._trabajo_id_seleccionado()
        self.tabla_trabajos.setRowCount(0)
        if self.pctx is None:
            return
        trabajos = self.pctx.jobs.listar_trabajos()
        self.tabla_trabajos.setRowCount(len(trabajos))
        fila_a_seleccionar = None
        for fila, trabajo in enumerate(trabajos):
            item_tipo = QTableWidgetItem(trabajo.tipo.value)
            item_tipo.setData(256, trabajo.id)  # Qt.UserRole == 256
            self.tabla_trabajos.setItem(fila, 0, item_tipo)
            self.tabla_trabajos.setItem(fila, 1, QTableWidgetItem(trabajo.documento_id))
            item_estado_trabajo = QTableWidgetItem(trabajo.estado.value)
            aplicar_color_estado(item_estado_trabajo, trabajo.estado.value)
            self.tabla_trabajos.setItem(fila, 2, item_estado_trabajo)
            self.tabla_trabajos.setItem(fila, 3, QTableWidgetItem(str(trabajo.intentos)))
            self.tabla_trabajos.setItem(fila, 4, QTableWidgetItem(trabajo.prioridad.value))
            if seleccionar_id is not None and trabajo.id == seleccionar_id:
                fila_a_seleccionar = fila
        if fila_a_seleccionar is not None:
            self.tabla_trabajos.selectRow(fila_a_seleccionar)

    def _trabajo_id_seleccionado(self) -> str | None:
        filas = self.tabla_trabajos.selectionModel().selectedRows()
        if not filas:
            return None
        item = self.tabla_trabajos.item(filas[0].row(), 0)
        return item.data(256) if item is not None else None

    def _on_clasificar(self) -> None:
        documento_id = self._documento_id_seleccionado()
        if self.pctx is None or documento_id is None:
            return
        try:
            self.pctx.documents.clasificar_documento(documento_id)
        except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(self, "No se pudo clasificar", mensaje_amigable(exc))
            return
        self._cargar_documentos(seleccionar_id=documento_id)

    def _on_extraer_sincrono(self) -> None:
        documento_id = self._documento_id_seleccionado()
        if self.pctx is None or documento_id is None:
            return
        try:
            self.pctx.documents.extraer_documento(documento_id)
        except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(self, "No se pudo extraer", mensaje_amigable(exc))
            return
        self._cargar_documentos(seleccionar_id=documento_id)

    def _on_encolar_extraccion(self) -> None:
        documento_id = self._documento_id_seleccionado()
        if self.pctx is None or self.proyecto is None or documento_id is None:
            return
        try:
            self.pctx.cola_trabajos.encolar(self.proyecto.id, TipoTrabajo.EXTRACCION, documento_id)
        except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(self, "No se pudo encolar el trabajo", mensaje_amigable(exc))
            return
        self._cargar_trabajos()

    def _on_procesar_siguiente(self) -> None:
        # Agregado 2026-07-31 (auditoria general): estos dos manejadores
        # eran los unicos de todo el panel sin try/except -- ColaDeTrabajos
        # ya deja un fallo del EJECUTOR como Trabajo FALLIDO sin lanzar,
        # pero un fallo de la capa de persistencia (BD, disco) al buscar o
        # actualizar el trabajo si podia subir sin capturar desde este
        # slot de Qt, rompiendo la regla que respeta el resto del panel:
        # ningun error se deja pasar en silencio, siempre se avisa.
        if self.pctx is None:
            return
        try:
            self.pctx.cola_trabajos.procesar_siguiente()
        except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(self, "No se pudo procesar el siguiente trabajo", mensaje_amigable(exc))
        self._cargar_documentos()
        self._cargar_trabajos()

    def _on_procesar_todos(self) -> None:
        if self.pctx is None:
            return
        try:
            self.pctx.cola_trabajos.procesar_todos_los_pendientes()
        except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(self, "No se pudieron procesar los trabajos pendientes", mensaje_amigable(exc))
        self._cargar_documentos()
        self._cargar_trabajos()

    def _on_accion_trabajo(self, nombre_metodo: str) -> None:
        trabajo_id = self._trabajo_id_seleccionado()
        if self.pctx is None or trabajo_id is None:
            return
        try:
            getattr(self.pctx.jobs, nombre_metodo)(trabajo_id)
        except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(self, "No se pudo aplicar la accion", mensaje_amigable(exc))
            return
        self._cargar_trabajos(seleccionar_id=trabajo_id)
