"""Pantalla "Pruebas" (de aceptacion) del menu funcional (Fase 11,
Documento Maestro seccion 4.11; Fase 9). Hasta ahora la unica forma de
correr `AcceptanceService` era `scripts/ejecutar_pruebas_aceptacion.py`
contra el corpus fijo de `corpus_aceptacion/`; esta pantalla permite
correrlo contra CUALQUIER carpeta, sobre el proyecto real que este
abierto, escribiendo el informe dentro de `10_reportes/` del propio
proyecto (no en `corpus_aceptacion/informes/`, que sigue siendo solo
para la corrida fija del script de desarrollo).

Confusion real reportada 2026-07-31 (ya corregida en su causa raiz):
esta pantalla se reutilizaba tal cual como "Etapa 9 de 10: Ejecutar
pruebas" dentro del asistente guiado (`ui.wizard.asistente_widget`),
entre "Generar Markdown" y "Cerrar lote" -- un usuario que seguia el
asistente paso a paso asumia naturalmente que esta etapa evaluaba el
documento que acababa de procesar en las etapas anteriores. No es asi:
`AcceptanceService.ejecutar_pruebas_de_aceptacion()` (Fase 9) SIEMPRE
vuelve a registrar desde cero cualquier archivo que haya dentro de la
carpeta de corpus que se le indique, de forma completamente
independiente de los documentos que ya esten en el inventario del
proyecto -- es una revision de control de calidad de LA HERRAMIENTA
MISMA contra documentos representativos (Documento Maestro, seccion
8.1/8.2), no una validacion del documento en turno.

Correccion de fondo (2026-07-31, propuesta explicita del consultor tras
madurar la herramienta): la etapa "Ejecutar pruebas" se quito por
completo del asistente guiado -- esta pantalla ya NO se reutiliza ahi,
es exclusivamente una herramienta de QA de Modo Avanzado, sin relacion
con el recorrido de ningun proyecto en particular. El texto en pantalla
se actualizo para dejar de hablar de "etapas anteriores" o de "Cerrar
lote" (que aqui ya no aplican) y explicar en su lugar, sin ambiguedad,
que se trata de una prueba de la herramienta en general, no del
proyecto abierto. Si se apunta esta pantalla a una copia del mismo
archivo que ya se proceso antes en algun proyecto (mismo contenido,
mismo hash SHA-256, aunque este en otra carpeta o con otro nombre), el
Modulo 3 (deteccion de duplicados) bloquea correctamente el registro
DENTRO de ese proyecto -- esto es lo esperado, no un error de la
herramienta (esta pantalla no depende de ningun proyecto para correr)."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
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
from application.acceptance.service import AcceptanceService
from domain.projects.entities import Proyecto
from ui.errores import mensaje_amigable


class PruebasPanel(QWidget):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self.pctx: ProjectContext | None = None
        self.proyecto: Proyecto | None = None
        self._ultima_ruta_informe: str | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Pruebas de aceptacion</b> (Documento Maestro, secciones 8.1 y 8.2)"))
        etiqueta_explicacion = QLabel(
            "Esta prueba valida la HERRAMIENTA en general (el motor de extraccion/OCR) contra "
            "documentos representativos -- no es un paso del flujo de ningun proyecto en "
            "particular, ni evalua el proyecto que tengas abierto ahora mismo. Vuelve a registrar "
            "desde cero cualquier archivo que haya en la carpeta de corpus, de forma independiente "
            "del inventario de cualquier proyecto: si apuntas a una copia de un archivo que ya "
            "procesaste antes en algun proyecto (mismo contenido, aunque este en otra carpeta o con "
            "otro nombre), la deteccion de duplicados la bloqueara correctamente dentro de ese "
            "proyecto -- eso es lo esperado, no un error. "
            "El \"corpus\" es la carpeta que contiene los archivos originales a procesar en esta "
            "prueba (documentos reales y representativos, no sinteticos, no necesariamente los de "
            "este proyecto) -- ver corpus_aceptacion/README.md."
        )
        etiqueta_explicacion.setWordWrap(True)
        layout.addWidget(etiqueta_explicacion)

        barra = QHBoxLayout()
        self.boton_elegir_corpus = QPushButton("Elegir carpeta de corpus...")
        self.boton_elegir_corpus.setToolTip(
            "Carpeta que contiene los archivos originales a procesar (por ejemplo, PDFs, Word, "
            "hojas de calculo). La herramienta los recorre de forma recursiva, sin importar la "
            "subcarpeta en la que esten."
        )
        self.boton_elegir_corpus.clicked.connect(self._on_elegir_corpus)
        barra.addWidget(self.boton_elegir_corpus)
        self.etiqueta_corpus = QLabel("Ninguna carpeta seleccionada.")
        barra.addWidget(self.etiqueta_corpus)
        barra.addStretch()
        layout.addLayout(barra)

        self.boton_ejecutar = QPushButton("Ejecutar pruebas de aceptacion")
        self.boton_ejecutar.clicked.connect(self._on_ejecutar)
        self.boton_ejecutar.setEnabled(False)
        layout.addWidget(self.boton_ejecutar)

        self.etiqueta_resultado = QLabel("")
        layout.addWidget(self.etiqueta_resultado)

        self.lista_dominios = QListWidget()
        layout.addWidget(self.lista_dominios)

        self.boton_abrir_informe = QPushButton("Abrir informe generado")
        self.boton_abrir_informe.clicked.connect(self._on_abrir_informe)
        self.boton_abrir_informe.setEnabled(False)
        layout.addWidget(self.boton_abrir_informe)

        self._ruta_corpus: Path | None = None

    def establecer_proyecto(self, pctx: ProjectContext | None, proyecto: Proyecto | None) -> None:
        self.pctx = pctx
        self.proyecto = proyecto
        self._actualizar_boton_ejecutar()

    def _actualizar_boton_ejecutar(self) -> None:
        self.boton_ejecutar.setEnabled(self.pctx is not None and self._ruta_corpus is not None)

    def _on_elegir_corpus(self) -> None:
        ruta = QFileDialog.getExistingDirectory(
            self, "Elegir carpeta con los archivos originales a procesar (corpus)"
        )
        if not ruta:
            return
        self._ruta_corpus = Path(ruta)
        self.etiqueta_corpus.setText(ruta)
        self._actualizar_boton_ejecutar()

    def _on_ejecutar(self) -> None:
        if self.pctx is None or self.proyecto is None or self._ruta_corpus is None:
            return
        acceptance = AcceptanceService(
            self.pctx.documents, self.pctx.validity, self.pctx.incidents, self.pctx.batches,
            self.pctx.reports, self.proyecto.id,
        )
        try:
            informe = acceptance.ejecutar_pruebas_de_aceptacion(self._ruta_corpus)
        except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(self, "No se pudieron ejecutar las pruebas", mensaje_amigable(exc))
            return

        # Hallazgo real de la cuarta auditoria general (2026-08-01), dos
        # correcciones en el mismo lugar: (1) el escritor del informe ya
        # no se construye aqui -- se ensambla una sola vez en
        # app.bootstrap.abrir_proyecto() (mismo criterio que report_writer)
        # y se consume ya armado desde `self.pctx`, en vez de que este
        # panel importe infrastructure directamente (unica excepcion que
        # tenia toda la capa ui a ese patron); (2) la escritura en disco
        # ahora esta protegida por try/except -- antes era la unica
        # escritura de archivo de toda la capa ui sin el patron
        # try/except + mensaje_amigable ya aplicado en el resto de
        # paneles (por ejemplo, reportes_panel.py, markdown_panel.py),
        # asi que un PermissionError real (Documento Maestro, seccion
        # 4.11.1) dejaba pasar un traceback crudo sin ningun aviso, y el
        # boton "Abrir informe generado" ni siquiera se habilitaba.
        try:
            ruta_informe = self.pctx.informe_aceptacion_writer.escribir(informe)
        except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(self, "No se pudo guardar el informe", mensaje_amigable(exc))
            return
        self._ultima_ruta_informe = ruta_informe
        self.boton_abrir_informe.setEnabled(True)

        resultado = "APROBADO" if informe.aprobado() else "CON HALLAZGOS"
        completo = "si" if informe.esta_completo() else "no"
        self.etiqueta_resultado.setText(
            f"Resultado: {resultado} -- corpus completo (7 dominios): {completo} -- informe: {ruta_informe}"
        )
        self.lista_dominios.clear()
        for criterio in informe.criterios_dominio:
            marca = "PENDIENTE" if criterio.cumplido is None else ("CUMPLE" if criterio.cumplido else "FALLA")
            # Bug real reportado 2026-07-31: un FALLA o PENDIENTE no
            # decia nada de POR QUE -- el usuario tenia que salir de la
            # aplicacion y abrir el informe Markdown a mano para
            # enterarse. `criterio.detalle` ya traia esa explicacion
            # desde la Fase 9 (incluye los "Hallazgos" especificos por
            # archivo cuando aplica); ahora se muestra aqui mismo, tanto
            # en la linea (recortada si es muy larga) como completa en
            # el tooltip al pasar el mouse.
            detalle = criterio.detalle
            resumen = detalle if len(detalle) <= 160 else detalle[:157] + "..."
            item = QListWidgetItem(f"{criterio.dominio}: {marca} -- {resumen}" if resumen else f"{criterio.dominio}: {marca}")
            if detalle:
                item.setToolTip(detalle)
            self.lista_dominios.addItem(item)

    def _on_abrir_informe(self) -> None:
        if self._ultima_ruta_informe is None:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(self._ultima_ruta_informe))
