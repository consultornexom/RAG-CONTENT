"""Ventana principal del prototipo de Modulo 8 (revision contra
originales) + panel minimo de Modulo 10 (incidencias). Solo importa
`app.bootstrap` (para `AppContext`/`abrir_proyecto`, el unico punto de
ensamblado permitido, ADR-001 seccion 4) y `application`/`domain` para
tipos -- nunca construye un adaptador de `infrastructure` por su
cuenta.

Alcance del Modulo 8, actualizado 2026-07-28 (cierra los tres
pendientes que dejaba el primer prototipo, ver bitacora anterior en el
Documento Maestro):
- "Correccion" (editar y persistir el Markdown extraido) ya es real: el
  panel "Extraido / revisado" se vuelve editable exactamente cuando el
  documento esta EXTRAIDO (unico estado en el que
  `Documento.corregir()` lo permite -- ver domain.documents.entities);
  en cualquier otro estado queda de solo lectura, para no sugerir una
  edicion que el backend rechazaria. El boton "Guardar correccion"
  llama a `DocumentsService.corregir_extraccion()`.
- "Verificacion de fechas/cifras": se detectan con
  `domain.documents.verificacion_fechas_cifras.detectar_fechas_y_cifras()`
  sobre el Markdown vigente y se listan en un panel aparte; un clic en
  un hallazgo salta el cursor del panel de Markdown a su posicion,
  para que el revisor lo coteje contra el original. Es deteccion, no
  validacion -- la decision de si esta bien sigue siendo del revisor.
- Navegacion sincronizada real: si el documento tiene
  `Documento.mapa_paginas` (solo lo llenan PdfExtractor/PdfOcrExtractor,
  ver su docstring), cambiar de pagina del PDF original mueve el
  cursor del panel de Markdown al desplazamiento donde empieza esa
  pagina. Sin mapa (documentos que no son PDF paginado), el
  comportamiento cae de vuelta a "ambos paneles visibles, sin salto"
  -- nunca falla, solo no sincroniza.
- La entidad `Revision` del modelo de datos (ADR-001 seccion 5:
  documento_id, revisor, fecha, alcance revisado, incidencias
  detectadas) ya se persiste en su propia tabla ("revisiones",
  historial completo) -- ver application.documents.commands.
  revisar_documento y domain.documents.ports.RevisionRepository. Al
  aprobar una revision, esta ventana consulta las incidencias
  actualmente abiertas del documento y las pasa como
  `incidencias_detectadas` (fotografia del momento, no una relacion
  viva -- ver el docstring de Revision).

Fase 11 (Interfaz completa, Documento Maestro seccion 4.11), 2026-07-29:
el menu funcional se agrega ENVOLVIENDO lo anterior, sin tocarlo -- todo
lo que antes vivia directo en el widget central (tabla_documentos,
texto_extraido, lista_incidencias, etc.) ahora vive en su propia
"pagina" del `QStackedWidget` (`self.paginas`), navegable desde
`self.lista_navegacion`, pero sigue siendo un atributo de ESTA clase, no
de un widget aparte -- ningun test de
tests/smoke/test_gui_revision_incidencias_extremo_a_extremo.py (todos
escritos antes de esta fase) tuvo que cambiar. Las otras once areas del
menu (Proyectos, Inventario, Procesamiento, Normalizacion, Incidencias
de todo el proyecto, Vigencias de todo el proyecto, Markdown, Pruebas de
aceptacion, Reportes, Auditoria, Configuracion) son paneles nuevos en
`ui.panels.*`, cada uno con su propio `establecer_proyecto(pctx,
proyecto)` que esta ventana llama al abrir un proyecto y al cambiar de
pagina (para no mostrar datos obsoletos si algo cambio en otra pagina
mientras tanto).

Alcance deliberadamente acotado de la primera pasada de esta fase (ver
bitacora): el "menu funcional" se conecto por completo; el "asistente
por etapas" y la "pantalla principal" tipo dashboard quedaron para una
pasada siguiente -- confirmado con el usuario antes de empezar, no una
omision silenciosa.

Fase 11.2 (Asistente guiado por etapas), 2026-07-29: agrega
`ui.wizard.AsistenteWidget` como vista predeterminada al abrir la
ventana (Documento Maestro seccion 4.11.1: "el asistente por etapas es
la vista predeterminada al abrir un proyecto; el modo avanzado -- colas,
logs, configuracion fina -- queda oculto detras de un interruptor
explicito"). El menu completo de la Fase 11 (`self.lista_navegacion` +
`self.paginas`, sin cambios) pasa a ser ese "modo avanzado": vive dentro
de `self.modo_stack` junto al asistente, y solo se muestra cuando
`self.casilla_modo_avanzado` esta marcada. La barra superior (selector
de proyecto) queda FUERA del interruptor -- es compartida por ambos
modos, sin duplicarse.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import (
    QBrush,
    QCloseEvent,
    QColor,
    QDesktopServices,
    QKeySequence,
    QPixmap,
    QShortcut,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.bootstrap import AppContext, ProjectContext, abrir_proyecto
from domain.documents.entities import Criticidad, Documento, EstadoDocumento, FormatoDocumento
from domain.documents.verificacion_fechas_cifras import detectar_fechas_y_cifras
from domain.documents.verificacion_totales_tabla import verificar_totales_de_tablas
from domain.projects.entities import Proyecto
from domain.validity.entities import vigencia_desconocida
from ui.dashboard.pantalla_principal_widget import PantallaPrincipalWidget
from ui.dialogs import RegistrarIncidenciaDialog, RegistrarVigenciaDialog, RevisarDocumentoDialog
from ui.editor_texto import BuscarReemplazarDialog, EditorConNumerosDeLinea
from ui.panels.auditoria_panel import AuditoriaPanel
from ui.panels.configuracion_panel import ConfiguracionPanel
from ui.panels.incidencias_panel import IncidenciasPanel
from ui.panels.inventario_panel import InventarioPanel
from ui.panels.lotes_panel import LotesPanel
from ui.panels.markdown_panel import MarkdownPanel
from ui.panels.normalizacion_panel import NormalizacionPanel
from ui.panels.procesamiento_panel import ProcesamientoPanel
from ui.panels.pruebas_panel import PruebasPanel
from ui.panels.proyectos_panel import ProyectosPanel
from ui.panels.reportes_panel import ReportesPanel
from ui.panels.vigencias_panel import VigenciasPanel
from ui.pdf_preview import contar_paginas, render_pagina
from ui.theme import AMBAR_ATENCION, AMBAR_ATENCION_FONDO, aplicar_color_estado
from ui.wizard.asistente_widget import AsistenteWidget
from ui.errores import mensaje_amigable

_FORMATOS_TEXTO_PLANO = {FormatoDocumento.TXT, FormatoDocumento.MARKDOWN, FormatoDocumento.JSON, FormatoDocumento.CSV}
_FORMATOS_IMAGEN = {FormatoDocumento.PNG, FormatoDocumento.JPG}


@runtime_checkable
class _PanelConProyecto(Protocol):
    """Estructural, no un tipo base real: todos los paneles de
    `ui.panels.*` y `ui.dashboard.pantalla_principal_widget` implementan
    `establecer_proyecto(pctx, proyecto)` con esta misma firma, pero no
    comparten ninguna clase base propia mas alla de `QWidget` (que no
    declara el metodo). Sirve para que Mypy pueda verificar
    `self._paginas_con_proyecto` sin recurrir a `getattr`/`type: ignore`
    en cada sitio donde se llama, y (via `@runtime_checkable`) para que
    `_on_cambiar_pagina` pueda angostar `QWidget | None` con un
    `isinstance` real en vez de una comprobacion de pertenencia a lista
    que Mypy no relaciona con el tipo de `pagina_actual`."""

    def establecer_proyecto(self, pctx: ProjectContext | None, proyecto: Proyecto | None) -> None: ...


class MainWindow(QMainWindow):
    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self.pctx: ProjectContext | None = None
        self.proyecto_actual: Proyecto | None = None
        self.documento_actual: Documento | None = None
        self._pagina_pdf_actual = 0
        self._num_paginas_pdf = 0

        self.setWindowTitle("RAG Content Studio Desktop")
        self.resize(1200, 800)

        self._construir_ui()
        self._cargar_proyectos()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Fuga de recursos real encontrada en la segunda auditoria
        2026-07-31: ni esta ventana ni `ui.app.main()` cerraban nunca
        las sesiones de SQLAlchemy al salir de la aplicacion -- se
        liberaban solo por el fin del proceso, no de forma explicita.
        Se cierran aqui ambas sesiones (la del proyecto abierto, si
        hay uno, y la global de `AppContext`) antes de aceptar el
        cierre -- mismo criterio que cerrar el proyecto al cambiar de
        uno a otro (ver `_on_abrir_proyecto`)."""
        if self.pctx is not None:
            self.pctx.session.close()
        self.ctx.session.close()
        super().closeEvent(event)

    # -- construccion de la ventana ---------------------------------

    def _construir_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout_raiz = QVBoxLayout(central)

        barra_proyecto = QHBoxLayout()
        barra_proyecto.addWidget(QLabel("Proyecto:"))
        self.combo_proyectos = QComboBox()
        self.combo_proyectos.setMinimumWidth(300)
        barra_proyecto.addWidget(self.combo_proyectos)
        boton_abrir = QPushButton("Abrir proyecto")
        boton_abrir.clicked.connect(self._on_abrir_proyecto)
        barra_proyecto.addWidget(boton_abrir)
        barra_proyecto.addStretch()
        # Selector de modo explicito (Documento Maestro seccion 4.11 y
        # 4.11.1) -- fuera de `self.modo_stack` a proposito: la barra de
        # proyecto es compartida por las tres vistas, no se duplica.
        # "Inicio" (pantalla principal) es la vista de entrada; abrir o
        # crear un proyecto pasa automaticamente a "Asistente" (seccion
        # 4.11.1: "vista predeterminada al abrir un proyecto"), salvo
        # que el operador ya este en "Modo avanzado" a proposito.
        self.radio_inicio = QRadioButton("Inicio")
        self.radio_asistente = QRadioButton("Asistente")
        self.radio_modo_avanzado = QRadioButton("Modo avanzado (menu completo)")
        self.radio_inicio.setChecked(True)
        self.grupo_modos = QButtonGroup(self)
        for boton in (self.radio_inicio, self.radio_asistente, self.radio_modo_avanzado):
            self.grupo_modos.addButton(boton)
            barra_proyecto.addWidget(boton)
        self.grupo_modos.idClicked.connect(self._on_cambiar_modo)
        layout_raiz.addLayout(barra_proyecto)

        self.modo_stack = QStackedWidget()
        layout_raiz.addWidget(self.modo_stack, stretch=1)

        self.pantalla_principal = PantallaPrincipalWidget(self.ctx)
        self.pantalla_principal.abrir_proyecto_id.connect(self._on_abrir_proyecto_id)
        self.modo_stack.addWidget(self.pantalla_principal)  # indice 0: vista de entrada.

        self.asistente = AsistenteWidget(self.ctx)
        self.asistente.proyecto_creado.connect(self._on_proyecto_creado_desde_panel)
        self.asistente.ir_a_modo_avanzado.connect(self._on_ir_a_modo_avanzado)
        self.modo_stack.addWidget(self.asistente)  # indice 1: vista predeterminada al abrir un proyecto.

        contenedor_menu = QWidget()
        fila_principal = QHBoxLayout(contenedor_menu)
        self.lista_navegacion = QListWidget()
        self.lista_navegacion.setMaximumWidth(200)
        fila_principal.addWidget(self.lista_navegacion)

        self.paginas = QStackedWidget()
        fila_principal.addWidget(self.paginas, stretch=1)
        self.modo_stack.addWidget(contenedor_menu)  # indice 2: modo avanzado.

        self._construir_paginas()

    def _on_cambiar_modo(self, _id: int) -> None:
        if self.radio_inicio.isChecked():
            indice = 0
        elif self.radio_asistente.isChecked():
            indice = 1
        else:
            indice = 2
        self.modo_stack.setCurrentIndex(indice)
        if indice == 0:
            self.pantalla_principal.establecer_proyecto(self.pctx, self.proyecto_actual)
        elif indice == 1:
            # Auditoria 2026-08-24: antes solo se refrescaba "Inicio" al
            # cambiar de modo -- si el operador ya estaba parado en el
            # asistente o en la misma pagina del modo avanzado antes de
            # cambiar, y volvia a ese mismo lugar despues, ni
            # `AsistenteWidget._mostrar_etapa` ni
            # `_on_cambiar_pagina` se disparaban (ambos dependen de que
            # el indice/renglon CAMBIE, no de que la pestana se vuelva a
            # mostrar), asi que quedaba viendo datos obsoletos hasta
            # navegar a otra etapa/pagina y volver. `establecer_proyecto`
            # aqui es seguro de llamar de nuevo: restaura la MISMA etapa
            # autoguardada (se guarda en cada `_mostrar_etapa`), no
            # reinicia el asistente.
            self.asistente.establecer_proyecto(self.pctx, self.proyecto_actual)
        else:
            # Mismo motivo que arriba, para el modo avanzado: fuerza el
            # refresco de la pagina actualmente seleccionada aunque el
            # renglon de `lista_navegacion` no haya cambiado.
            self._on_cambiar_pagina(self.lista_navegacion.currentRow())

    def _on_abrir_proyecto_id(self, proyecto_id: str) -> None:
        """Conectado a `PantallaPrincipalWidget.abrir_proyecto_id`
        (Fase 11.3): doble clic en un proyecto reciente lo abre igual
        que si se hubiera elegido en el combo de la barra superior."""
        indice = self.combo_proyectos.findData(proyecto_id)
        if indice >= 0:
            self.combo_proyectos.setCurrentIndex(indice)
            self._on_abrir_proyecto()

    def _on_ir_a_modo_avanzado(self, etiqueta: str) -> None:
        """Conectado a `AsistenteWidget.ir_a_modo_avanzado` (Fase
        11.2): alguna etapa del asistente necesita una pantalla del
        menu completo (Revision, Reportes) que no tiene sentido
        duplicar dentro del propio asistente -- activa el interruptor y
        navega directo a esa pagina."""
        self.radio_modo_avanzado.setChecked(True)
        self.modo_stack.setCurrentIndex(2)
        for i in range(self.lista_navegacion.count()):
            if self.lista_navegacion.item(i).text() == etiqueta:
                self.lista_navegacion.setCurrentRow(i)
                break

    def _construir_paginas(self) -> None:
        """Arma las trece areas del menu funcional (Fase 11, Documento
        Maestro seccion 4.11, mas "Lotes" -- hallazgo real de la cuarta
        auditoria general, 2026-08-01: ver docstring de
        `ui.panels.lotes_panel`) en el mismo orden en que aparecen ahi.
        "Revision" es la pagina original del prototipo (sin cambios de
        contenido, ver docstring del modulo); las otras doce son
        paneles nuevos de `ui.panels.*`. `self._paginas_con_proyecto`
        guarda las que implementan `establecer_proyecto()` y por eso se
        refrescan solas via `_on_cambiar_pagina` (todas salvo
        "Proyectos", que no depende de ningun proyecto abierto). ver
        `_on_cambiar_pagina()` para el caso de "Revision", que no
        implementa ese protocolo pero desde 2026-07-30 tambien se
        refresca al entrar a la pagina -- bug real encontrado esa fecha
        (ver docstring de `_cargar_documentos`)."""
        self.panel_proyectos = ProyectosPanel(self.ctx)
        self.panel_proyectos.proyecto_creado.connect(self._on_proyecto_creado_desde_panel)
        self.panel_proyectos.proyecto_modificado.connect(self._on_proyecto_modificado_desde_panel)
        self.panel_inventario = InventarioPanel(self.ctx)
        self.panel_procesamiento = ProcesamientoPanel(self.ctx)
        self.panel_normalizacion = NormalizacionPanel(self.ctx)
        self.panel_incidencias = IncidenciasPanel(self.ctx)
        self.panel_vigencias = VigenciasPanel(self.ctx)
        self.panel_markdown = MarkdownPanel(self.ctx)
        self.panel_pruebas = PruebasPanel(self.ctx)
        self.panel_reportes = ReportesPanel(self.ctx)
        self.panel_lotes = LotesPanel(self.ctx)
        self.panel_auditoria = AuditoriaPanel(self.ctx)
        self.panel_configuracion = ConfiguracionPanel(self.ctx)

        self._paginas_con_proyecto: list[_PanelConProyecto] = [
            self.panel_inventario,
            self.panel_procesamiento,
            self.panel_normalizacion,
            self.panel_incidencias,
            self.panel_vigencias,
            self.panel_markdown,
            self.panel_pruebas,
            self.panel_reportes,
            self.panel_lotes,
            self.panel_auditoria,
            self.panel_configuracion,
        ]

        self.pagina_revision = self._construir_pagina_revision()

        orden: list[tuple[str, QWidget]] = [
            ("Proyectos", self.panel_proyectos),
            ("Inventario", self.panel_inventario),
            ("Procesamiento", self.panel_procesamiento),
            ("Revision", self.pagina_revision),
            ("Normalizacion", self.panel_normalizacion),
            ("Incidencias", self.panel_incidencias),
            ("Vigencias", self.panel_vigencias),
            ("Markdown", self.panel_markdown),
            ("Pruebas de aceptacion", self.panel_pruebas),
            ("Reportes", self.panel_reportes),
            ("Lotes", self.panel_lotes),
            ("Auditoria", self.panel_auditoria),
            ("Configuracion", self.panel_configuracion),
        ]
        for etiqueta, pagina in orden:
            self.lista_navegacion.addItem(etiqueta)
            self.paginas.addWidget(pagina)

        self.lista_navegacion.currentRowChanged.connect(self._on_cambiar_pagina)
        self.lista_navegacion.setCurrentRow(0)  # "Proyectos": vista de entrada natural, sin proyecto abierto todavia.

    def _construir_pagina_revision(self) -> QWidget:
        """Todo lo que antes construia `_construir_ui()` directo sobre
        el widget central -- movido aqui sin cambiar ni un atributo, ver
        docstring del modulo.

        Distribucion del espacio ajustada 2026-07-31 (comentario real del
        consultor con captura de pantalla): la tabla de documentos
        truncaba el encabezado "Tipo de procesamiento" a "de procesam"
        porque `QTableWidget` no usaba el ancho disponible del panel
        (modo de ajuste "Interactive" con anchos fijos pequenos por
        defecto, sin relacion con el ancho real del panel) -- ahora usa
        `Stretch` para repartir TODO el ancho disponible entre las tres
        columnas. El panel lateral (incidencias/fechas/vigencia) tenia
        varias listas de altura variable compitiendo por el mismo
        espacio vertical sin ninguna forma de desplazarse si el
        contenido no cabia en la ventana -- ahora vive dentro de un
        `QScrollArea` para que nada quede recortado sin importar el
        tamano de la ventana. Las proporciones iniciales del splitter
        tambien se ajustaron para darle mas espacio al area de trabajo
        real (el visor Original/Normalizado) en vez de a la lista de
        documentos, que normalmente solo necesita mostrar tres columnas
        cortas.

        Paneles laterales plegables (2026-07-31, comentario real del
        consultor con captura de pantalla): el panel izquierdo
        ("Documentos del proyecto") y el derecho ("Estado" -- estado,
        incidencias, fechas/cifras, vigencia y fuente) se pueden ocultar
        con un boton, para que el visor central (Original/Normalizado,
        el area de trabajo real de esta pantalla) aproveche ese espacio
        cuando el operador no los necesita en ese momento -- por
        ejemplo, ya eligio el documento y solo quiere comparar texto.
        Se implementa ocultando/mostrando el widget dentro del
        `QSplitter` (Qt ya redistribuye el espacio de un hijo oculto
        entre los demas automaticamente, sin logica adicional); el
        estado por defecto sigue siendo "ambos visibles", igual que
        antes de este cambio."""
        pagina = QWidget()
        layout_pagina = QVBoxLayout(pagina)

        barra_alternar_paneles = QHBoxLayout()
        self.boton_alternar_panel_documentos = QPushButton("Ocultar documentos")
        self.boton_alternar_panel_documentos.setCheckable(True)
        self.boton_alternar_panel_documentos.setChecked(True)
        self.boton_alternar_panel_documentos.setToolTip(
            "Ocultar o mostrar el panel de documentos del proyecto, para darle "
            "mas espacio al visor Original/Normalizado."
        )
        self.boton_alternar_panel_documentos.toggled.connect(self._on_alternar_panel_documentos_revision)
        barra_alternar_paneles.addWidget(self.boton_alternar_panel_documentos)
        barra_alternar_paneles.addStretch()
        # Boton nuevo (2026-09-04, pedido explicito de un usuario real:
        # queria mas espacio para editar "Normalizado" y sugirio una
        # ventana aparte; se opto por este boton en su lugar, simetrico
        # a los otros dos -- ver docstring de ui/editor_texto.py para el
        # porque). Oculta "Original" dentro de `splitter_visor`, asi que
        # el espacio liberado se lo lleva "Normalizado" (el otro hijo de
        # ese mismo splitter), sin afectar a "Documentos" ni a "Estado".
        self.boton_alternar_panel_original = QPushButton("Ocultar original")
        self.boton_alternar_panel_original.setCheckable(True)
        self.boton_alternar_panel_original.setChecked(True)
        self.boton_alternar_panel_original.setToolTip(
            "Ocultar o mostrar el panel 'Original', para darle mas espacio al editor "
            "'Normalizado' cuando hace falta corregir un tramo largo de texto."
        )
        self.boton_alternar_panel_original.toggled.connect(self._on_alternar_panel_original_revision)
        barra_alternar_paneles.addWidget(self.boton_alternar_panel_original)
        self.boton_alternar_panel_estado = QPushButton("Ocultar estado")
        self.boton_alternar_panel_estado.setCheckable(True)
        self.boton_alternar_panel_estado.setChecked(True)
        self.boton_alternar_panel_estado.setToolTip(
            "Ocultar o mostrar el panel de estado, incidencias, fechas/cifras "
            "y vigencia, para darle mas espacio al visor Original/Normalizado."
        )
        self.boton_alternar_panel_estado.toggled.connect(self._on_alternar_panel_estado_revision)
        barra_alternar_paneles.addWidget(self.boton_alternar_panel_estado)
        layout_pagina.addLayout(barra_alternar_paneles)

        splitter_principal = QSplitter()
        layout_pagina.addWidget(splitter_principal, stretch=1)

        # -- panel izquierdo: lista de documentos --
        panel_documentos = QWidget()
        layout_documentos = QVBoxLayout(panel_documentos)
        layout_documentos.addWidget(QLabel("Documentos del proyecto"))
        self.tabla_documentos = QTableWidget(0, 3)
        self.tabla_documentos.setHorizontalHeaderLabels(["Nombre", "Estado", "Tipo de procesamiento"])
        self.tabla_documentos.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla_documentos.itemSelectionChanged.connect(self._on_documento_seleccionado)
        layout_documentos.addWidget(self.tabla_documentos)
        splitter_principal.addWidget(panel_documentos)
        self._panel_documentos_revision = panel_documentos

        # -- centro: visor dual --
        splitter_visor = QSplitter()

        panel_original = QWidget()
        layout_original = QVBoxLayout(panel_original)
        layout_original.addWidget(QLabel("Original"))
        self.area_original = QScrollArea()
        self.area_original.setWidgetResizable(True)
        self.etiqueta_original = QLabel("Seleccione un documento.")
        self.etiqueta_original.setWordWrap(True)
        self.area_original.setWidget(self.etiqueta_original)
        layout_original.addWidget(self.area_original)

        barra_paginacion = QHBoxLayout()
        self.boton_pagina_anterior = QPushButton("<- Pagina anterior")
        self.boton_pagina_anterior.clicked.connect(self._pagina_pdf_anterior)
        self.etiqueta_pagina = QLabel("")
        self.boton_pagina_siguiente = QPushButton("Pagina siguiente ->")
        self.boton_pagina_siguiente.clicked.connect(self._pagina_pdf_siguiente)
        barra_paginacion.addWidget(self.boton_pagina_anterior)
        barra_paginacion.addWidget(self.etiqueta_pagina)
        barra_paginacion.addWidget(self.boton_pagina_siguiente)
        barra_paginacion.addStretch()
        self.boton_abrir_externo = QPushButton("Abrir con la aplicacion del sistema")
        self.boton_abrir_externo.clicked.connect(self._abrir_original_externo)
        barra_paginacion.addWidget(self.boton_abrir_externo)
        layout_original.addLayout(barra_paginacion)
        self._actualizar_controles_paginacion()

        splitter_visor.addWidget(panel_original)
        self._panel_original_revision = panel_original

        panel_extraido = QWidget()
        layout_extraido = QVBoxLayout(panel_extraido)
        barra_panel_extraido = QHBoxLayout()
        self.etiqueta_panel_extraido = QLabel("Extraido / revisado")
        barra_panel_extraido.addWidget(self.etiqueta_panel_extraido)
        barra_panel_extraido.addStretch()
        # Editor con numeros de renglon + buscar/reemplazar (2026-09-04,
        # pedido explicito de un usuario real -- ver docstring de
        # ui/editor_texto.py). Cortar/copiar/pegar/deshacer/rehacer ya
        # los trae `QPlainTextEdit` de fabrica, por eso no se agrega
        # ningun boton para esos.
        self.boton_buscar_reemplazar = QPushButton("Buscar/Reemplazar...")
        self.boton_buscar_reemplazar.setToolTip("Buscar y reemplazar texto en 'Normalizado' (Ctrl+F).")
        self.boton_buscar_reemplazar.clicked.connect(self._on_buscar_reemplazar)
        barra_panel_extraido.addWidget(self.boton_buscar_reemplazar)
        self.boton_ir_a_renglon = QPushButton("Ir a renglon...")
        self.boton_ir_a_renglon.setToolTip("Saltar a un numero de renglon especifico en 'Normalizado' (Ctrl+G).")
        self.boton_ir_a_renglon.clicked.connect(self._on_ir_a_renglon)
        barra_panel_extraido.addWidget(self.boton_ir_a_renglon)
        layout_extraido.addLayout(barra_panel_extraido)
        self.texto_extraido = EditorConNumerosDeLinea()
        self.texto_extraido.setReadOnly(True)
        layout_extraido.addWidget(self.texto_extraido)
        # Atajos de teclado, acotados a este editor especifico
        # (WidgetShortcut: solo se disparan si `texto_extraido` mismo
        # tiene el foco) para no competir con atajos de otras pantallas
        # de esta misma ventana.
        atajo_buscar = QShortcut(QKeySequence("Ctrl+F"), self.texto_extraido)
        atajo_buscar.setContext(Qt.ShortcutContext.WidgetShortcut)
        atajo_buscar.activated.connect(self._on_buscar_reemplazar)
        atajo_ir_a_renglon = QShortcut(QKeySequence("Ctrl+G"), self.texto_extraido)
        atajo_ir_a_renglon.setContext(Qt.ShortcutContext.WidgetShortcut)
        atajo_ir_a_renglon.activated.connect(self._on_ir_a_renglon)
        # Nivel 1 (confianza de OCR, 2026-08-01): resumen de cuantas
        # palabras quedaron resaltadas abajo -- ver
        # `_resaltar_baja_confianza()`. Vacio cuando no hay ninguna
        # (documento sin OCR, o ninguna palabra por debajo del umbral).
        self.etiqueta_baja_confianza = QLabel("")
        self.etiqueta_baja_confianza.setWordWrap(True)
        layout_extraido.addWidget(self.etiqueta_baja_confianza)
        self.boton_guardar_correccion = QPushButton("Guardar correccion")
        self.boton_guardar_correccion.clicked.connect(self._on_guardar_correccion)
        self.boton_guardar_correccion.setEnabled(False)
        layout_extraido.addWidget(self.boton_guardar_correccion)
        splitter_visor.addWidget(panel_extraido)

        splitter_principal.addWidget(splitter_visor)

        # -- panel derecho: incidencias + acciones --
        panel_lateral = QWidget()
        layout_lateral = QVBoxLayout(panel_lateral)

        self.etiqueta_estado_documento = QLabel("")
        self.etiqueta_estado_documento.setWordWrap(True)
        layout_lateral.addWidget(self.etiqueta_estado_documento)

        self.boton_revisar = QPushButton("Aprobar revision")
        self.boton_revisar.clicked.connect(self._on_aprobar_revision)
        self.boton_revisar.setEnabled(False)
        layout_lateral.addWidget(self.boton_revisar)

        layout_lateral.addWidget(QLabel("Incidencias"))
        self.lista_incidencias = QListWidget()
        self.lista_incidencias.setMinimumHeight(90)
        layout_lateral.addWidget(self.lista_incidencias, stretch=1)

        self.boton_registrar_incidencia = QPushButton("Registrar incidencia")
        self.boton_registrar_incidencia.clicked.connect(self._on_registrar_incidencia)
        self.boton_registrar_incidencia.setEnabled(False)
        layout_lateral.addWidget(self.boton_registrar_incidencia)

        layout_lateral.addWidget(QLabel("Fechas/cifras detectadas (verificar contra el original)"))
        self.lista_verificaciones = QListWidget()
        self.lista_verificaciones.setMinimumHeight(90)
        self.lista_verificaciones.itemClicked.connect(self._on_hallazgo_verificacion_seleccionado)
        layout_lateral.addWidget(self.lista_verificaciones, stretch=1)

        layout_lateral.addWidget(QLabel("Vigencia y fuente"))
        self.etiqueta_vigencia_fuente = QLabel("Sin registrar.")
        self.etiqueta_vigencia_fuente.setWordWrap(True)
        layout_lateral.addWidget(self.etiqueta_vigencia_fuente)

        self.boton_registrar_vigencia_fuente = QPushButton("Registrar / actualizar vigencia y fuente")
        self.boton_registrar_vigencia_fuente.clicked.connect(self._on_registrar_vigencia_fuente)
        self.boton_registrar_vigencia_fuente.setEnabled(False)
        layout_lateral.addWidget(self.boton_registrar_vigencia_fuente)

        # Envuelto en QScrollArea (bug real reportado 2026-07-31): sin
        # esto, en una ventana de poca altura el contenido de mas abajo
        # (Vigencia y fuente, su boton) quedaba apretado contra el borde
        # de la ventana o directamente recortado, sin ninguna forma de
        # llegar a el -- ahora siempre se puede desplazar.
        area_lateral = QScrollArea()
        area_lateral.setWidgetResizable(True)
        area_lateral.setWidget(panel_lateral)
        splitter_principal.addWidget(area_lateral)
        self._area_lateral_revision = area_lateral

        # Proporciones iniciales: menos espacio para la lista de
        # documentos (tres columnas cortas, normalmente pocas filas) y
        # mas para el visor Original/Normalizado (el area de trabajo
        # real de esta pantalla) y el panel lateral (texto e
        # incidencias, necesita ancho legible). El usuario puede seguir
        # ajustando los splitters a mano; esto solo mejora el punto de
        # partida.
        splitter_principal.setSizes([220, 760, 340])
        splitter_visor.setSizes([480, 480])

        return pagina

    def _on_alternar_panel_documentos_revision(self, visible: bool) -> None:
        """Muestra/oculta el panel izquierdo ("Documentos del proyecto")
        de la pantalla Revision -- ver docstring de
        `_construir_pagina_revision()`. Ocultar el widget dentro del
        `QSplitter` basta para que Qt le devuelva ese espacio al visor
        central; no hace falta recalcular tamanos a mano."""
        self._panel_documentos_revision.setVisible(visible)
        self.boton_alternar_panel_documentos.setText("Ocultar documentos" if visible else "Mostrar documentos")

    def _on_alternar_panel_estado_revision(self, visible: bool) -> None:
        """Muestra/oculta el panel derecho ("Estado": estado, incidencias,
        fechas/cifras, vigencia y fuente) de la pantalla Revision -- ver
        docstring de `_construir_pagina_revision()`."""
        self._area_lateral_revision.setVisible(visible)
        self.boton_alternar_panel_estado.setText("Ocultar estado" if visible else "Mostrar estado")

    def _on_alternar_panel_original_revision(self, visible: bool) -> None:
        """Muestra/oculta el panel "Original" dentro de `splitter_visor`,
        de modo que "Normalizado" (el editor) recupere ese espacio -- ver
        el comentario en `_construir_pagina_revision()` sobre por que se
        eligio este boton en vez de una ventana aparte."""
        self._panel_original_revision.setVisible(visible)
        self.boton_alternar_panel_original.setText("Ocultar original" if visible else "Mostrar original")

    # -- proyectos -----------------------------------------------------

    def _cargar_proyectos(self) -> None:
        # incluir_archivados=False (Auditoria 2026-09-02, RAG_CONTENT_01):
        # este selector es para ABRIR un proyecto a trabajar -- un
        # proyecto archivado ya no tiene sentido ahi (es justamente lo
        # que "Archivar proyecto" en la pantalla "Proyectos" existe para
        # lograr: sacarlo de en medio). La tabla de esa pantalla si sigue
        # mostrando los archivados, para poder consultarlos o eliminarlos.
        self.combo_proyectos.clear()
        for proyecto in self.ctx.projects.listar_proyectos(incluir_archivados=False):
            self.combo_proyectos.addItem(f"{proyecto.nombre} ({proyecto.id})", proyecto.id)

    def _on_abrir_proyecto(self) -> None:
        proyecto_id = self.combo_proyectos.currentData()
        if proyecto_id is None:
            return
        proyecto = self.ctx.projects.obtener_proyecto(proyecto_id)
        if proyecto is None:
            QMessageBox.warning(self, "Proyecto no encontrado", f"No se encontro el proyecto '{proyecto_id}'.")
            return
        # Fuga de recursos real encontrada en la segunda auditoria
        # 2026-07-31: `abrir_proyecto()` crea un engine/Session de
        # SQLAlchemy nuevo (app/bootstrap.py) cada vez que se llama --
        # si el operador abre varios proyectos (o el mismo dos veces) en
        # la misma corrida, la sesion anterior nunca se cerraba, dejando
        # la conexion SQLite abierta hasta que el proceso terminara. Se
        # cierra aqui antes de reemplazar self.pctx.
        if self.pctx is not None:
            self.pctx.session.close()
        self.pctx = abrir_proyecto(self.ctx, proyecto)
        self.proyecto_actual = proyecto
        self._cargar_documentos()
        self._propagar_contexto_a_paneles()
        # Fase 11.3 (seccion 4.11.1: "el asistente por etapas es la
        # vista predeterminada AL ABRIR UN PROYECTO"): si el operador
        # estaba en "Inicio" (pantalla principal, la vista de entrada
        # antes de tener un proyecto abierto), pasar automaticamente al
        # asistente. Si ya estaba en modo avanzado a proposito, no se lo
        # saca de ahi solo por abrir/cambiar de proyecto.
        if self.radio_inicio.isChecked():
            self.radio_asistente.setChecked(True)
            self.modo_stack.setCurrentIndex(1)

    def _propagar_contexto_a_paneles(self) -> None:
        """Fase 11: cada pagina del menu (salvo "Proyectos", que no
        depende de ningun proyecto abierto, y "Revision", que sigue su
        propio ciclo de vida sin cambios) recibe el `pctx`/`proyecto`
        recien abiertos aqui -- llamado tanto al abrir un proyecto como
        al cambiar de pagina (`_on_cambiar_pagina`), para no mostrar
        datos obsoletos si algo cambio en otra pagina mientras tanto."""
        for pagina in self._paginas_con_proyecto:
            pagina.establecer_proyecto(self.pctx, self.proyecto_actual)
        # Fase 11.2: el asistente tambien se refresca aqui (restaura su
        # etapa autoguardada -- ver ui.wizard.estado_asistente).
        self.asistente.establecer_proyecto(self.pctx, self.proyecto_actual)
        # Fase 11.3: la pantalla principal tambien, para que sus datos
        # del proyecto (documentos por estado, incidencias criticas...)
        # no queden obsoletos si el operador vuelve a "Inicio" despues.
        self.pantalla_principal.establecer_proyecto(self.pctx, self.proyecto_actual)

    def _on_cambiar_pagina(self, indice: int) -> None:
        self.paginas.setCurrentIndex(indice)
        pagina_actual = self.paginas.currentWidget()
        # isinstance (no "in self._paginas_con_proyecto") para que Mypy
        # angoste pagina_actual -- ver docstring de _PanelConProyecto.
        # Equivalente en la practica: "Proyectos" y "Revision" son las
        # unicas paginas que no implementan establecer_proyecto.
        if isinstance(pagina_actual, _PanelConProyecto):
            pagina_actual.establecer_proyecto(self.pctx, self.proyecto_actual)
        elif pagina_actual is self.pagina_revision:
            # Bug real encontrado 2026-07-30: "Revision" no implementa
            # establecer_proyecto() (es la pagina original del
            # prototipo, ver docstring del modulo) y por eso quedaba
            # fuera del refresco de arriba -- su tabla de documentos
            # solo se cargaba al abrir el proyecto o al aprobar una
            # revision, nunca al simplemente entrar a esta pestana. Un
            # documento clasificado/extraido en "Procesamiento" (u
            # otra pestana) mientras el operador ya tenia el proyecto
            # abierto no aparecia reflejado aqui hasta cerrar y volver
            # a abrir el proyecto -- justo lo que esta pestana existe
            # para permitir cotejar (Documento Maestro, seccion 4.7:
            # revision contra el original). _cargar_documentos()
            # preserva la seleccion actual, mismo criterio que el resto
            # de los paneles (seccion 4.11.1, baja friccion).
            self._cargar_documentos()

    def _on_proyecto_creado_desde_panel(self, proyecto_id: str) -> None:
        """Conectado a `ProyectosPanel.proyecto_creado` (Fase 11): un
        proyecto recien creado se abre de inmediato -- principio de baja
        friccion (Documento Maestro, seccion 4.11.1), sin que el
        operador tenga que ir a buscarlo a mano en el combo."""
        self._cargar_proyectos()
        indice = self.combo_proyectos.findData(proyecto_id)
        if indice >= 0:
            self.combo_proyectos.setCurrentIndex(indice)
            self._on_abrir_proyecto()

    def _on_proyecto_modificado_desde_panel(self, proyecto_id: str) -> None:
        """Conectado a `ProyectosPanel.proyecto_modificado` (Auditoria
        2026-09-02, RAG_CONTENT_01): un proyecto recien archivado o
        eliminado debe desaparecer del selector "Proyecto:" -- se
        recarga el combo con el mismo criterio de `_cargar_proyectos()`
        (incluir_archivados=False). Si el proyecto afectado era el que
        estaba abierto, no basta con avisar: hay que soltar `self.pctx`/
        `self.proyecto_actual` y propagar `None` a todos los paneles de
        inmediato (hallazgo real de la auditoria independiente de esta
        misma ronda -- antes solo se mostraba el aviso, pero los paneles
        seguian operando contra el `pctx` viejo hasta que el operador
        abriera otro proyecto a mano; en el caso de "Eliminar", ese
        `pctx` apunta a una carpeta que ya no existe en disco). Cada
        panel ya sabe manejar `pctx=None` -- es el mismo estado que
        tienen antes de abrir cualquier proyecto (ver
        `establecer_proyecto` en cualquier panel, p.ej.
        `ui/panels/inventario_panel.py`)."""
        self._cargar_proyectos()
        if self.proyecto_actual is not None and self.proyecto_actual.id == proyecto_id:
            if self.pctx is not None:
                self.pctx.session.close()
            self.pctx = None
            self.proyecto_actual = None
            self._propagar_contexto_a_paneles()
            QMessageBox.information(
                self,
                "Proyecto ya no disponible",
                "El proyecto que tenia abierto se archivo o elimino. Abra otro proyecto desde el selector "
                "de arriba antes de seguir trabajando.",
            )

    def _cargar_documentos(self, seleccionar_id: str | None = None) -> None:
        """Puebla `tabla_documentos` con TODOS los documentos del
        proyecto abierto -- la lista completa de archivos que ya
        pasaron (o estan pasando) por el flujo de procesamiento, para
        que el operador pueda elegir cualquiera y cotejarlo contra su
        original (Documento Maestro, seccion 4.7). Se llama al abrir el
        proyecto, al aprobar una revision, y -- desde la correccion del
        bug real de 2026-07-30 -- cada vez que se entra a esta pestana
        (ver `_on_cambiar_pagina`).

        Preserva la seleccion actual a traves del recargue (mismo
        criterio que `ui.panels.procesamiento_panel`/
        `normalizacion_panel`/etc., seccion 4.11.1: baja friccion) --
        sin esto, cada refresco (incluido el automatico al cambiar de
        pestana) dejaba la tabla sin ninguna fila seleccionada."""
        if seleccionar_id is None:
            seleccionar_id = self._documento_id_seleccionado_en_revision()
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

    def _documento_id_seleccionado_en_revision(self) -> str | None:
        filas = self.tabla_documentos.selectionModel().selectedRows()
        if not filas:
            return None
        item = self.tabla_documentos.item(filas[0].row(), 0)
        return item.data(256) if item is not None else None

    # -- seleccion de documento -----------------------------------------

    def _on_documento_seleccionado(self) -> None:
        filas = self.tabla_documentos.selectionModel().selectedRows()
        if not filas or self.pctx is None:
            return
        item_fila = self.tabla_documentos.item(filas[0].row(), 0)
        if item_fila is None:
            return
        documento_id = item_fila.data(256)
        documento = self.pctx.documents.obtener_documento(documento_id)
        if documento is None:
            return
        self.documento_actual = documento
        self._pagina_pdf_actual = 0
        self._mostrar_original(documento)
        self._mostrar_extraido(documento)
        self._mostrar_incidencias(documento)
        self._mostrar_vigencia_fuente(documento)
        self._actualizar_panel_estado(documento)
        self._sincronizar_navegacion_markdown()

    def _mostrar_original(self, documento: Documento) -> None:
        ruta = documento.ruta_copia_original
        if documento.formato == FormatoDocumento.PDF:
            self._num_paginas_pdf = contar_paginas(ruta) if Path(ruta).exists() else 0
            self._pagina_pdf_actual = 0
            self._render_pagina_pdf_actual(ruta)
        elif documento.formato in _FORMATOS_IMAGEN:
            self._num_paginas_pdf = 0
            self.etiqueta_original.clear()
            self.etiqueta_original.setPixmap(QPixmap(ruta))
        elif documento.formato in _FORMATOS_TEXTO_PLANO:
            self._num_paginas_pdf = 0
            try:
                contenido = Path(ruta).read_text(encoding="utf-8")
            except OSError as exc:
                contenido = f"No se pudo leer el archivo original: {mensaje_amigable(exc)}"
            self.etiqueta_original.clear()
            self.etiqueta_original.setText(contenido)
        else:
            self._num_paginas_pdf = 0
            self.etiqueta_original.clear()
            self.etiqueta_original.setText(
                f"Vista previa no disponible para '{documento.formato.value}' en este prototipo.\n\n"
                f"Ruta del original: {ruta}"
            )
        self._actualizar_controles_paginacion()

    def _render_pagina_pdf_actual(self, ruta: str) -> None:
        if self._num_paginas_pdf == 0:
            self.etiqueta_original.setText("No se pudo abrir el PDF original.")
            return
        pixmap = render_pagina(ruta, self._pagina_pdf_actual)
        self.etiqueta_original.setText("")
        self.etiqueta_original.setPixmap(pixmap)

    def _pagina_pdf_anterior(self) -> None:
        if self.documento_actual is None or self._pagina_pdf_actual <= 0:
            return
        self._pagina_pdf_actual -= 1
        self._render_pagina_pdf_actual(self.documento_actual.ruta_copia_original)
        self._actualizar_controles_paginacion()
        self._sincronizar_navegacion_markdown()

    def _pagina_pdf_siguiente(self) -> None:
        if self.documento_actual is None or self._pagina_pdf_actual >= self._num_paginas_pdf - 1:
            return
        self._pagina_pdf_actual += 1
        self._render_pagina_pdf_actual(self.documento_actual.ruta_copia_original)
        self._actualizar_controles_paginacion()
        self._sincronizar_navegacion_markdown()

    def _sincronizar_navegacion_markdown(self) -> None:
        """Modulo 8 (navegacion sincronizada real): si el documento
        actual tiene `mapa_paginas` (solo lo llenan PdfExtractor/
        PdfOcrExtractor -- ver su docstring en domain.documents.entities),
        mueve el cursor del panel de Markdown al desplazamiento donde
        empieza la pagina actualmente mostrada del original. Sin mapa
        (el resto de formatos), no hace nada -- nunca falla, solo no
        sincroniza."""
        if self.documento_actual is None:
            return
        mapa = self.documento_actual.mapa_paginas
        if not mapa or self._pagina_pdf_actual >= len(mapa):
            return
        self._saltar_cursor_markdown(mapa[self._pagina_pdf_actual])

    def _actualizar_controles_paginacion(self) -> None:
        tiene_paginas = self._num_paginas_pdf > 0
        self.boton_pagina_anterior.setEnabled(tiene_paginas and self._pagina_pdf_actual > 0)
        self.boton_pagina_siguiente.setEnabled(tiene_paginas and self._pagina_pdf_actual < self._num_paginas_pdf - 1)
        if tiene_paginas:
            self.etiqueta_pagina.setText(f"Pagina {self._pagina_pdf_actual + 1} de {self._num_paginas_pdf}")
        else:
            self.etiqueta_pagina.setText("")

    def _abrir_original_externo(self) -> None:
        if self.documento_actual is None:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.documento_actual.ruta_copia_original))

    def _mostrar_extraido(self, documento: Documento) -> None:
        # ruta_markdown_vigente() es la misma fuente unica de verdad que
        # usa NormalizarDocumento (domain.documents.entities.Documento):
        # normalizado -> corregido (Modulo 8) -> extraido en crudo.
        ruta = documento.ruta_markdown_vigente()
        if ruta is None:
            self.texto_extraido.setPlainText("Este documento todavia no tiene Markdown extraido.")
            self.texto_extraido.setReadOnly(True)
            self.boton_guardar_correccion.setEnabled(False)
            self.lista_verificaciones.clear()
            self.texto_extraido.setExtraSelections([])
            self.etiqueta_baja_confianza.setText("")
            return
        if documento.ruta_normalizado is not None:
            self.etiqueta_panel_extraido.setText("Normalizado")
        elif documento.ruta_revisado is not None:
            self.etiqueta_panel_extraido.setText("Extraido / revisado (con correccion guardada)")
        else:
            self.etiqueta_panel_extraido.setText("Extraido / revisado")
        try:
            contenido = Path(ruta).read_text(encoding="utf-8")
        except OSError as exc:
            contenido = f"No se pudo leer '{ruta}': {mensaje_amigable(exc)}"
        self.texto_extraido.setPlainText(contenido)
        # Modulo 8 (correccion): solo se puede guardar una correccion
        # mientras el documento sigue EXTRAIDO -- ver
        # Documento.corregir(). Deshabilitar edicion/boton fuera de ese
        # estado evita ofrecer una accion que el backend rechazaria
        # (defensa en profundidad, mismo principio ya usado con el
        # boton "Aprobar revision").
        editable = documento.estado == EstadoDocumento.EXTRAIDO
        self.texto_extraido.setReadOnly(not editable)
        self.boton_guardar_correccion.setEnabled(editable)
        self._resaltar_baja_confianza(documento)
        self._mostrar_verificaciones(contenido)

    def _resaltar_baja_confianza(self, documento: Documento) -> None:
        """Resalta con fondo ambar los rangos de texto que Tesseract
        marco con baja confianza (Nivel 1, ver
        domain.documents.ocr_table_reconstruction.RangoBajaConfianza),
        para que el revisor sepa donde fijarse primero al cotejar contra
        el original -- esto nunca reemplaza su criterio, solo lo dirige
        (Modulo 13: el revisor sigue siendo la autoridad final).

        Misma limitacion aceptada que `Documento.mapa_paginas` (ver su
        docstring): `Documento.corregir()` no recalcula
        `rangos_baja_confianza`, asi que tras una correccion manual los
        rangos pueden apuntar a texto ligeramente distinto o quedar
        fuera de los limites del texto vigente -- se descartan en
        silencio los que ya no encajan, nunca se lanza una excepcion por
        esto."""
        largo_texto = len(self.texto_extraido.toPlainText())
        formato = QTextCharFormat()
        formato.setBackground(QColor(AMBAR_ATENCION_FONDO))
        selecciones = []
        for rango in documento.rangos_baja_confianza:
            if rango.inicio < 0 or rango.fin > largo_texto or rango.inicio >= rango.fin:
                continue
            cursor = QTextCursor(self.texto_extraido.document())
            cursor.setPosition(rango.inicio)
            cursor.setPosition(rango.fin, QTextCursor.MoveMode.KeepAnchor)
            seleccion = QTextEdit.ExtraSelection()
            seleccion.cursor = cursor
            seleccion.format = formato
            selecciones.append(seleccion)
        self.texto_extraido.setExtraSelections(selecciones)
        if selecciones:
            self.etiqueta_baja_confianza.setText(
                f"{len(selecciones)} palabra(s) resaltada(s) arriba: el OCR tuvo baja confianza "
                "en ellas -- cotejar contra el original."
            )
        else:
            self.etiqueta_baja_confianza.setText("")

    def _mostrar_verificaciones(self, markdown: str) -> None:
        # Nivel 2 (validaciones numericas), 2026-08-01: se combinan los
        # hallazgos de deteccion de fechas/cifras (Modulo 8 original) con
        # los de validacion de calendario (ya incluidos en cada
        # HallazgoVerificacion de tipo FECHA, ver
        # domain.documents.verificacion_fechas_cifras) y los de totales
        # de tabla (domain.documents.verificacion_totales_tabla) en una
        # sola lista, ordenada por posicion -- mismo criterio de lectura
        # de arriba hacia abajo que ya usaba la lista original. Los que
        # traen `advertencia` (una fecha imposible o una tabla que no
        # cuadra) se resaltan en ambar -- mismo color que Nivel 1 (OCR de
        # baja confianza), para un lenguaje visual consistente de
        # "revisar esto con mas cuidado" en toda la pantalla.
        self.lista_verificaciones.clear()
        hallazgos = detectar_fechas_y_cifras(markdown) + verificar_totales_de_tablas(markdown)
        hallazgos.sort(key=lambda h: h.posicion)
        for hallazgo in hallazgos:
            texto_item = f"[{hallazgo.tipo.value}] {hallazgo.texto}"
            if hallazgo.advertencia:
                texto_item = f"⚠ {texto_item}"
            item = QListWidgetItem(texto_item)
            item.setData(256, hallazgo.posicion)  # Qt.UserRole == 256
            if hallazgo.advertencia:
                item.setToolTip(hallazgo.advertencia)
                item.setForeground(QBrush(QColor(AMBAR_ATENCION)))
                item.setBackground(QBrush(QColor(AMBAR_ATENCION_FONDO)))
            self.lista_verificaciones.addItem(item)

    def _on_hallazgo_verificacion_seleccionado(self, item: QListWidgetItem) -> None:
        posicion = item.data(256)
        if posicion is None:
            return
        self._saltar_cursor_markdown(posicion)

    def _saltar_cursor_markdown(self, posicion: int) -> None:
        cursor = self.texto_extraido.textCursor()
        cursor.setPosition(min(posicion, len(self.texto_extraido.toPlainText())))
        self.texto_extraido.setTextCursor(cursor)
        self.texto_extraido.ensureCursorVisible()

    def _on_buscar_reemplazar(self) -> None:
        """Abre el dialogo de Buscar/Reemplazar sobre "Normalizado". El
        reemplazo solo se habilita si el editor esta en modo edicion
        (documento en estado EXTRAIDO); si esta en solo lectura, el
        dialogo igual permite buscar (ver BuscarReemplazarDialog)."""
        dialogo = BuscarReemplazarDialog(self, self.texto_extraido, permitir_reemplazar=not self.texto_extraido.isReadOnly())
        dialogo.exec()

    def _on_ir_a_renglon(self) -> None:
        """Salta a un numero de renglon especifico dentro de
        "Normalizado", pedido por el usuario como equivalente al "Ir a
        linea" de un editor de texto convencional."""
        total_renglones = max(1, self.texto_extraido.blockCount())
        numero, aceptado = QInputDialog.getInt(
            self,
            "Ir a renglon",
            "Numero de renglon:",
            1,
            1,
            total_renglones,
            1,
        )
        if not aceptado:
            return
        if not self.texto_extraido.ir_a_linea(numero):
            QMessageBox.information(
                self,
                "Ir a renglon",
                f"El renglon {numero} no existe en este documento (total: {total_renglones}).",
            )

    def _on_guardar_correccion(self) -> None:
        if self.pctx is None or self.documento_actual is None:
            return
        markdown_corregido = self.texto_extraido.toPlainText()
        try:
            documento = self.pctx.documents.corregir_extraccion(self.documento_actual.id, markdown_corregido)
        except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(self, "No se pudo guardar la correccion", mensaje_amigable(exc))
            return
        self.documento_actual = documento
        self._resaltar_baja_confianza(documento)
        self._mostrar_verificaciones(markdown_corregido)
        # Sin dialogo modal de confirmacion a proposito -- mismo criterio
        # que el resto de esta ventana: los dialogos bloqueantes se
        # reservan para errores (QMessageBox.critical/warning); un
        # exito se refleja en el estado visible de la propia ventana.
        self.etiqueta_panel_extraido.setText("Extraido / revisado (con correccion guardada)")

    def _mostrar_incidencias(self, documento: Documento) -> None:
        self.lista_incidencias.clear()
        if self.pctx is None:
            return
        for incidencia in self.pctx.incidents.listar_incidencias_de_documento(documento.id):
            self.lista_incidencias.addItem(
                f"[{incidencia.severidad.value}] {incidencia.tipo} -- {incidencia.estado.value}"
            )
        self.boton_registrar_incidencia.setEnabled(True)

    def _mostrar_vigencia_fuente(self, documento: Documento) -> None:
        """Modulo 11 (Vigencias y fuentes): resumen de solo lectura de
        lo ya registrado -- editar/registrar siempre pasa por el
        dialogo (_on_registrar_vigencia_fuente), nunca directo aqui."""
        self.boton_registrar_vigencia_fuente.setEnabled(self.pctx is not None)
        if self.pctx is None:
            self.etiqueta_vigencia_fuente.setText("Sin registrar.")
            return
        fuente = self.pctx.validity.obtener_fuente(documento.id)
        vigencia = self.pctx.validity.obtener_vigencia(documento.id)
        if fuente is None and vigencia is None:
            self.etiqueta_vigencia_fuente.setText("Sin registrar.")
            return
        partes = []
        if fuente is not None:
            partes.append(f"Fuente: {fuente.sistema_origen} (autoridad: {fuente.autoridad})")
        else:
            partes.append("Fuente: sin registrar.")
        if vigencia is not None and not vigencia_desconocida(vigencia):
            hasta = "sin vencimiento" if vigencia.sin_vencimiento else str(vigencia.vigente_hasta)
            partes.append(f"Vigencia: desde {vigencia.vigente_desde} hasta {hasta}.")
        else:
            partes.append("Vigencia: DESCONOCIDA -- registrela antes de aprobar un documento critico.")
        self.etiqueta_vigencia_fuente.setText("\n".join(partes))

    def _actualizar_panel_estado(self, documento: Documento) -> None:
        hay_criticas = self.pctx.incidents.existen_criticas_abiertas(documento.id) if self.pctx else False
        # Segunda regla de Modulo 13 (2026-07-28): solo aplica a
        # documentos criticos (Documento.criticidad == CRITICO) -- ver
        # domain.governance.exceptions.VigenciaDesconocidaError.
        vigencia_bloquea = (
            self.pctx is not None
            and documento.criticidad == Criticidad.CRITICO
            and vigencia_desconocida(self.pctx.validity.obtener_vigencia(documento.id))
        )
        avisos = []
        if hay_criticas:
            avisos.append("tiene incidencias CRITICAS abiertas: resuelvalas antes de aprobar la revision")
        if vigencia_bloquea:
            avisos.append("es critico y su vigencia es DESCONOCIDA: registrela antes de aprobar la revision")
        aviso = f" -- {'; ademas, '.join(avisos)}" if avisos else ""
        self.etiqueta_estado_documento.setText(f"Estado: {documento.estado.value}{aviso}")
        # Modulo 13 (gobernanza): ademas de la verificacion real que hace
        # GovernanceService dentro de revisar_documento() (que bloquea
        # de verdad, con o sin GUI), este boton se deshabilita antes de
        # que el operador intente aprobar -- "todo bloqueo de estado se
        # explica en espanol simple: que falta y que accion lo resuelve"
        # (Documento Maestro, seccion 4.11.1), en vez de dejar que
        # descubra el bloqueo solo al hacer clic.
        self.boton_revisar.setEnabled(
            documento.estado == EstadoDocumento.EXTRAIDO and not hay_criticas and not vigencia_bloquea
        )

    # -- acciones -----------------------------------------------------

    def _on_aprobar_revision(self) -> None:
        if self.pctx is None or self.documento_actual is None:
            return
        dialogo = RevisarDocumentoDialog(self)
        if not dialogo.exec():
            return
        revisor = dialogo.revisor()
        if not revisor:
            QMessageBox.warning(self, "Revisor requerido", "Debe indicar quien realiza la revision.")
            return
        incidencias_abiertas = [
            incidencia.id
            for incidencia in self.pctx.incidents.listar_incidencias_de_documento(self.documento_actual.id)
        ]
        try:
            documento = self.pctx.documents.revisar_documento(
                self.documento_actual.id,
                revisor,
                dialogo.comentario(),
                incidencias_abiertas,
            )
        except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(self, "No se pudo aprobar la revision", mensaje_amigable(exc))
            return
        self.documento_actual = documento
        self._cargar_documentos()
        self._actualizar_panel_estado(documento)
        # Tras aprobar, el documento ya no esta EXTRAIDO -- refresca el
        # panel de Markdown para que la edicion/boton de correccion se
        # deshabiliten de inmediato (ver _mostrar_extraido()).
        self._mostrar_extraido(documento)

    def _on_registrar_incidencia(self) -> None:
        if self.pctx is None or self.documento_actual is None:
            return
        dialogo = RegistrarIncidenciaDialog(self)
        if not dialogo.exec():
            return
        if not dialogo.tipo() or not dialogo.evidencia() or not dialogo.impacto():
            QMessageBox.warning(self, "Campos requeridos", "Tipo, evidencia e impacto no pueden estar vacios.")
            return
        try:
            self.pctx.incidents.registrar_incidencia(
                proyecto_id=self.documento_actual.proyecto_id,
                documento_id=self.documento_actual.id,
                etapa=dialogo.etapa(),
                tipo=dialogo.tipo(),
                severidad=dialogo.severidad(),
                evidencia=dialogo.evidencia(),
                impacto=dialogo.impacto(),
            )
        except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(self, "No se pudo registrar la incidencia", mensaje_amigable(exc))
            return
        self._mostrar_incidencias(self.documento_actual)
        self._actualizar_panel_estado(self.documento_actual)

    def _on_registrar_vigencia_fuente(self) -> None:
        if self.pctx is None or self.documento_actual is None:
            return
        fuente_actual = self.pctx.validity.obtener_fuente(self.documento_actual.id)
        vigencia_actual = self.pctx.validity.obtener_vigencia(self.documento_actual.id)
        # El documento actual no puede sustituirse a si mismo -- se
        # excluye de las opciones del selector (ver docstring de
        # RegistrarVigenciaDialog).
        documentos_disponibles = [
            documento
            for documento in self.pctx.documents.listar_documentos()
            if documento.id != self.documento_actual.id
        ]
        dialogo = RegistrarVigenciaDialog(
            self,
            fuente=fuente_actual,
            vigencia=vigencia_actual,
            documentos_disponibles=documentos_disponibles,
        )
        if not dialogo.exec():
            return
        try:
            # Las fechas se parsean adentro del dialogo (pueden lanzar
            # ValueError con un mensaje en espanol simple si el texto
            # no tiene el formato esperado) -- se leen ANTES de llamar
            # a application, para no dejar una Fuente guardada si la
            # Vigencia todavia tiene un error de formato.
            fecha_emision = dialogo.fecha_emision()
            vigente_desde = dialogo.vigente_desde()
            vigente_hasta = dialogo.vigente_hasta()
        except ValueError as exc:
            QMessageBox.warning(self, "Fecha invalida", mensaje_amigable(exc))
            return
        if not dialogo.sistema_origen() or not dialogo.autoridad_fuente() or not dialogo.evidencia_consulta():
            QMessageBox.warning(
                self, "Campos requeridos", "Sistema de origen, autoridad y evidencia de consulta no pueden estar vacios."
            )
            return
        try:
            self.pctx.validity.registrar_fuente(
                self.documento_actual.id,
                dialogo.sistema_origen(),
                dialogo.autoridad_fuente(),
                dialogo.evidencia_consulta(),
            )
            self.pctx.validity.registrar_vigencia(
                self.documento_actual.id,
                fecha_emision,
                vigente_desde,
                vigente_hasta,
                dialogo.sin_vencimiento(),
                dialogo.autoridad_vigencia(),
                dialogo.sustituye_a(),
            )
        except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(self, "No se pudo registrar la vigencia/fuente", mensaje_amigable(exc))
            return
        self._mostrar_vigencia_fuente(self.documento_actual)
        # Modulo 13, segunda regla: si el documento es critico, registrar
        # su vigencia puede levantar el bloqueo de aprobacion de
        # inmediato -- refresca el boton/aviso sin esperar a que el
        # operador cambie de documento.
        self._actualizar_panel_estado(self.documento_actual)
