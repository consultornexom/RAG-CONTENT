"""Pantalla "Incidencias" del menu funcional (Fase 11, Documento Maestro
seccion 4.11 y Modulo 10). Vista de TODO el proyecto -- registrar una
incidencia puntual sobre el documento que se esta revisando sigue
viviendo en "Revision" (Modulo 8, sin cambios); esta pantalla cubre el
resto del ciclo de vida (asignar, responder, decidir, cerrar) que el
prototipo original nunca expuso."""
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
from domain.projects.entities import Proyecto
from ui.dialogs import DecidirIncidenciaDialog, TextoSimpleDialog
from ui.theme import aplicar_color_estado
from ui.errores import mensaje_amigable


class IncidenciasPanel(QWidget):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self.pctx: ProjectContext | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Incidencias</b>"))

        self.tabla = QTableWidget(0, 6)
        self.tabla.setHorizontalHeaderLabels(["Documento", "Etapa", "Tipo", "Severidad", "Estado", "Responsable"])
        layout.addWidget(self.tabla)

        barra = QHBoxLayout()
        self.boton_asignar = QPushButton("Asignar")
        self.boton_asignar.clicked.connect(self._on_asignar)
        barra.addWidget(self.boton_asignar)
        self.boton_responder = QPushButton("Responder")
        self.boton_responder.clicked.connect(self._on_responder)
        barra.addWidget(self.boton_responder)
        self.boton_decidir = QPushButton("Decidir")
        self.boton_decidir.clicked.connect(self._on_decidir)
        barra.addWidget(self.boton_decidir)
        self.boton_cerrar = QPushButton("Cerrar")
        self.boton_cerrar.clicked.connect(self._on_cerrar)
        barra.addWidget(self.boton_cerrar)
        barra.addStretch()
        layout.addLayout(barra)

    def establecer_proyecto(self, pctx: ProjectContext | None, proyecto: Proyecto | None) -> None:
        self.pctx = pctx
        self._cargar_tabla()

    def _cargar_tabla(self, seleccionar_id: str | None = None) -> None:
        # Preserva la seleccion a traves del recargue: sin esto,
        # asignar/responder/decidir/cerrar sobre la MISMA incidencia
        # exigiria reseleccionarla entre cada paso (viola la seccion
        # 4.11.1, baja friccion) -- y de hecho, sin esto, cada paso
        # despues del primero no hacia nada porque no habia fila
        # seleccionada.
        if seleccionar_id is None:
            seleccionar_id = self._incidencia_id_seleccionada()
        self.tabla.setRowCount(0)
        if self.pctx is None:
            return
        incidencias = self.pctx.incidents.listar_incidencias()
        self.tabla.setRowCount(len(incidencias))
        fila_a_seleccionar = None
        for fila, incidencia in enumerate(incidencias):
            item_documento = QTableWidgetItem(incidencia.documento_id)
            item_documento.setData(256, incidencia.id)  # Qt.UserRole == 256
            self.tabla.setItem(fila, 0, item_documento)
            self.tabla.setItem(fila, 1, QTableWidgetItem(incidencia.etapa.value))
            self.tabla.setItem(fila, 2, QTableWidgetItem(incidencia.tipo))
            self.tabla.setItem(fila, 3, QTableWidgetItem(incidencia.severidad.value))
            item_estado = QTableWidgetItem(incidencia.estado.value)
            aplicar_color_estado(item_estado, incidencia.estado.value)
            self.tabla.setItem(fila, 4, item_estado)
            self.tabla.setItem(fila, 5, QTableWidgetItem(incidencia.responsable or ""))
            if seleccionar_id is not None and incidencia.id == seleccionar_id:
                fila_a_seleccionar = fila
        if fila_a_seleccionar is not None:
            self.tabla.selectRow(fila_a_seleccionar)

    def _incidencia_id_seleccionada(self) -> str | None:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return None
        item = self.tabla.item(filas[0].row(), 0)
        return item.data(256) if item is not None else None

    def _on_asignar(self) -> None:
        incidencia_id = self._incidencia_id_seleccionada()
        if self.pctx is None or incidencia_id is None:
            return
        dialogo = TextoSimpleDialog(self, "Asignar incidencia", "Responsable:", una_linea=True)
        if not dialogo.exec():
            return  # cancelado -- no hace falta avisar nada, fue una eleccion del operador.
        if not dialogo.valor():
            # Bug real encontrado en la segunda auditoria 2026-07-31: este
            # panel era el unico de toda la interfaz que, si el operador
            # confirmaba el dialogo con el campo obligatorio vacio, no
            # avisaba nada -- simplemente no pasaba nada, sin explicar por
            # que. El resto de la interfaz (revisor, incidencia nueva,
            # nombre/perfil de proyecto, id de perfil, aprobador...)
            # siempre muestra "Campo requerido" en ese caso.
            QMessageBox.warning(self, "Campo requerido", "Debe indicar un responsable.")
            return
        try:
            self.pctx.incidents.asignar_incidencia(incidencia_id, dialogo.valor())
        except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(self, "No se pudo asignar", mensaje_amigable(exc))
            return
        self._cargar_tabla(seleccionar_id=incidencia_id)

    def _on_responder(self) -> None:
        incidencia_id = self._incidencia_id_seleccionada()
        if self.pctx is None or incidencia_id is None:
            return
        dialogo = TextoSimpleDialog(self, "Responder incidencia", "Respuesta:")
        if not dialogo.exec():
            return
        if not dialogo.valor():
            QMessageBox.warning(self, "Campo requerido", "Debe escribir una respuesta.")
            return
        try:
            self.pctx.incidents.responder_incidencia(incidencia_id, dialogo.valor())
        except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(self, "No se pudo responder", mensaje_amigable(exc))
            return
        self._cargar_tabla(seleccionar_id=incidencia_id)

    def _on_decidir(self) -> None:
        incidencia_id = self._incidencia_id_seleccionada()
        if self.pctx is None or incidencia_id is None:
            return
        dialogo = DecidirIncidenciaDialog(self)
        if not dialogo.exec():
            return
        if not dialogo.decision():
            QMessageBox.warning(self, "Campo requerido", "Debe escribir la decision.")
            return
        try:
            self.pctx.incidents.decidir_incidencia(incidencia_id, dialogo.decision(), dialogo.resuelta())
        except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(self, "No se pudo decidir", mensaje_amigable(exc))
            return
        self._cargar_tabla(seleccionar_id=incidencia_id)

    def _on_cerrar(self) -> None:
        incidencia_id = self._incidencia_id_seleccionada()
        if self.pctx is None or incidencia_id is None:
            return
        dialogo = TextoSimpleDialog(self, "Cerrar incidencia", "Motivo de cierre:")
        if not dialogo.exec():
            return
        if not dialogo.valor():
            QMessageBox.warning(self, "Campo requerido", "Debe indicar el motivo de cierre.")
            return
        try:
            self.pctx.incidents.cerrar_incidencia(incidencia_id, dialogo.valor())
        except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(self, "No se pudo cerrar", mensaje_amigable(exc))
            return
        self._cargar_tabla(seleccionar_id=incidencia_id)
