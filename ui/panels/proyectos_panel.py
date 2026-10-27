"""Pantalla "Proyectos" del menu funcional (Fase 11, Documento Maestro
seccion 4.11). Es la unica pagina que no recibe un `pctx` -- su trabajo
es justamente CREAR el proyecto que despues se abre desde la barra
superior de `MainWindow` (sin duplicar ese combo aqui: crear un
proyecto emite `proyecto_creado`, que `MainWindow` escucha para
refrescar su propio combo, mismo principio de responsabilidad unica que
el resto de esta capa).

Auditoria 2026-09-02 (hallazgo real del consultor, RAG_CONTENT_01:
"tratamiento a proyecto que no proceden, como eliminarlos" -- ver
evidencias pruebas): se agregan "Archivar proyecto" (siempre
disponible, no borra nada, solo saca el proyecto del selector de
"Proyecto:" de MainWindow) y "Eliminar proyecto" (borrado real, solo si
el proyecto todavia no tiene documentos registrados -- ver
ProjectInUseError). Ambos emiten `proyecto_modificado` para que
MainWindow refresque su combo, mismo principio que `proyecto_creado`."""
from __future__ import annotations

from PySide6.QtCore import Signal
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

from app.bootstrap import AppContext
from ui.dialogs import CrearProyectoDialog
from ui.theme import aplicar_color_estado
from ui.errores import mensaje_amigable


class ProyectosPanel(QWidget):
    proyecto_creado = Signal(str)  # proyecto_id
    proyecto_modificado = Signal(str)  # proyecto_id (archivado o eliminado)

    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Proyectos</b>"))

        barra = QHBoxLayout()
        boton_crear = QPushButton("Crear proyecto")
        boton_crear.clicked.connect(self._on_crear_proyecto)
        barra.addWidget(boton_crear)
        boton_actualizar = QPushButton("Actualizar lista")
        boton_actualizar.clicked.connect(self._cargar_tabla)
        barra.addWidget(boton_actualizar)
        boton_archivar = QPushButton("Archivar proyecto")
        boton_archivar.clicked.connect(self._on_archivar_proyecto)
        barra.addWidget(boton_archivar)
        boton_eliminar = QPushButton("Eliminar proyecto")
        boton_eliminar.clicked.connect(self._on_eliminar_proyecto)
        barra.addWidget(boton_eliminar)
        barra.addStretch()
        layout.addLayout(barra)

        self.tabla = QTableWidget(0, 5)
        self.tabla.setHorizontalHeaderLabels(["Id", "Nombre", "Perfil", "Confidencialidad", "Estado"])
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.tabla)

        self._cargar_tabla()

    def _cargar_tabla(self) -> None:
        # incluir_archivados=True (el predeterminado): a diferencia del
        # selector "Proyecto:" de MainWindow (que solo debe ofrecer
        # proyectos abribles), esta tabla es el unico lugar donde un
        # proyecto archivado sigue siendo visible -- para poder
        # consultarlo o, si ya no tiene documentos, eliminarlo.
        proyectos = self.ctx.projects.listar_proyectos()
        self.tabla.setRowCount(len(proyectos))
        for fila, proyecto in enumerate(proyectos):
            self.tabla.setItem(fila, 0, QTableWidgetItem(proyecto.id))
            self.tabla.setItem(fila, 1, QTableWidgetItem(proyecto.nombre))
            self.tabla.setItem(fila, 2, QTableWidgetItem(proyecto.perfil_id))
            self.tabla.setItem(fila, 3, QTableWidgetItem(proyecto.confidencialidad.value))
            item_estado = QTableWidgetItem(proyecto.estado.value)
            aplicar_color_estado(item_estado, proyecto.estado.value)
            self.tabla.setItem(fila, 4, item_estado)

    def _proyecto_seleccionado_id(self) -> str | None:
        fila = self.tabla.currentRow()
        if fila < 0:
            return None
        item = self.tabla.item(fila, 0)
        return item.text() if item is not None else None

    def _on_archivar_proyecto(self) -> None:
        proyecto_id = self._proyecto_seleccionado_id()
        if proyecto_id is None:
            QMessageBox.information(self, "Ningun proyecto seleccionado", "Seleccione un proyecto de la tabla.")
            return
        confirmacion = QMessageBox.question(
            self,
            "Archivar proyecto",
            f"¿Archivar el proyecto '{proyecto_id}'? Dejara de aparecer en el selector de proyectos "
            "activos, pero ningun archivo se borra -- puede consultarlo desde esta misma tabla.",
        )
        if confirmacion != QMessageBox.StandardButton.Yes:
            return
        try:
            self.ctx.projects.archivar_proyecto(proyecto_id)
        except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(self, "No se pudo archivar el proyecto", mensaje_amigable(exc))
            return
        self._cargar_tabla()
        self.proyecto_modificado.emit(proyecto_id)

    def _on_eliminar_proyecto(self) -> None:
        proyecto_id = self._proyecto_seleccionado_id()
        if proyecto_id is None:
            QMessageBox.information(self, "Ningun proyecto seleccionado", "Seleccione un proyecto de la tabla.")
            return
        confirmacion = QMessageBox.question(
            self,
            "Eliminar proyecto",
            f"¿Eliminar el proyecto '{proyecto_id}'? Solo es posible si todavia no tiene ningun documento "
            "registrado -- un proyecto con trabajo real debe archivarse, no eliminarse. Esta accion no se "
            "puede deshacer.",
        )
        if confirmacion != QMessageBox.StandardButton.Yes:
            return
        try:
            self.ctx.projects.eliminar_proyecto(proyecto_id)
        except Exception as exc:  # incluye ProjectInUseError -- se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(self, "No se pudo eliminar el proyecto", mensaje_amigable(exc))
            return
        self._cargar_tabla()
        self.proyecto_modificado.emit(proyecto_id)

    def _on_crear_proyecto(self) -> None:
        # Bug real encontrado en la tercera auditoria general
        # 2026-07-31: un perfil YAML corrupto (campo obligatorio
        # faltante, archivo vacio, version mal nombrada) hacia que
        # `listar_perfiles()` lanzara sin traducir -- esta pantalla era
        # una de las tres que no lo capturaba, dejando pasar un
        # traceback crudo en vez de un aviso amigable.
        try:
            perfiles = self.ctx.projects.listar_perfiles()
        except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(self, "No se pudieron cargar los perfiles", mensaje_amigable(exc))
            return
        if not perfiles:
            QMessageBox.warning(
                self,
                "Sin perfiles disponibles",
                "No hay ningun perfil cargado todavia -- cree uno primero desde 'Configuracion'.",
            )
            return
        dialogo = CrearProyectoDialog(self, perfiles)
        if not dialogo.exec():
            return
        # perfil_id capturado una sola vez: dos llamadas separadas a
        # dialogo.perfil_id() no permiten que Mypy angoste la segunda a
        # partir del chequeo "is None" hecho sobre la primera.
        perfil_id = dialogo.perfil_id()
        if not dialogo.nombre() or perfil_id is None:
            QMessageBox.warning(self, "Campos requeridos", "Nombre y perfil son obligatorios.")
            return
        try:
            proyecto = self.ctx.projects.crear_proyecto(
                nombre=dialogo.nombre(),
                perfil_id=perfil_id,
                objetivo=dialogo.objetivo(),
                idioma=dialogo.idioma(),
                confidencialidad=dialogo.confidencialidad(),
            )
        except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(self, "No se pudo crear el proyecto", mensaje_amigable(exc))
            return
        self._cargar_tabla()
        self.proyecto_creado.emit(proyecto.id)
