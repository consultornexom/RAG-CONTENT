"""Pantalla "Configuracion" del menu funcional (Fase 11, Documento
Maestro seccion 4.11). Agrupa dos cosas que no tenian ninguna pantalla
propia todavia: perfiles (Modulo 2, `ProfilesService`) y respaldos
cifrados del proyecto abierto (Fase 10, `SecurityService`) -- la unica
pantalla que combina algo de `ctx` (perfiles, independientes de cual
proyecto este abierto) con algo de `pctx` (respaldos, del proyecto
actual).

Bug real reportado 2026-07-30 (usuario de Windows): tras corregir la
ruta raiz hardcodeada, el usuario seguia sin saber en que carpeta
concreta de su equipo estaba guardando la herramienta sus proyectos --
la unica forma de averiguarlo era buscar manualmente en el Explorador de
Windows (lo que llevo a encontrar varias carpetas de proyectos
dispersas, de pruebas anteriores, en rutas distintas). Ninguna pantalla
de la interfaz mostraba nunca `app.configuration.cargar_rutas()`
resuelto. Corregido: esta pantalla ahora muestra la carpeta raiz de
datos resuelta en tiempo real y ofrece un boton para abrirla directo en
el explorador de archivos del sistema operativo, para que el usuario
nunca tenga que adivinar ni buscarla a mano."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.bootstrap import AppContext, ProjectContext
from domain.projects.entities import Proyecto
from ui.dialogs import CrearPerfilDialog
from ui.errores import mensaje_amigable


class ConfiguracionPanel(QWidget):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self.pctx: ProjectContext | None = None
        self.proyecto: Proyecto | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Configuracion</b>"))

        layout.addWidget(QLabel("Carpeta raiz de datos (perfiles, proyectos, logs)"))
        etiqueta_raiz = QLabel(str(self.ctx.rutas.raiz))
        etiqueta_raiz.setWordWrap(True)
        etiqueta_raiz.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(etiqueta_raiz)
        barra_raiz = QHBoxLayout()
        boton_abrir_proyectos = QPushButton("Abrir carpeta de proyectos")
        boton_abrir_proyectos.clicked.connect(self._on_abrir_carpeta_proyectos)
        barra_raiz.addWidget(boton_abrir_proyectos)
        barra_raiz.addStretch()
        layout.addLayout(barra_raiz)

        layout.addWidget(QLabel("Perfiles de proyecto"))
        self.lista_perfiles = QListWidget()
        layout.addWidget(self.lista_perfiles)
        barra_perfiles = QHBoxLayout()
        boton_crear_perfil = QPushButton("Crear perfil")
        boton_crear_perfil.clicked.connect(self._on_crear_perfil)
        barra_perfiles.addWidget(boton_crear_perfil)
        barra_perfiles.addStretch()
        layout.addLayout(barra_perfiles)

        layout.addWidget(QLabel("Respaldos cifrados del proyecto abierto (Fase 10)"))
        barra_respaldos = QHBoxLayout()
        self.boton_crear_respaldo = QPushButton("Crear respaldo")
        self.boton_crear_respaldo.clicked.connect(self._on_crear_respaldo)
        self.boton_crear_respaldo.setEnabled(False)
        barra_respaldos.addWidget(self.boton_crear_respaldo)
        self.boton_restaurar_respaldo = QPushButton("Restaurar respaldo...")
        self.boton_restaurar_respaldo.clicked.connect(self._on_restaurar_respaldo)
        self.boton_restaurar_respaldo.setEnabled(False)
        barra_respaldos.addWidget(self.boton_restaurar_respaldo)
        barra_respaldos.addStretch()
        layout.addLayout(barra_respaldos)
        self.etiqueta_respaldo = QLabel("")
        self.etiqueta_respaldo.setWordWrap(True)
        layout.addWidget(self.etiqueta_respaldo)

        self._cargar_perfiles()

    def _on_abrir_carpeta_proyectos(self) -> None:
        """Abre la carpeta de proyectos resuelta (`cargar_rutas()`) en el
        explorador de archivos del sistema operativo -- para que el
        usuario nunca tenga que buscarla a mano (bug real 2026-07-30, ver
        docstring del modulo). La crea primero si por alguna razon
        todavia no existe (por ejemplo, un proyecto todavia no creado en
        esta instalacion): abrir una carpeta inexistente falla
        silenciosamente en algunos sistemas operativos.

        Auditoria 2026-08-24: el `mkdir()` no tenia try/except, a
        diferencia de todos los demas puntos de escritura en disco de
        este mismo archivo (`_on_crear_respaldo`, `_on_restaurar_respaldo`)
        y del resto de `ui/panels/*` -- si la carpeta raiz de datos
        apunta a una ubicacion sin permiso de escritura, esto lanzaba
        `PermissionError`/`OSError` crudo sin capturar desde un slot de
        Qt, el mismo patron que ya se corrigio en otros lugares (ver
        bitacora "Anadir mensajes amigables para PermissionError")."""
        try:
            self.ctx.rutas.proyectos.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.critical(self, "No se pudo abrir la carpeta de proyectos", mensaje_amigable(exc))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.ctx.rutas.proyectos)))

    def establecer_proyecto(self, pctx: ProjectContext | None, proyecto: Proyecto | None) -> None:
        self.pctx = pctx
        self.proyecto = proyecto
        habilitado = pctx is not None and proyecto is not None
        self.boton_crear_respaldo.setEnabled(habilitado)
        self.boton_restaurar_respaldo.setEnabled(habilitado)

    def _cargar_perfiles(self) -> None:
        # Bug real encontrado en la tercera auditoria general
        # (2026-07-31): un perfil YAML corrupto (campo obligatorio
        # faltante, archivo vacio, version mal nombrada) hacia que
        # `listar_perfiles()` lanzara sin traducir -- esta pantalla era
        # una de las tres que no lo capturaba, dejando pasar un
        # traceback crudo en vez de un aviso amigable. Se llama tanto
        # desde `__init__` como despues de crear un perfil nuevo
        # (`_on_crear_perfil`); en ambos casos, si falla, la lista queda
        # vacia/sin actualizar y se avisa al usuario en vez de romper la
        # pantalla completa.
        self.lista_perfiles.clear()
        try:
            perfiles = self.ctx.profiles.listar_perfiles()
        except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(self, "No se pudieron cargar los perfiles", mensaje_amigable(exc))
            return
        for perfil in perfiles:
            self.lista_perfiles.addItem(f"{perfil.id} (v{perfil.version}) -- {perfil.descripcion}")

    def _on_crear_perfil(self) -> None:
        dialogo = CrearPerfilDialog(self)
        if not dialogo.exec():
            return
        if not dialogo.perfil_id():
            QMessageBox.warning(self, "Campo requerido", "El id del perfil es obligatorio.")
            return
        try:
            self.ctx.profiles.crear_perfil(
                perfil_id=dialogo.perfil_id(), version=dialogo.version(), descripcion=dialogo.descripcion()
            )
        except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(self, "No se pudo crear el perfil", mensaje_amigable(exc))
            return
        self._cargar_perfiles()

    def _on_crear_respaldo(self) -> None:
        if self.pctx is None or self.proyecto is None:
            return
        try:
            respaldo = self.pctx.security.crear_respaldo(self.proyecto.id, Path(self.proyecto.ruta_carpeta))
        except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(self, "No se pudo crear el respaldo", mensaje_amigable(exc))
            return
        self.etiqueta_respaldo.setText(
            f"Respaldo creado: {respaldo.ruta_archivo}\nHash SHA-256: {respaldo.hash_sha256}\n"
            f"Tamano: {respaldo.tamano_bytes} bytes"
        )

    def _on_restaurar_respaldo(self) -> None:
        if self.pctx is None or self.proyecto is None:
            return
        ruta_archivo, _ = QFileDialog.getOpenFileName(self, "Elegir archivo de respaldo (.zip.enc)")
        if not ruta_archivo:
            return
        destino = QFileDialog.getExistingDirectory(self, "Elegir carpeta de destino para la restauracion")
        if not destino:
            return
        try:
            restauracion = self.pctx.security.restaurar_respaldo(self.proyecto.id, Path(ruta_archivo), Path(destino))
        except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(self, "No se pudo restaurar el respaldo", mensaje_amigable(exc))
            return
        if not restauracion.exitosa:
            QMessageBox.warning(self, "Restauracion no exitosa", restauracion.detalle)
            return
        self.etiqueta_respaldo.setText(f"Restauracion exitosa en: {restauracion.ruta_destino}")
